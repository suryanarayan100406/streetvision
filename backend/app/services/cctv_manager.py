"""CCTV camera management service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import cv2
import numpy as np
import structlog
from skimage.metrics import structural_similarity

from app.config import settings

logger = structlog.get_logger(__name__)


def test_rtsp_connection(rtsp_url: str, timeout_seconds: int = 10) -> dict[str, Any]:
    """Test RTSP connection and capture a single frame."""
    cap = cv2.VideoCapture(rtsp_url)
    cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, timeout_seconds * 1000)

    if not cap.isOpened():
        return {"success": False, "error": "Failed to open RTSP stream"}

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        return {"success": False, "error": "Failed to capture frame"}

    # Encode thumbnail
    _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return {"success": True, "frame_captured": True, "thumbnail": buffer.tobytes()}


def compute_homography(
    image_points: list[list[float]],
    real_width_m: float = 3.5,
    real_length_m: float = 5.0,
) -> np.ndarray:
    """Compute perspective transform from 4 image points to road surface plane."""
    src_pts = np.float32(image_points)
    # Map to a 640x640 top-down view
    dst_pts = np.float32([
        [0, 0],
        [640, 0],
        [640, 640],
        [0, 640],
    ])
    matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
    return matrix


def apply_perspective_correction(frame: np.ndarray, matrix: np.ndarray, size: int = 640) -> np.ndarray:
    """Apply homography matrix to produce top-down road surface view."""
    corrected = cv2.warpPerspective(frame, np.array(matrix), (size, size))
    return corrected


def check_frame_similarity(frame1: np.ndarray, frame2: np.ndarray, threshold: float = 0.98) -> bool:
    """Check if two frames are too similar (SSIM > threshold). Returns True if should skip."""
    gray1 = cv2.cvtColor(cv2.resize(frame1, (256, 256)), cv2.COLOR_BGR2GRAY)
    gray2 = cv2.cvtColor(cv2.resize(frame2, (256, 256)), cv2.COLOR_BGR2GRAY)
    score = structural_similarity(gray1, gray2)
    return score > threshold


def capture_and_process_frame(
    rtsp_url: str,
    perspective_matrix: list[list[float]] | None = None,
    tile_size: int = 640,
) -> dict[str, Any] | None:
    """Capture one frame from CCTV, apply perspective correction, return processed tile."""
    cap = cv2.VideoCapture(rtsp_url)
    if not cap.isOpened():
        return None

    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return None

    if perspective_matrix:
        matrix = np.array(perspective_matrix, dtype=np.float32)
        frame = apply_perspective_correction(frame, matrix, tile_size)
    else:
        frame = cv2.resize(frame, (tile_size, tile_size))

    return {"frame": frame, "timestamp": datetime.now(timezone.utc).isoformat()}
