"""Crowd consensus service for escalation and confidence adjustments."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.cctv import CCTVNode
from app.models.pothole import Pothole
from app.models.source_report import SourceReport

logger = structlog.get_logger(__name__)

CROWD_SOURCE_TYPES = {"crowd_visual", "crowd_vibration", "mobile_visual", "mobile_vibration"}


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_device_id(report: SourceReport) -> str:
    payload = report.raw_payload or {}
    return str(
        payload.get("device_id")
        or payload.get("user_id")
        or payload.get("display_name")
        or f"report-{report.id}"
    )


def _extract_z_axis_change(report: SourceReport) -> float | None:
    payload = report.raw_payload or {}
    candidates = [
        payload.get("z_axis_change"),
        payload.get("z_delta"),
        payload.get("z_delta_cm"),
        payload.get("z_score"),
        payload.get("peak_acceleration"),
        payload.get("vibration_peak"),
    ]
    for candidate in candidates:
        parsed = _safe_float(candidate)
        if parsed is not None:
            return parsed
    return None


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_m = 6371000.0
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    return 2 * radius_m * asin(sqrt(a))


def _bbox_for_point(lat: float, lon: float, radius_m: float) -> dict[str, float]:
    lat_delta = radius_m / 111320.0
    lon_delta = radius_m / (111320.0 * max(cos(radians(lat)), 0.2))
    return {
        "lat_min": lat - lat_delta,
        "lat_max": lat + lat_delta,
        "lon_min": lon - lon_delta,
        "lon_max": lon + lon_delta,
    }


def _elevate_severity(current: str | None) -> str:
    order = ["Low", "Medium", "High", "Critical"]
    if current not in order:
        return "High"
    idx = order.index(current)
    return order[min(idx + 1, len(order) - 1)]


async def _nearest_pothole(db: AsyncSession, lat: float, lon: float, radius_m: float) -> Pothole | None:
    pothole_rows = await db.execute(
        select(Pothole).where(
            Pothole.latitude.is_not(None),
            Pothole.longitude.is_not(None),
        )
    )
    nearest: Pothole | None = None
    nearest_dist = float("inf")
    for pothole in pothole_rows.scalars().all():
        distance = _haversine_m(lat, lon, float(pothole.latitude), float(pothole.longitude))
        if distance <= radius_m and distance < nearest_dist:
            nearest = pothole
            nearest_dist = distance
    return nearest


async def _nearest_cctv(db: AsyncSession, lat: float, lon: float, radius_m: float) -> CCTVNode | None:
    node_rows = await db.execute(
        select(CCTVNode).where(
            CCTVNode.is_active.is_(True),
            CCTVNode.latitude.is_not(None),
            CCTVNode.longitude.is_not(None),
        )
    )
    nearest: CCTVNode | None = None
    nearest_dist = float("inf")
    for node in node_rows.scalars().all():
        distance = _haversine_m(lat, lon, float(node.latitude), float(node.longitude))
        if distance <= radius_m and distance < nearest_dist:
            nearest = node
            nearest_dist = distance
    return nearest


async def apply_crowd_consensus(db: AsyncSession, report: SourceReport) -> dict[str, Any]:
    """Apply crowd consensus rules for escalation and confidence.

    Rules:
    - High z-axis shift from >=2 unique devices triggers satellite + nearest CCTV/drone analysis.
    - Reports from >10 unique devices increase pothole confidence.
    """
    if report.latitude is None or report.longitude is None:
        return {
            "consensus_devices": 0,
            "high_z_devices": 0,
            "escalation_triggered": False,
            "confidence_boost_applied": False,
        }

    now = datetime.now(timezone.utc)
    lookback_hours = int(settings.CROWD_LOOKBACK_HOURS)
    cluster_radius_m = float(settings.CROWD_CLUSTER_RADIUS_M)
    high_z_threshold = float(settings.CROWD_Z_AXIS_HIGH_THRESHOLD)

    result = await db.execute(
        select(SourceReport).where(
            SourceReport.source_type.in_(list(CROWD_SOURCE_TYPES)),
            SourceReport.created_at >= now - timedelta(hours=lookback_hours),
            SourceReport.latitude.is_not(None),
            SourceReport.longitude.is_not(None),
        )
    )
    candidates = result.scalars().all()

    center_lat = float(report.latitude)
    center_lon = float(report.longitude)

    cluster: list[SourceReport] = []
    for item in candidates:
        dist = _haversine_m(center_lat, center_lon, float(item.latitude), float(item.longitude))
        if dist <= cluster_radius_m:
            cluster.append(item)

    device_ids = {_extract_device_id(item) for item in cluster}
    high_z_devices = {
        _extract_device_id(item)
        for item in cluster
        if (_extract_z_axis_change(item) or 0.0) >= high_z_threshold
    }

    pothole = await _nearest_pothole(db, center_lat, center_lon, cluster_radius_m)
    if pothole is None and high_z_devices:
        pothole = Pothole(
            latitude=center_lat,
            longitude=center_lon,
            geom=f"SRID=4326;POINT({center_lon} {center_lat})",
            severity="High",
            confidence_score=0.62,
            risk_score=68.0,
            status="Detected",
            detected_at=now,
            estimated_depth_cm=max(high_z_threshold, 0.0),
            image_path=report.image_url,
        )
        db.add(pothole)
        await db.flush()

    if pothole is not None:
        report.pothole_id = pothole.id

    escalation_triggered = len(high_z_devices) >= int(settings.CROWD_CONSENSUS_MIN_DEVICES)
    confidence_boost_applied = False
    trigger_summary: dict[str, Any] = {
        "consensus_devices": len(device_ids),
        "high_z_devices": len(high_z_devices),
        "high_z_threshold": high_z_threshold,
        "cluster_radius_m": cluster_radius_m,
        "lookback_hours": lookback_hours,
        "escalation_triggered": escalation_triggered,
        "confidence_boost_applied": False,
        "actions": [],
    }

    if pothole is not None and len(device_ids) > int(settings.CROWD_CONFIDENCE_BOOST_MIN_DEVICES):
        boost_value = float(settings.CROWD_CONFIDENCE_BOOST_VALUE)
        base_conf = float(pothole.confidence_score or 0.6)
        pothole.confidence_score = min(round(base_conf + boost_value, 3), 1.0)
        pothole.status = "Confirmed" if float(pothole.confidence_score) >= 0.9 else pothole.status
        confidence_boost_applied = True
        trigger_summary["confidence_boost_applied"] = True
        trigger_summary["actions"].append("confidence_boost")

    if escalation_triggered:
        if pothole is not None:
            pothole.severity = _elevate_severity(pothole.severity)

        bbox = _bbox_for_point(center_lat, center_lon, cluster_radius_m)
        from app.tasks.satellite_tasks import scan_satellite_bbox

        scan_satellite_bbox.delay(
            "CARTOSAT-3",
            bbox,
            f"crowd-consensus-{report.id}",
            8,
            25.0,
            None,
            None,
            None,
            True,
        )
        trigger_summary["actions"].append("satellite_scan")

        nearest_cctv = await _nearest_cctv(db, center_lat, center_lon, float(settings.CROWD_CCTV_RADIUS_M))
        if nearest_cctv is not None:
            from app.tasks.cctv_tasks import process_cctv_node

            process_cctv_node.delay(nearest_cctv.id, pothole.nh_number if pothole else "crowd-consensus")
            trigger_summary["actions"].append("nearest_cctv_analysis")
            trigger_summary["nearest_cctv_id"] = nearest_cctv.id
        else:
            from app.tasks.drone_tasks import ingest_openaerialmap_bbox

            ingest_openaerialmap_bbox.delay(
                bbox,
                f"crowd-consensus-{report.id}",
                0.8,
                20,
                None,
                None,
            )
            trigger_summary["actions"].append("drone_footage_analysis")

    report_payload = dict(report.raw_payload or {})
    report_payload["crowd_consensus"] = trigger_summary
    report.raw_payload = report_payload

    await logger.ainfo(
        "crowd_consensus_evaluated",
        report_id=report.id,
        pothole_id=report.pothole_id,
        consensus_devices=len(device_ids),
        high_z_devices=len(high_z_devices),
        escalation_triggered=escalation_triggered,
        confidence_boost_applied=confidence_boost_applied,
    )

    return {
        "consensus_devices": len(device_ids),
        "high_z_devices": len(high_z_devices),
        "escalation_triggered": escalation_triggered,
        "confidence_boost_applied": confidence_boost_applied,
        "actions": trigger_summary["actions"],
        "pothole_id": report.pothole_id,
    }
