"""YOLOv8x-seg pothole detector wrapper.

Loads the model once and exposes a `detect()` coroutine that returns
bounding boxes, segmentation masks, and confidence scores.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)

# Lazy singleton
_model = None
_lock = asyncio.Lock()

DEFAULT_MODEL_PATH = Path("/models/yolov8x-seg-pothole.pt")
CONFIDENCE_THRESHOLD = 0.55
IOU_THRESHOLD = 0.45
IMG_SIZE = 1024


async def _get_model(model_path: str | Path | None = None):
    """Thread-safe lazy loading of YOLOv8 model."""
    global _model
    if _model is not None:
        return _model

    async with _lock:
        if _model is not None:
            return _model

        from ultralytics import YOLO

        path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
        if path.exists():
            logger.info("loading_yolo_model", path=str(path))
            _model = YOLO(str(path))
        else:
            fallback_model = "yolov8n-seg.pt"
            logger.warning(
                "yolo_model_not_found_using_fallback",
                missing_path=str(path),
                fallback=fallback_model,
            )
            _model = YOLO(fallback_model)
        return _model


async def detect(
    image: np.ndarray,
    *,
    model_path: str | Path | None = None,
    confidence: float = CONFIDENCE_THRESHOLD,
    iou: float = IOU_THRESHOLD,
    img_size: int = IMG_SIZE,
) -> list[dict[str, Any]]:
    """Run pothole detection on a single image.

    Args:
        image: BGR numpy array (H, W, 3).
        model_path: Optional custom model path.
        confidence: Minimum confidence threshold.
        iou: NMS IoU threshold.
        img_size: Inference image size.

    Returns:
        List of detection dicts with keys:
            bbox: [x1, y1, x2, y2]
            confidence: float
            class_id: int
            class_name: str
            mask: np.ndarray (H, W) binary mask or None
            area_px: int (mask pixel count)
    """
    model = await _get_model(model_path)

    # Run inference in thread pool to avoid blocking event loop
    loop = asyncio.get_event_loop()
    results = await loop.run_in_executor(
        None,
        lambda: model.predict(
            image,
            conf=confidence,
            iou=iou,
            imgsz=img_size,
            verbose=False,
            retina_masks=True,
        ),
    )

    detections = []
    for result in results:
        boxes = result.boxes
        masks = result.masks

        for i in range(len(boxes)):
            box = boxes[i]
            det: dict[str, Any] = {
                "bbox": box.xyxy[0].cpu().numpy().tolist(),
                "confidence": float(box.conf[0].cpu()),
                "class_id": int(box.cls[0].cpu()),
                "class_name": result.names[int(box.cls[0].cpu())],
                "mask": None,
                "area_px": 0,
            }

            if masks is not None and i < len(masks):
                mask = masks[i].data[0].cpu().numpy().astype(np.uint8)
                det["mask"] = mask
                det["area_px"] = int(np.sum(mask > 0))

            detections.append(det)

    logger.info("yolo_detection", count=len(detections))
    return detections


async def detect_batch(
    images: list[np.ndarray],
    **kwargs,
) -> list[list[dict[str, Any]]]:
    """Run detection on a batch of images."""
    results = []
    for img in images:
        dets = await detect(img, **kwargs)
        results.append(dets)
    return results


def estimate_diameter_from_mask(
    mask: np.ndarray, gsd_m_per_px: float
) -> float:
    """Estimate pothole diameter in meters from binary mask and GSD.

    Args:
        mask: Binary mask (H, W).
        gsd_m_per_px: Ground sampling distance in meters/pixel.

    Returns:
        Estimated diameter in meters.
    """
    area_px = int(np.sum(mask > 0))
    radius_px = np.sqrt(area_px / np.pi)
    diameter_m = 2 * radius_px * gsd_m_per_px
    return round(float(diameter_m), 3)
