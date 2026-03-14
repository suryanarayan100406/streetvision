"""Public API endpoints — no authentication required."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_AsGeoJSON, ST_DWithin, ST_MakePoint

from app.database import get_db
from app.models.pothole import Pothole
from app.models.complaint import Complaint
from app.models.cctv import CCTVNode
from app.models.drone import DroneMission
from app.models.satellite import SatelliteJob
from app.models.source_report import SourceReport
from app.models.settings import GamificationPoints
from app.schemas.pothole import PotholeOut, PotholeDetail, PotholeListParams

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/potholes", response_model=list[PotholeOut])
async def list_potholes(
    params: PotholeListParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """List potholes with optional filters."""
    q = select(Pothole)

    if params.severity:
        q = q.where(Pothole.severity == params.severity)
    if params.nh_number:
        q = q.where(Pothole.nh_number == params.nh_number)
    if params.status:
        q = q.where(Pothole.status == params.status)
    if params.min_risk is not None:
        q = q.where(Pothole.risk_score >= params.min_risk)
    if params.bbox:
        parts = [float(x) for x in params.bbox.split(",")]
        if len(parts) == 4:
            from geoalchemy2.functions import ST_MakeEnvelope
            q = q.where(
                Pothole.geom.ST_Within(
                    ST_MakeEnvelope(parts[0], parts[1], parts[2], parts[3], 4326)
                )
            )

    q = q.order_by(Pothole.risk_score.desc())
    q = q.offset(params.offset).limit(params.limit)

    result = await db.execute(q)
    return result.scalars().all()


@router.get("/potholes/{pothole_id}", response_model=PotholeDetail)
async def get_pothole(pothole_id: int, db: AsyncSession = Depends(get_db)):
    """Get detailed pothole information including complaints and sources."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Pothole)
        .options(
            selectinload(Pothole.complaints),
            selectinload(Pothole.source_reports),
        )
        .where(Pothole.id == pothole_id)
    )
    pothole = result.scalar_one_or_none()
    if not pothole:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Pothole not found")
    return pothole


