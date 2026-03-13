"""Admin system overview endpoint — the main admin dashboard."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pothole import Pothole
from app.models.complaint import Complaint
from app.models.satellite import SatelliteJob
from app.models.drone import DroneMission
from app.models.cctv import CCTVNode
from app.schemas.admin import SystemOverview

router = APIRouter(prefix="/api/admin/overview", tags=["admin-overview"])


@router.get("/", response_model=SystemOverview)
async def system_overview(db: AsyncSession = Depends(get_db)):
    """Full system health and stats overview for admin dashboard."""
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)

    # Pothole stats
    total_potholes = (await db.execute(
        select(func.count(Pothole.id))
    )).scalar() or 0

    active_potholes = (await db.execute(
        select(func.count(Pothole.id))
        .where(Pothole.status.in_(["Detected", "Confirmed"]))
    )).scalar() or 0

    critical_potholes = (await db.execute(
        select(func.count(Pothole.id)).where(Pothole.severity == "Critical")
    )).scalar() or 0

    new_24h = (await db.execute(
        select(func.count(Pothole.id)).where(Pothole.detected_at >= last_24h)
    )).scalar() or 0

    # Complaint stats
    total_complaints = (await db.execute(
        select(func.count(Complaint.id))
    )).scalar() or 0

    open_complaints = (await db.execute(
        select(func.count(Complaint.id))
        .where(Complaint.portal_status.notin_(["Resolved", "Closed"]))
    )).scalar() or 0

    critically_overdue = (await db.execute(
        select(func.count(Pothole.id)).where(Pothole.critically_overdue.is_(True))
    )).scalar() or 0

    # Source stats
    active_sat_jobs = (await db.execute(
        select(func.count(SatelliteJob.id))
        .where(SatelliteJob.status.in_(["PENDING", "RUNNING"]))
    )).scalar() or 0

    active_drone_missions = (await db.execute(
        select(func.count(DroneMission.id))
        .where(DroneMission.processing_status.in_(["PENDING", "PROCESSING"]))
    )).scalar() or 0

    active_cctv = (await db.execute(
        select(func.count(CCTVNode.id)).where(CCTVNode.is_active.is_(True))
    )).scalar() or 0

    return SystemOverview(
        total_potholes=total_potholes,
        active_potholes=active_potholes,
        critical_potholes=critical_potholes,
        new_last_24h=new_24h,
        total_complaints=total_complaints,
        open_complaints=open_complaints,
        critically_overdue=critically_overdue,
        active_satellite_jobs=active_sat_jobs,
        active_drone_missions=active_drone_missions,
        active_cctv_cameras=active_cctv,
    )


@router.get("/health")
async def system_health():
    """Check health of all system components."""
    import redis
    import httpx

    from app.config import settings
    from app.database import engine

    checks = []

    # Database
    try:
        async with engine.connect() as conn:
            await conn.execute(select(func.now()))
        checks.append({"name": "PostgreSQL", "status": "healthy"})
    except Exception as e:
        checks.append({"name": "PostgreSQL", "status": "unhealthy", "error": str(e)})

    # Redis
    try:
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        checks.append({"name": "Redis", "status": "healthy"})
    except Exception as e:
        checks.append({"name": "Redis", "status": "unhealthy", "error": str(e)})

    # MinIO
    try:
        from app.services.minio_client import get_minio_client
        client = get_minio_client()
        client.list_buckets()
        checks.append({"name": "MinIO", "status": "healthy"})
    except Exception as e:
        checks.append({"name": "MinIO", "status": "unhealthy", "error": str(e)})

    # Celery workers
    try:
        from app.tasks.celery_app import app as celery_app
        inspect = celery_app.control.inspect(timeout=3)
        ping = inspect.ping() or {}
        worker_count = len(ping)
        checks.append({
            "name": "Celery Workers",
            "status": "healthy" if worker_count > 0 else "degraded",
            "workers": worker_count,
        })
    except Exception as e:
        checks.append({"name": "Celery Workers", "status": "unhealthy", "error": str(e)})

    # NodeODM
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.NODEODM_URL}/info")
            if resp.status_code == 200:
                checks.append({"name": "NodeODM", "status": "healthy"})
            else:
                checks.append({"name": "NodeODM", "status": "degraded"})
    except Exception:
        checks.append({"name": "NodeODM", "status": "offline"})

    overall = "healthy"
    if any(c["status"] == "unhealthy" for c in checks):
        overall = "unhealthy"
    elif any(c["status"] in ("degraded", "offline") for c in checks):
        overall = "degraded"

    return {"overall": overall, "checks": checks}
