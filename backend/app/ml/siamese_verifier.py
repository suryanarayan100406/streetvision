"""Siamese CNN (ResNet-18 backbone) for repair verification.

Compares a before/after image pair and outputs a similarity score.
Score > 0.85 → Repaired, 0.60-0.85 → Partially_Repaired, < 0.60 → Not_Repaired.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import numpy as np
import structlog

from app.config import settings
from app.services.model_registry import get_active_model_weights

logger = structlog.get_logger(__name__)

_model = None
_fallback_encoder = None
_device = None
_lock = asyncio.Lock()

DEFAULT_MODEL_PATH = Path(settings.SIAMESE_MODEL_PATH)
REPAIRED_THRESHOLD = 0.85
PARTIAL_THRESHOLD = 0.60
INPUT_SIZE = (224, 224)


async def _load_model(model_path: str | Path | None = None):
    """Lazy-load the Siamese model."""
    global _model, _fallback_encoder, _device
    if _model is not None or _fallback_encoder is not None:
        return

    async with _lock:
        if _model is not None or _fallback_encoder is not None:
            return

        import torch
        import torch.nn as nn
        from torchvision import models

        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("loading_siamese_model", device=str(_device))

        selected_path = (
            str(model_path)
            if model_path
            else await get_active_model_weights(
                "VERIFICATION",
                str(DEFAULT_MODEL_PATH),
                virtual_prefixes=("torchvision:",),
            )
        )
        configured_path = Path(selected_path) if not selected_path.startswith("torchvision:") else DEFAULT_MODEL_PATH

        class SiameseNetwork(nn.Module):
            """Twin-branch network with shared ResNet-18 encoder."""

            def __init__(self):
                super().__init__()
                backbone = models.resnet18(weights=None)
                self.encoder = nn.Sequential(*list(backbone.children())[:-1])
                self.fc = nn.Sequential(
                    nn.Linear(512, 256),
                    nn.ReLU(inplace=True),
                    nn.Linear(256, 1),
                    nn.Sigmoid(),
                )

            def forward_one(self, x):
                return self.encoder(x).flatten(1)

            def forward(self, x1, x2):
                e1 = self.forward_one(x1)
                e2 = self.forward_one(x2)
                diff = torch.abs(e1 - e2)
                return self.fc(diff)

        candidate_paths = [
            configured_path,
            Path("/models/siamese_resnet18_repair.pt"),
            Path("/app/ml/siamese_resnet18_repair.pt"),
        ]

        loaded_custom = False
        for path in candidate_paths:
            if not path.exists():
                continue
            try:
                _model = SiameseNetwork()
                state = torch.load(str(path), map_location=_device)
                _model.load_state_dict(state, strict=False)
                logger.info("siamese_weights_loaded", path=str(path))
                _model.to(_device)
                _model.eval()
                loaded_custom = True
                break
            except Exception as exc:
                logger.warning(
                    "siamese_weights_load_failed",
                    path=str(path),
                    error=str(exc),
                )

        if not loaded_custom:
            logger.warning("siamese_no_weights_using_pretrained_resnet", path=str(configured_path))
            try:
                backbone = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
                _fallback_encoder = nn.Sequential(*list(backbone.children())[:-1])
                _fallback_encoder.to(_device)
                _fallback_encoder.eval()
            except Exception as exc:
                logger.warning("siamese_pretrained_resnet_unavailable", error=str(exc))
                _fallback_encoder = nn.Sequential(*list(models.resnet18(weights=None).children())[:-1])
                _fallback_encoder.to(_device)
                _fallback_encoder.eval()


def _preprocess(image: np.ndarray) -> "torch.Tensor":
    """Preprocess a BGR image for model input."""
    import cv2
    import torch
    from torchvision import transforms

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, INPUT_SIZE)

    transform = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],
        ),
    ])
    return transform(rgb).unsqueeze(0)


async def compare(
    before: np.ndarray,
    after: np.ndarray,
    model_path: str | Path | None = None,
) -> dict:
    """Compare before/after images and return repair similarity.

    Args:
        before: BGR image of pothole before repair.
        after: BGR image of same location after repair.
        model_path: Optional custom model weights.

    Returns:
        Dictionary with:
            similarity: float (0-1, higher = more similar / more repaired)
            repair_status: "Repaired" | "Partially_Repaired" | "Not_Repaired"
    """
    import torch

    await _load_model(model_path)

    t_before = _preprocess(before).to(_device)
    t_after = _preprocess(after).to(_device)

    loop = asyncio.get_event_loop()

    def _infer():
        with torch.no_grad():
            if _model is not None:
                return _model(t_before, t_after).item()

            emb_before = _fallback_encoder(t_before).flatten(1)
            emb_after = _fallback_encoder(t_after).flatten(1)
            cos = torch.nn.functional.cosine_similarity(emb_before, emb_after).item()
            return (cos + 1.0) / 2.0

    # The Siamese network outputs similarity where:
    # 1.0 = identical (repaired — after looks like good road)
    # 0.0 = completely different (still damaged)
    # We train with: positive pairs = (pothole, repaired_road)
    similarity = await loop.run_in_executor(None, _infer)

    if similarity >= REPAIRED_THRESHOLD:
        status = "Repaired"
    elif similarity >= PARTIAL_THRESHOLD:
        status = "Partially_Repaired"
    else:
        status = "Not_Repaired"

    logger.info(
        "siamese_comparison",
        similarity=round(similarity, 4),
        status=status,
    )

    return {
        "similarity": round(float(similarity), 4),
        "repair_status": status,
    }
