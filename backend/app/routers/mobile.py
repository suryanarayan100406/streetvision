"""Mobile app API endpoints — visual/vibration reports, leaderboard."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.pothole import Pothole
from app.models.source_report import SourceReport
from app.models.settings import GamificationPoints
from app.schemas.mobile import MobileReportResponse

router = APIRouter(prefix="/api/mobile", tags=["mobile"])


@router.post("/report/visual", response_model=MobileReportResponse)
async def submit_visual_report(
    latitude: float = Form(...),
    longitude: float = Form(...),
    severity_estimate: str = Form("Medium"),
    description: str = Form(""),
    user_id: str = Form(None),
    device_id: str | None = Form(None),
    z_axis_change: float | None = Form(None),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Submit a visual pothole report with photo from the mobile app."""
    # Upload image to MinIO
    from app.services.minio_client import upload_bytes

    image_data = await image.read()
    if len(image_data) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=413, detail="Image too large (max 10MB)")

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = f"mobile-reports/{ts}_{image.filename}"
    upload_bytes(
        path,
        image_data,
        content_type=image.content_type or "application/octet-stream",
    )

    # Create source report
    source_report = SourceReport(
        source_type="mobile_visual",
        latitude=latitude,
        longitude=longitude,
        image_url=path,
        raw_payload={
            "severity_estimate": severity_estimate,
            "description": description,
            "user_id": user_id,
            "device_id": device_id,
            "z_axis_change": z_axis_change,
        },
        processed=False,
    )
    db.add(source_report)
    await db.flush()

    from app.services.crowd_consensus import apply_crowd_consensus

    consensus = await apply_crowd_consensus(db, source_report)

    # Award gamification points
    if user_id:
        points_q = await db.execute(
            select(GamificationPoints).where(GamificationPoints.user_id == user_id)
        )
        points = points_q.scalar_one_or_none()
        if points:
            points.total_points += 10
            points.reports_count += 1
        else:
            points = GamificationPoints(
                user_id=user_id,
                total_points=10,
                reports_count=1,
            )
            db.add(points)

    await db.commit()
    await db.refresh(source_report)

    # Queue for inference
    from app.tasks.cctv_tasks import run_inference_on_tile
    run_inference_on_tile.delay(path, "MOBILE_VISUAL", "")

    escalation = bool(consensus.get("escalation_triggered"))

    return MobileReportResponse(
        report_id=source_report.id,
        points_earned=10 if user_id else 0,
        message=(
            "Report submitted successfully. Consensus escalation triggered for satellite/CCTV-drone review."
            if escalation
            else "Report submitted successfully. Processing will begin shortly."
        ),
    )


@router.post("/report/vibration", response_model=MobileReportResponse)
async def submit_vibration_report(
    latitude: float = Form(...),
    longitude: float = Form(...),
    peak_acceleration: float = Form(...),
    duration_ms: int = Form(...),
    speed_kmh: float = Form(0),
    user_id: str = Form(None),
    device_id: str | None = Form(None),
    z_axis_change: float | None = Form(None),
    movement_variance: float = Form(0),
    moving: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    """Submit a vibration-based pothole detection from pocket mode."""
    effective_z_axis_change = z_axis_change if z_axis_change is not None else peak_acceleration

    # Validate acceleration threshold
    if (
        peak_acceleration < 1.5
        or effective_z_axis_change < float(settings.CROWD_Z_AXIS_HIGH_THRESHOLD)
        or speed_kmh < float(settings.MOBILE_VIBRATION_MIN_SPEED_KMH)
        or movement_variance < float(settings.MOBILE_VIBRATION_MIN_VARIANCE)
        or not moving
    ):
        return MobileReportResponse(
            report_id=0,
            status="below_threshold",
            points_earned=0,
            message="Large z-axis changes are only reported when the phone is moving and the vibration pattern is irregular enough.",
        )

    source_report = SourceReport(
        source_type="mobile_vibration",
        latitude=latitude,
        longitude=longitude,
        raw_payload={
            "peak_acceleration": peak_acceleration,
            "duration_ms": duration_ms,
            "speed_kmh": speed_kmh,
            "user_id": user_id,
            "device_id": device_id,
            "z_axis_change": effective_z_axis_change,
            "movement_variance": movement_variance,
            "moving": moving,
        },
        processed=False,
    )
    db.add(source_report)
    await db.flush()

    from app.services.crowd_consensus import apply_crowd_consensus

    consensus = await apply_crowd_consensus(db, source_report)

    # Estimate severity from vibration data
    if peak_acceleration > 5.0:
        severity = "High"
        points = 15
    elif peak_acceleration > 3.0:
        severity = "Medium"
        points = 10
    else:
        severity = "Low"
        points = 5

    if user_id:
        gp_q = await db.execute(
            select(GamificationPoints).where(GamificationPoints.user_id == user_id)
        )
        gp = gp_q.scalar_one_or_none()
        if gp:
            gp.total_points += points
            gp.reports_count += 1
        else:
            gp = GamificationPoints(
                user_id=user_id,
                total_points=points,
                reports_count=1,
            )
            db.add(gp)

    await db.commit()
    await db.refresh(source_report)

    escalation = bool(consensus.get("escalation_triggered"))

    return MobileReportResponse(
        report_id=source_report.id,
        status="received",
        points_earned=points if user_id else 0,
        message=(
            f"Vibration report submitted. Estimated severity: {severity}. Escalation triggered for satellite/CCTV-drone review."
            if escalation
            else f"Vibration report submitted. Estimated severity: {severity}"
        ),
        severity=severity,
    )


@router.get("/leaderboard")
async def mobile_leaderboard(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Get gamification leaderboard for mobile app."""
    result = await db.execute(
        select(GamificationPoints)
        .order_by(GamificationPoints.total_points.desc())
        .limit(limit)
    )
    entries = result.scalars().all()
    return [
        {
            "rank": i + 1,
            "user_id": e.user_id,
            "display_name": e.display_name,
            "total_points": e.total_points,
            "reports_count": e.reports_count,
        }
        for i, e in enumerate(entries)
    ]


@router.get("/nearby")
async def nearby_for_mobile(
    lat: float,
    lon: float,
    radius_m: float = 1000,
    db: AsyncSession = Depends(get_db),
):
    """Get nearby potholes for mobile map display."""
    from geoalchemy2.functions import ST_DWithin, ST_MakePoint
    from sqlalchemy import func

    point = ST_MakePoint(lon, lat)
    result = await db.execute(
        select(
            Pothole.id, Pothole.latitude, Pothole.longitude,
            Pothole.severity, Pothole.risk_score, Pothole.status,
        )
        .where(
            ST_DWithin(
                Pothole.geom,
                func.ST_SetSRID(point, 4326),
                radius_m,
            )
        )
        .order_by(Pothole.risk_score.desc())
        .limit(100)
    )
    rows = result.all()
    return [
        {
            "id": r.id,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "severity": r.severity,
            "risk_score": float(r.risk_score) if r.risk_score else 0,
            "status": r.status,
        }
        for r in rows
    ]
