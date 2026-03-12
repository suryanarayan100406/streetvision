"""Risk Score Engine — computes 0-10 risk score from severity, accidents, traffic, geometry, weather."""

from __future__ import annotations

from decimal import Decimal

import structlog
from geoalchemy2 import func as geo_func
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.pothole import Pothole
from app.models.road import RoadAccident, RoadSegment
from app.models.weather import WeatherCache

logger = structlog.get_logger(__name__)

SEVERITY_SCORES = {"Critical": 4.0, "High": 3.0, "Medium": 2.0, "Low": 1.0}
TRAFFIC_SCORES = {"High": 2.0, "Medium": 1.2, "Low": 0.5}


async def compute_risk_score(db: AsyncSession, pothole_id: int) -> Decimal:
    """Recompute full risk score for a pothole."""
    result = await db.execute(select(Pothole).where(Pothole.id == pothole_id))
    pothole = result.scalar_one_or_none()
    if pothole is None:
        return Decimal("0")

    # ─── Severity Component ────────────────────────────────────
    severity_raw = SEVERITY_SCORES.get(pothole.severity or "Low", 1.0)
    severity_component = severity_raw * settings.RISK_SEVERITY_WEIGHT

    # ─── Accident History Component ────────────────────────────
    accident_result = await db.execute(
        select(func.count(RoadAccident.id)).where(
            func.ST_DWithin(
                func.ST_Geography(RoadAccident.geom),
                func.ST_Geography(pothole.geom),
                2000,  # 2000 metres
            )
        )
    )
    accident_count = accident_result.scalar() or 0
    accident_raw = min(accident_count / 3.0, 4.0)
    accident_component = accident_raw * settings.RISK_ACCIDENT_WEIGHT

    # ─── Traffic Volume Component ──────────────────────────────
    segment_result = await db.execute(
        select(RoadSegment).where(
            func.ST_DWithin(
                func.ST_Geography(RoadSegment.geom),
                func.ST_Geography(pothole.geom),
                100,
            )
        ).limit(1)
    )
    segment = segment_result.scalar_one_or_none()
    traffic_raw = TRAFFIC_SCORES.get(
        segment.traffic_volume_category if segment else "Low", 0.5
    )
    traffic_component = traffic_raw * settings.RISK_TRAFFIC_WEIGHT

    # ─── Road Geometry Component ───────────────────────────────
    geometry_raw = 0.0
    if segment:
        if segment.has_curves or segment.is_blind_spot:
            geometry_raw += 1.5
        if segment.slope_angle_degrees and float(segment.slope_angle_degrees) > 5.0:
            geometry_raw += 0.3
        if segment.junction_within_200m:
            geometry_raw += 0.2
        if segment.thermal_stress_flag:
            geometry_raw += 0.15
    geometry_component = geometry_raw * settings.RISK_GEOMETRY_WEIGHT

    base_score = severity_component + accident_component + traffic_component + geometry_component
    base_score = min(base_score, 10.0)

    # ─── Weather Boost ─────────────────────────────────────────
    weather_boost = False
    if pothole.rain_flag:
        weather_boost = True
    if pothole.imd_warning_level in ("Orange", "Red"):
        weather_boost = True
    if pothole.eos04_moisture_flag:
        weather_boost = True

    final_score = base_score * settings.WEATHER_BOOST_MULTIPLIER if weather_boost else base_score
    final_score = min(final_score, 10.0)

    pothole.base_risk_score = Decimal(str(round(base_score, 2)))
    pothole.risk_score = Decimal(str(round(final_score, 2)))
    await db.flush()

    await logger.ainfo(
        "risk_score_computed",
        pothole_id=pothole_id,
        base=round(base_score, 2),
        boosted=weather_boost,
        final=round(final_score, 2),
        accident_count=accident_count,
    )
    return pothole.risk_score


def get_urgency_language(risk_score: float) -> str:
    if risk_score >= 8.0:
        return "demands immediate emergency intervention"
    elif risk_score >= 5.0:
        return "requires urgent attention within 7 days"
    return "requests scheduled remediation within 30 days"
