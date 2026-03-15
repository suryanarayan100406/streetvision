"""Risk Score Engine — computes 0-10 risk score from severity, accidents, traffic, geometry, weather."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.pothole import Pothole
from app.models.weather import WeatherCache
from app.services.weather_service import should_apply_rain_flag
logger = structlog.get_logger(__name__)
_road_accidents_has_geom: bool | None = None

SEVERITY_SCORES = {"Critical": 4.0, "High": 3.0, "Medium": 2.0, "Low": 1.0}
TRAFFIC_SCORES = {"High": 2.0, "Medium": 1.2, "Low": 0.5}


async def _road_accidents_supports_geom(db: AsyncSession) -> bool:
    global _road_accidents_has_geom
    if _road_accidents_has_geom is not None:
        return _road_accidents_has_geom

    schema_result = await db.execute(
        text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'road_accidents'
                  AND column_name = 'geom'
            )
            """
        )
    )
    _road_accidents_has_geom = bool(schema_result.scalar())
    return _road_accidents_has_geom


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
    road_accidents_has_geom = await _road_accidents_supports_geom(db)
    if road_accidents_has_geom:
        accident_result = await db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM road_accidents
                WHERE ST_DWithin(
                    geom,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                    0.02
                )
                """
            ),
            {"lon": float(pothole.longitude), "lat": float(pothole.latitude)},
        )
        accident_count = accident_result.scalar() or 0
        accident_raw = min(accident_count / 3.0, 4.0)
    else:
        district_name = (pothole.district or "").strip()
        if district_name:
            accident_result = await db.execute(
                text(
                    """
                    SELECT COALESCE(SUM(total_accidents), 0)
                    FROM road_accidents
                    WHERE lower(district) = lower(:district)
                    """
                ),
                {"district": district_name},
            )
            district_accidents = int(accident_result.scalar() or 0)
        else:
            district_accidents = 0
        accident_count = district_accidents
        accident_raw = min(district_accidents / 500.0, 4.0)
    accident_component = accident_raw * settings.RISK_ACCIDENT_WEIGHT

    # ─── Traffic Volume Component ──────────────────────────────
    segment_result = await db.execute(
        text(
            """
            SELECT nh_number, chainage_km, aadt, is_curve, is_blind_spot, is_junction, thermal_stress_zone
            FROM road_segments
            WHERE ST_DWithin(
                geom,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                0.001
            )
            ORDER BY ST_Distance(
                geom,
                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
            )
            LIMIT 1
            """
        ),
        {"lon": float(pothole.longitude), "lat": float(pothole.latitude)},
    )
    segment = segment_result.mappings().first()
    segment_aadt = int(segment["aadt"] or 0) if segment else 0
    if segment_aadt >= 15000:
        traffic_category = "High"
    elif segment_aadt >= 5000:
        traffic_category = "Medium"
    else:
        traffic_category = "Low"
    traffic_raw = TRAFFIC_SCORES.get(traffic_category, 0.5)
    traffic_component = traffic_raw * settings.RISK_TRAFFIC_WEIGHT

    # ─── Road Geometry Component ───────────────────────────────
    geometry_raw = 0.0
    if segment:
        if segment["is_curve"] or segment["is_blind_spot"]:
            geometry_raw += 1.5
        if segment["is_junction"]:
            geometry_raw += 0.2
        if segment["thermal_stress_zone"]:
            geometry_raw += 0.15
    geometry_component = geometry_raw * settings.RISK_GEOMETRY_WEIGHT

    base_score = severity_component + accident_component + traffic_component + geometry_component
    base_score = min(base_score, 10.0)

    # ─── Weather Boost ─────────────────────────────────────────
    weather_boost = bool(
        pothole.rain_flag
        or pothole.moisture_flag
        or pothole.thermal_stress_flag
    )

    if not weather_boost:
        weather_row_result = await db.execute(
            select(WeatherCache)
            .where(WeatherCache.forecast_date >= (date.today() - timedelta(days=1)))
            .order_by(WeatherCache.checked_at.desc())
            .limit(1)
        )
        weather_row = weather_row_result.scalar_one_or_none()
        if weather_row is not None:
            rain_signal = should_apply_rain_flag(
                weather_row.imd_warning_level,
                float(weather_row.open_meteo_rain_48h_mm or 0.0),
                float(weather_row.gfs_rain_7d_mm or 0.0),
            )
            if rain_signal:
                pothole.rain_flag = True
                weather_boost = True

    final_score_10 = base_score * settings.WEATHER_BOOST_MULTIPLIER if weather_boost else base_score
    final_score_10 = min(final_score_10, 10.0)
    final_score = round(final_score_10 * 10.0, 2)

    if hasattr(pothole, "base_risk_score"):
        pothole.base_risk_score = Decimal(str(round(base_score * 10.0, 2)))
    pothole.risk_score = float(final_score)
    await db.flush()

    await logger.ainfo(
        "risk_score_computed",
        pothole_id=pothole_id,
        base=round(base_score * 10.0, 2),
        boosted=weather_boost,
        final=round(final_score, 2),
        accident_count=accident_count,
    )
    return Decimal(str(pothole.risk_score or 0))


def get_urgency_language(risk_score: float) -> str:
    if risk_score >= 80.0:
        return "demands immediate emergency intervention"
    elif risk_score >= 50.0:
        return "requires urgent attention within 7 days"
    return "requests scheduled remediation within 30 days"