@router.get("/potholes/nearby")
async def nearby_potholes(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: float = Query(500, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Find potholes within radius of a point."""
    point = ST_MakePoint(lon, lat)
    q = (
        select(Pothole)
        .where(ST_DWithin(Pothole.geom, func.ST_SetSRID(point, 4326), radius_m))
        .order_by(Pothole.risk_score.desc())
        .limit(50)
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/stats")
async def public_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate statistics for the public dashboard."""
    total_q = await db.execute(select(func.count(Pothole.id)))
    total = total_q.scalar() or 0

    filed_q = await db.execute(
        select(func.count(Complaint.id)).where(Complaint.portal_status != None)
    )
    filed = filed_q.scalar() or 0

    repaired_q = await db.execute(
        select(func.count(Pothole.id)).where(Pothole.status == "Repaired")
    )
    repaired = repaired_q.scalar() or 0

    critical_q = await db.execute(
        select(func.count(Pothole.id)).where(Pothole.severity == "Critical")
    )
    critical = critical_q.scalar() or 0

    by_nh_q = await db.execute(
        select(Pothole.nh_number, func.count(Pothole.id))
        .group_by(Pothole.nh_number)
    )
    by_nh = {r[0]: r[1] for r in by_nh_q.all()}

    return {
        "total_potholes": total,
        "complaints_filed": filed,
        "repaired": repaired,
        "critical": critical,
        "by_highway": by_nh,
    }


@router.get("/geojson")
async def potholes_geojson(
    nh_number: str | None = None,
    severity: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """GeoJSON FeatureCollection of all potholes for map rendering."""
    q = select(
        Pothole.id,
        Pothole.latitude,
        Pothole.longitude,
        Pothole.severity,
        Pothole.risk_score,
        Pothole.status,
        Pothole.nh_number,
        Pothole.detected_at,
    )
    if nh_number:
        q = q.where(Pothole.nh_number == nh_number)
    if severity:
        q = q.where(Pothole.severity == severity)

    result = await db.execute(q)
    rows = result.all()

    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [r.longitude, r.latitude],
            },
            "properties": {
                "id": r.id,
                "severity": r.severity,
                "risk_score": float(r.risk_score) if r.risk_score else 0,
                "status": r.status,
                "nh_number": r.nh_number,
                "detected_at": r.detected_at.isoformat() if r.detected_at else None,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }


# ---------------------------------------------------------------------------
# CCTV public summary (no RTSP URLs exposed)
# ---------------------------------------------------------------------------

@router.get("/cctv/nodes")
async def public_cctv_nodes(
    active_only: bool = True,
    db: AsyncSession = Depends(get_db),
):
    """Return active CCTV node locations for map display. RTSP URLs are never exposed."""
    q = select(
        CCTVNode.id,
        CCTVNode.name,
        CCTVNode.latitude,
        CCTVNode.longitude,
        CCTVNode.nh_number,
        CCTVNode.chainage_km,
        CCTVNode.is_active,
        CCTVNode.last_frame_at,
    )
    if active_only:
        q = q.where(CCTVNode.is_active.is_(True))
    q = q.order_by(CCTVNode.name)
    result = await db.execute(q)
    rows = result.all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "nh_number": r.nh_number,
            "chainage_km": r.chainage_km,
            "is_active": r.is_active,
            "last_frame_at": r.last_frame_at.isoformat() if r.last_frame_at else None,
            "source": "CCTV",
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Crowdsourcing endpoints (public)
# ---------------------------------------------------------------------------


@router.post("/crowd/report")
async def submit_crowd_report(
    latitude: float = Form(...),
    longitude: float = Form(...),
    severity_estimate: str = Form("Medium"),
    description: str = Form(""),
    user_id: str | None = Form(None),
    display_name: str | None = Form(None),
    device_id: str | None = Form(None),
    z_axis_change: float | None = Form(None),
    source_type: str = Form("crowd_visual"),
    image: UploadFile | None = File(None),
    db: AsyncSession = Depends(get_db),
):
    """Submit a crowdsourced pothole report (with optional photo)."""
    from app.services.minio_client import upload_bytes

    image_path = None
    if image is not None:
        image_data = await image.read()
        if len(image_data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image too large (max 10MB)")

        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        image_path = f"crowd-reports/{ts}_{image.filename}"
        upload_bytes(
            image_path,
            image_data,
            content_type=image.content_type or "application/octet-stream",
        )

    safe_source = source_type if source_type in {"crowd_visual", "crowd_vibration"} else "crowd_visual"

    report = SourceReport(
        pothole_id=None,
        source_type=safe_source,
        latitude=latitude,
        longitude=longitude,
        image_url=image_path,
        raw_payload={
            "severity_estimate": severity_estimate,
            "description": description,
            "user_id": user_id,
            "display_name": display_name,
            "device_id": device_id,
            "z_axis_change": z_axis_change,
        },
        processed=False,
    )
    db.add(report)
    await db.flush()

    from app.services.crowd_consensus import apply_crowd_consensus

    consensus = await apply_crowd_consensus(db, report)

    points_earned = 0
    if user_id:
        points_earned = 10 if safe_source == "crowd_visual" else 6
        gp_q = await db.execute(
            select(GamificationPoints).where(GamificationPoints.user_id == user_id)
        )
        gp = gp_q.scalar_one_or_none()
        if gp:
            gp.total_points += points_earned
            gp.reports_count += 1
            if display_name and not gp.display_name:
                gp.display_name = display_name
        else:
            gp = GamificationPoints(
                user_id=user_id,
                display_name=display_name,
                total_points=points_earned,
                reports_count=1,
            )
            db.add(gp)

    await db.commit()
    await db.refresh(report)

    return {
        "report_id": report.id,
        "status": "received",
        "points_earned": points_earned,
        "consensus": consensus,
        "message": "Crowdsourced report submitted successfully.",
    }


@router.get("/crowd/reports")
async def list_crowd_reports(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List latest crowdsourced reports for public feed."""
    from app.services.minio_client import get_presigned_url

    result = await db.execute(
        select(SourceReport)
        .where(SourceReport.source_type.in_(["crowd_visual", "crowd_vibration", "mobile_visual", "mobile_vibration"]))
        .order_by(SourceReport.created_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()

    payload = []
    for row in rows:
        image_url = None
        if row.image_url:
            try:
                image_url = get_presigned_url(row.image_url, expires_hours=24)
            except Exception:
                image_url = None

        payload.append(
            {
                "id": row.id,
                "source_type": row.source_type,
                "latitude": row.latitude,
                "longitude": row.longitude,
                "processed": row.processed,
                "captured_at": row.captured_at.isoformat() if row.captured_at else None,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "image_url": image_url,
                "raw_payload": row.raw_payload or {},
            }
        )

    return payload


@router.get("/crowd/leaderboard")
async def crowd_leaderboard(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Crowdsourcing leaderboard by points."""
    result = await db.execute(
        select(GamificationPoints)
        .order_by(GamificationPoints.total_points.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "rank": i + 1,
            "user_id": r.user_id,
            "display_name": r.display_name,
            "total_points": r.total_points,
            "reports_count": r.reports_count,
        }
        for i, r in enumerate(rows)
    ]


# ---------------------------------------------------------------------------
# Drone missions public summary
# ---------------------------------------------------------------------------

@router.get("/drones/missions")
async def public_drone_missions(
    limit: int = Query(50, le=200),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return drone mission summaries for public display."""
    q = select(
        DroneMission.id,
        DroneMission.mission_name,
        DroneMission.operator,
        DroneMission.flight_date,
        DroneMission.area_bbox,
        DroneMission.image_count,
        DroneMission.gsd_cm,
        DroneMission.processing_status,
        DroneMission.created_at,
        DroneMission.completed_at,
    ).order_by(DroneMission.created_at.desc()).limit(limit)
    if status:
        q = q.where(DroneMission.processing_status == status)
    result = await db.execute(q)
    rows = result.all()
    return [
        {
            "id": r.id,
            "mission_name": r.mission_name,
            "operator": r.operator,
            "flight_date": r.flight_date.isoformat() if r.flight_date else None,
            "area_bbox": r.area_bbox,
            "image_count": r.image_count,
            "gsd_cm": r.gsd_cm,
            "processing_status": r.processing_status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "source": "Drone",
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Satellite jobs public summary
# ---------------------------------------------------------------------------

@router.get("/satellites/jobs")
async def public_satellite_jobs(
    limit: int = Query(50, le=200),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Return recent satellite scan jobs for public display."""
    q = select(
        SatelliteJob.id,
        SatelliteJob.status,
        SatelliteJob.bbox,
        SatelliteJob.tiles_total,
        SatelliteJob.tiles_processed,
        SatelliteJob.tiles_forwarded_to_inference,
        SatelliteJob.monitoring_only_tiles,
        SatelliteJob.detections_count,
        SatelliteJob.created_at,
        SatelliteJob.completed_at,
    ).order_by(SatelliteJob.created_at.desc()).limit(limit)
    if status:
        q = q.where(SatelliteJob.status == status)
    result = await db.execute(q)
    rows = result.all()
    return [
        {
            "id": r.id,
            "status": r.status,
            "bbox": r.bbox,
            "tiles_total": r.tiles_total,
            "tiles_processed": r.tiles_processed,
            "tiles_forwarded_to_inference": r.tiles_forwarded_to_inference,
            "monitoring_only_tiles": r.monitoring_only_tiles,
            "detections_count": r.detections_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "source": "Satellite",
        }
        for r in rows
    ]
