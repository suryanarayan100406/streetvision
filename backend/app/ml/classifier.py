"""Severity classifier for detected potholes.

Combines detection area, estimated depth, and mask shape features
to classify severity as Low / Medium / High / Critical.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

import numpy as np
import structlog

logger = structlog.get_logger(__name__)


class Severity(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


# Thresholds (derived from CG highway pothole dataset)
AREA_THRESHOLDS = {
    "small": 0.05,      # < 0.05 m²
    "medium": 0.15,     # 0.05 – 0.15 m²
    "large": 0.40,      # 0.15 – 0.40 m²
    # >= 0.40 m² → critical area
}

DEPTH_THRESHOLDS = {
    "shallow": 3.0,     # < 3 cm
    "medium": 7.0,      # 3 – 7 cm
    "deep": 15.0,       # 7 – 15 cm
    # >= 15 cm → critical depth
}


def classify_severity(
    area_m2: float,
    depth_cm: float,
    confidence: float = 1.0,
    near_junction: bool = False,
    on_curve: bool = False,
    aadt: int = 0,
) -> dict[str, Any]:
    """Classify pothole severity from measured attributes.

    Args:
        area_m2: Estimated surface area in square meters.
        depth_cm: Estimated depth in centimeters.
        confidence: Detection confidence (0-1).
        near_junction: Whether pothole is near a road junction.
        on_curve: Whether pothole is on a curve.
        aadt: Annual average daily traffic count.

    Returns:
        Dictionary with severity, score, and reasoning.
    """
    # Base scoring
    area_score = _score_area(area_m2)
    depth_score = _score_depth(depth_cm)

    # Weighted combination (depth is more dangerous than area)
    base_score = area_score * 0.4 + depth_score * 0.6

    # Context multipliers
    multiplier = 1.0
    reasons = []

    if near_junction:
        multiplier += 0.15
        reasons.append("near junction (+15%)")

    if on_curve:
        multiplier += 0.20
        reasons.append("on curve (+20%)")

    if aadt > 20000:
        multiplier += 0.15
        reasons.append(f"high traffic AADT={aadt} (+15%)")
    elif aadt > 10000:
        multiplier += 0.08
        reasons.append(f"moderate traffic AADT={aadt} (+8%)")

    final_score = min(base_score * multiplier, 10.0)

    severity = _score_to_severity(final_score)

    return {
        "severity": severity.value,
        "score": round(final_score, 2),
        "area_score": round(area_score, 2),
        "depth_score": round(depth_score, 2),
        "multiplier": round(multiplier, 2),
        "reasons": reasons,
        "area_m2": round(area_m2, 4),
        "depth_cm": round(depth_cm, 2),
    }


def _score_area(area_m2: float) -> float:
    """Map area to 0-10 score."""
    if area_m2 < AREA_THRESHOLDS["small"]:
        return area_m2 / AREA_THRESHOLDS["small"] * 2.5
    elif area_m2 < AREA_THRESHOLDS["medium"]:
        return 2.5 + (area_m2 - AREA_THRESHOLDS["small"]) / (
            AREA_THRESHOLDS["medium"] - AREA_THRESHOLDS["small"]
        ) * 2.5
    elif area_m2 < AREA_THRESHOLDS["large"]:
        return 5.0 + (area_m2 - AREA_THRESHOLDS["medium"]) / (
            AREA_THRESHOLDS["large"] - AREA_THRESHOLDS["medium"]
        ) * 2.5
    else:
        return min(7.5 + (area_m2 - AREA_THRESHOLDS["large"]) / 0.4 * 2.5, 10.0)


def _score_depth(depth_cm: float) -> float:
    """Map depth to 0-10 score."""
    if depth_cm < DEPTH_THRESHOLDS["shallow"]:
        return depth_cm / DEPTH_THRESHOLDS["shallow"] * 2.5
    elif depth_cm < DEPTH_THRESHOLDS["medium"]:
        return 2.5 + (depth_cm - DEPTH_THRESHOLDS["shallow"]) / (
            DEPTH_THRESHOLDS["medium"] - DEPTH_THRESHOLDS["shallow"]
        ) * 2.5
    elif depth_cm < DEPTH_THRESHOLDS["deep"]:
        return 5.0 + (depth_cm - DEPTH_THRESHOLDS["medium"]) / (
            DEPTH_THRESHOLDS["deep"] - DEPTH_THRESHOLDS["medium"]
        ) * 2.5
    else:
        return min(7.5 + (depth_cm - DEPTH_THRESHOLDS["deep"]) / 15.0 * 2.5, 10.0)


def _score_to_severity(score: float) -> Severity:
    """Map numerical score to severity enum."""
    if score < 2.5:
        return Severity.LOW
    elif score < 5.0:
        return Severity.MEDIUM
    elif score < 7.5:
        return Severity.HIGH
    else:
        return Severity.CRITICAL


def classify_from_detection(
    detection: dict[str, Any],
    gsd_m_per_px: float,
    depth_cm: float,
    **context,
) -> dict[str, Any]:
    """Convenience: classify directly from detector output.

    Args:
        detection: Output from detector.detect().
        gsd_m_per_px: Ground sampling distance.
        depth_cm: From depth_estimator.
        **context: near_junction, on_curve, aadt, etc.
    """
    mask = detection.get("mask")
    if mask is not None:
        area_px = int(np.sum(mask > 0))
        area_m2 = area_px * (gsd_m_per_px ** 2)
    else:
        # Fallback: estimate from bbox
        bbox = detection["bbox"]
        w_px = bbox[2] - bbox[0]
        h_px = bbox[3] - bbox[1]
        area_m2 = w_px * h_px * (gsd_m_per_px ** 2) * 0.7  # ellipse approx

    return classify_severity(
        area_m2=area_m2,
        depth_cm=depth_cm,
        confidence=detection.get("confidence", 1.0),
        **context,
    )
