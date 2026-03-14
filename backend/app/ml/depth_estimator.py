"""MiDaS v3 DPT_Large monocular depth estimator.

Estimates relative depth from a single image, used to approximate
pothole depth when stereo / LiDAR is unavailable.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import numpy as np
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

_model = None
_transform = None
_device = None
_lock = asyncio.Lock()


async def _load_model():
    """Lazy-load MiDaS DPT_Large once."""
    global _model, _transform, _device
    if _model is not None:
        return

    async with _lock:
        if _model is not None:
            return

        import os
        import torch

        _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("loading_midas", device=str(_device))

        # Ensure hub cache directory exists before parallel workers race to create it
        hub_dir = torch.hub.get_dir()
        os.makedirs(hub_dir, exist_ok=True)

        _model = torch.hub.load("intel-isl/MiDaS", "DPT_Large", trust_repo=True)

        # Prefer fine-tuned checkpoint if present
        configured_path = Path(settings.MIDAS_MODEL_PATH)
        candidate_paths = [
            configured_path,
            Path("/models/midas_dpt_large_pothole_finetuned.pt"),
            Path("/app/ml/midas_dpt_large_pothole_finetuned.pt"),
        ]

        loaded_custom = False
        for checkpoint_path in candidate_paths:
            if not checkpoint_path.exists():
                continue
            try:
                state_dict = torch.load(
                    checkpoint_path,
                    map_location=_device,
                )
                _model.load_state_dict(state_dict, strict=False)
                logger.info(
                    "loaded_custom_midas_checkpoint",
                    path=str(checkpoint_path),
                )
                loaded_custom = True
                break
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "failed_loading_custom_midas_checkpoint",
                    path=str(checkpoint_path),
                    error=str(exc),
                )

        if not loaded_custom:
            logger.warning(
                "custom_midas_checkpoint_not_found_using_pretrained",
                configured_path=str(configured_path),
            )

        _model.to(_device)
        _model.eval()

        # Ensure hub cache dir exists for transforms too
        midas_transforms = torch.hub.load(
            "intel-isl/MiDaS", "transforms", trust_repo=True
        )
        _transform = midas_transforms.dpt_transform


async def estimate_depth(
    image: np.ndarray,
    mask: np.ndarray | None = None,
) -> dict:
    """Estimate depth from a single BGR image.

    Args:
        image: BGR numpy array (H, W, 3).
        mask: Optional binary mask to restrict depth to ROI.

    Returns:
        Dictionary with:
            depth_map: np.ndarray (H, W) relative depth values.
            mean_depth: float — mean depth within mask or whole image.
            max_depth: float — max depth within mask or whole image.
            estimated_depth_cm: float — rough cm estimate (calibrated for potholes).
    """
    import torch
    import cv2

    await _load_model()

    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    loop = asyncio.get_event_loop()

    def _infer():
        input_batch = _transform(rgb).to(_device)
        with torch.no_grad():
            prediction = _model(input_batch)
        prediction = torch.nn.functional.interpolate(
            prediction.unsqueeze(1),
            size=rgb.shape[:2],
            mode="bicubic",
            align_corners=False,
        ).squeeze()
        return prediction.cpu().numpy()

    depth_map = await loop.run_in_executor(None, _infer)

    # Apply mask if provided
    if mask is not None:
        resized_mask = cv2.resize(
            mask.astype(np.uint8), (depth_map.shape[1], depth_map.shape[0])
        )
        roi_depths = depth_map[resized_mask > 0]
    else:
        roi_depths = depth_map.flatten()

    if len(roi_depths) == 0:
        return {
            "depth_map": depth_map,
            "mean_depth": 0.0,
            "max_depth": 0.0,
            "estimated_depth_cm": 0.0,
        }

    mean_depth = float(np.mean(roi_depths))
    max_depth = float(np.max(roi_depths))

    # Rough calibration: MiDaS relative depth → cm
    # Based on typical highway pothole depths (2-30 cm)
    # Calibration factor derived from ground truth dataset
    CALIBRATION_FACTOR = 0.15  # tune per deployment
    estimated_cm = round(max_depth * CALIBRATION_FACTOR, 2)
    estimated_cm = min(estimated_cm, 50.0)  # cap at 50cm

    return {
        "depth_map": depth_map,
        "mean_depth": round(mean_depth, 4),
        "max_depth": round(max_depth, 4),
        "estimated_depth_cm": estimated_cm,
    }
