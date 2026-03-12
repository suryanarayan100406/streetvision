"""Confidence Fusion Engine — recomputes pothole confidence from all source multipliers."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pothole import Pothole
from app.models.source_report import SourceReport

logger = structlog.get_logger(__name__)

# Source multipliers (multiplicative)
SOURCE_MULTIPLIERS: dict[str, float] = {
    "DRONE_SUB01": 1.85,         # < 0.1 m/px
    "CARTOSAT-3": 1.80,
    "DRONE_01_05": 1.70,         # 0.1-0.5 m/px
    "CARTOSAT-2S": 1.70,
    "OAM_DRONE": 1.70,
    "RISAT-2B": 1.65,
    "CCTV": 1.60,
    "RESOURCESAT-2A": 1.55,
    "MOBILE_VISUAL": 1.50,
    "DRONE_05_10": 1.45,         # 0.5-1.0 m/px
    "MAPILLARY": 1.30,
    "KARTAVIEW": 1.30,
    "EOS-04": 1.25,
    "ALOS-2": 1.25,
    "MOBILE_POCKET_CLUSTER": 1.20,
    "LANDSAT-9": 1.15,
    "SENTINEL-1": 1.15,
    "MODIS": 1.10,
    "OSM_NOTE": 1.05,
}


async def recompute_confidence(db: AsyncSession, pothole_id: int) -> Decimal:
    """Recompute confidence_score for a pothole using all corroborating source reports."""
    pothole_result = await db.execute(select(Pothole).where(Pothole.id == pothole_id))
    pothole = pothole_result.scalar_one_or_none()
    if pothole is None:
        return Decimal("0")

    # Get all source reports within 50m and 3 days
    reports_result = await db.execute(
        select(SourceReport).where(SourceReport.pothole_id == pothole_id)
    )
    reports = reports_result.scalars().all()

    # Base confidence is from the detection metadata or default
    base_conf = float(pothole.confidence_score or Decimal("0.6"))

    # Collect unique source types
    seen_sources: set[str] = set()
    fused = base_conf

    for report in reports:
        source = report.source
        if source in seen_sources:
            continue
        seen_sources.add(source)

        multiplier = SOURCE_MULTIPLIERS.get(source, 1.0)
        if multiplier > 1.0:
            fused *= multiplier

    # Cap at 1.0
    fused = min(fused, 1.0)
    final_score = Decimal(str(round(fused, 3)))

    pothole.confidence_score = final_score
    await db.flush()

    await logger.ainfo(
        "confidence_recomputed",
        pothole_id=pothole_id,
        base=base_conf,
        sources=list(seen_sources),
        final=float(final_score),
    )
    return final_score


def determine_action(confidence: Decimal, auto_threshold: float = 0.85, review_threshold: float = 0.65) -> str:
    """Determine the action based on confidence thresholds."""
    c = float(confidence)
    if c >= auto_threshold:
        return "AUTO_FILE_COMPLAINT"
    elif c >= review_threshold:
        return "FLAG_FOR_REVIEW"
    return "MONITOR"
