"""Decision engine for detection pipeline.

Combines YOLO confidence, source reliability, geometric severity features,
and policy thresholds into a single action:
- AUTO_FILE_COMPLAINT
- FLAG_FOR_REVIEW
- MONITOR
"""

from __future__ import annotations

from typing import Any

from app.config import settings


SOURCE_MULTIPLIERS: dict[str, float] = {
    "DRONE": 1.25,
    "OAM_DRONE": 1.20,
    "CCTV": 1.15,
    "RISAT-2B": 1.18,
    "EOS-04": 1.20,
    "SENTINEL-1": 1.05,
    "ALOS-2": 1.10,
    "CARTOSAT-3": 1.25,
    "CARTOSAT-2S": 1.20,
    "SENTINEL-2": 0.95,
    "LANDSAT-9": 0.90,
    "LANDSAT-8": 0.90,
    "MODIS": 0.70,
    "RESOURCESAT-2A": 0.78,
}


SOURCE_ALIASES: dict[str, str] = {
    "OAM": "OAM_DRONE",
    "OPENAERIALMAP": "OAM_DRONE",
    "OPEN_AERIAL_MAP": "OAM_DRONE",
    "CARTOSAT3": "CARTOSAT-3",
    "CARTOSAT2S": "CARTOSAT-2S",
    "LANDSAT9": "LANDSAT-9",
    "LANDSAT8": "LANDSAT-8",
    "SENTINEL1": "SENTINEL-1",
    "SENTINEL2": "SENTINEL-2",
    "ALOS2": "ALOS-2",
    "EOS04": "EOS-04",
    "RISAT2B": "RISAT-2B",
    "RESOURCESAT2A": "RESOURCESAT-2A",
}

SEVERITY_RISK_BASE = {
    "Low": 20.0,
    "Medium": 45.0,
    "High": 70.0,
    "Critical": 90.0,
}


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, value))


def normalize_source_type(source_type: str) -> str:
    raw = (source_type or "").strip().upper().replace("_", "-")
    key = raw.replace("-", "")
    if key in SOURCE_ALIASES:
        return SOURCE_ALIASES[key]
    if raw in SOURCE_ALIASES:
        return SOURCE_ALIASES[raw]
    return raw or "UNKNOWN"


def _depth_boost(depth_cm: float) -> float:
    if depth_cm >= 15:
        return 0.18
    if depth_cm >= 7:
        return 0.10
    if depth_cm >= 3:
        return 0.05
    return 0.0


def _area_boost(area_m2: float) -> float:
    if area_m2 >= 0.40:
        return 0.12
    if area_m2 >= 0.15:
        return 0.08
    if area_m2 >= 0.05:
        return 0.04
    return 0.0


def decide_detection_action(
    *,
    yolo_confidence: float,
    source_type: str,
    area_m2: float,
    depth_cm: float,
    severity: str,
) -> dict[str, Any]:
    """Fuse confidence + context and return action and risk score."""
    base = _clip01(float(yolo_confidence or 0.0))
    normalized_source = normalize_source_type(source_type)
    source_weight = SOURCE_MULTIPLIERS.get(normalized_source, 1.0)

    fused = base * source_weight
    fused += _depth_boost(float(depth_cm or 0.0))
    fused += _area_boost(float(area_m2 or 0.0))
    fused = _clip01(fused)

    auto_thr = float(settings.AUTO_FILE_THRESHOLD)
    review_thr = float(settings.REVIEW_THRESHOLD)

    if fused >= auto_thr:
        action = "AUTO_FILE_COMPLAINT"
    elif fused >= review_thr:
        action = "FLAG_FOR_REVIEW"
    else:
        action = "MONITOR"

    base_risk = float(SEVERITY_RISK_BASE.get(severity, 30.0))
    confidence_risk_boost = 10.0 * fused
    depth_risk_boost = min(float(depth_cm or 0.0), 20.0)
    risk_score = min(100.0, round(base_risk + confidence_risk_boost + depth_risk_boost, 2))

    return {
        "action": action,
        "fused_confidence": round(fused, 3),
        "risk_score": risk_score,
        "risk_score_10": round(risk_score / 10.0, 2),
        "thresholds": {
            "auto_file": auto_thr,
            "review": review_thr,
        },
        "normalized_source": normalized_source,
        "source_multiplier": source_weight,
        "decision_reason": (
            f"fused_confidence={round(fused, 3)}; "
            f"thresholds(auto={auto_thr}, review={review_thr}); "
            f"source={normalized_source} x{source_weight}"
        ),
    }
