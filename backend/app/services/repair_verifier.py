"""Repair verification service — Siamese CNN + SSIM."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import numpy as np
import structlog
from skimage.metrics import structural_similarity

logger = structlog.get_logger(__name__)


async def compute_ssim(before_img: np.ndarray, after_img: np.ndarray) -> float:
    """Compute SSIM between before and after 224x224 patches."""
    import cv2

    before_gray = cv2.cvtColor(cv2.resize(before_img, (224, 224)), cv2.COLOR_BGR2GRAY)
    after_gray = cv2.cvtColor(cv2.resize(after_img, (224, 224)), cv2.COLOR_BGR2GRAY)
    score = structural_similarity(before_gray, after_gray)
    return round(float(score), 4)


def classify_repair_ssim(ssim_score: float) -> str:
    """Classify repair status from SSIM score."""
    if ssim_score >= 0.85:
        return "Repaired"
    elif ssim_score >= 0.60:
        return "Partially_Repaired"
    return "Unresolved"


async def verify_with_siamese(before_img: np.ndarray, after_img: np.ndarray, model_path: str) -> dict[str, Any]:
    """Run Siamese CNN repair verification. Takes precedence over SSIM when results conflict."""
    import torch
    import torchvision.transforms as T

    transform = T.Compose([
        T.ToPILImage(),
        T.Resize((224, 224)),
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    before_tensor = transform(before_img).unsqueeze(0)
    after_tensor = transform(after_img).unsqueeze(0)

    # Load Siamese model
    model = torch.jit.load(model_path, map_location="cpu")
    model.eval()

    with torch.no_grad():
        output = model(before_tensor, after_tensor)
        probs = torch.softmax(output, dim=1)
        pred_class = torch.argmax(probs, dim=1).item()
        confidence = probs[0, pred_class].item()

    class_map = {0: "Repaired", 1: "Partially_Repaired", 2: "Unresolved"}
    return {
        "repair_status": class_map.get(pred_class, "Unresolved"),
        "siamese_score": round(confidence, 4),
    }


async def verify_repair(
    before_path: str,
    after_path: str,
    siamese_model_path: str | None = None,
) -> dict[str, Any]:
    """Full repair verification pipeline: SSIM + optional Siamese CNN."""
    import cv2
    from app.services.minio_client import download_bytes

    before_data = download_bytes(before_path)
    after_data = download_bytes(after_path)
    before_img = cv2.imdecode(np.frombuffer(before_data, np.uint8), cv2.IMREAD_COLOR)
    after_img = cv2.imdecode(np.frombuffer(after_data, np.uint8), cv2.IMREAD_COLOR)

    ssim_score = await compute_ssim(before_img, after_img)
    ssim_status = classify_repair_ssim(ssim_score)

    result: dict[str, Any] = {
        "ssim_score": ssim_score,
        "ssim_status": ssim_status,
        "repair_status": ssim_status,
    }

    # Siamese CNN takes precedence when an actual weight file is available.
    if siamese_model_path and not str(siamese_model_path).startswith("torchvision:"):
        try:
            siamese_result = await verify_with_siamese(before_img, after_img, siamese_model_path)
            result["siamese_score"] = siamese_result["siamese_score"]
            result["siamese_status"] = siamese_result["repair_status"]
            result["repair_status"] = siamese_result["repair_status"]  # Siamese wins
        except Exception as exc:
            await logger.aexception("siamese_verification_failed", error=str(exc))

    return result
