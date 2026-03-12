"""Admin pipeline monitoring endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.task import TaskHistory
from app.models.pothole import Pothole
from app.models.complaint import Complaint

router = APIRouter(prefix="/api/admin/pipeline", tags=["admin-pipeline"])


@router.get("/status")
async def pipeline_status(db: AsyncSession = Depends(get_db)):
    """Real-time pipeline status across all data sources."""
    from app.models.satellite import SatelliteJob
    from app.models.drone import DroneMission

    now = datetime.now(timezone.utc)
    last_hour = now - timedelta(hours=1)
    last_24h = now - timedelta(hours=24)

    # Satellite jobs status
    sat_q = await db.execute(
        select(
            SatelliteJob.status,
            func.count(SatelliteJob.id),
        )
        .where(SatelliteJob.created_at >= last_24h)
        .group_by(SatelliteJob.status)
    )
    sat_status = {r[0]: r[1] for r in sat_q.all()}

    # Drone missions
    drone_q = await db.execute(
        select(
            DroneMission.processing_status,
            func.count(DroneMission.id),
        )
        .where(DroneMission.created_at >= last_24h)
        .group_by(DroneMission.processing_status)
    )
    drone_status = {r[0]: r[1] for r in drone_q.all()}

    # Recent detections
    det_1h = await db.execute(
        select(func.count(Pothole.id)).where(Pothole.detected_at >= last_hour)
    )
    det_24h = await db.execute(
        select(func.count(Pothole.id)).where(Pothole.detected_at >= last_24h)
    )

    # Recent complaints
    comp_24h = await db.execute(
        select(func.count(Complaint.id)).where(Complaint.filed_at >= last_24h)
    )

    return {
        "satellite_jobs_24h": sat_status,
        "drone_missions_24h": drone_status,
        "detections_last_hour": det_1h.scalar() or 0,
        "detections_last_24h": det_24h.scalar() or 0,
        "complaints_last_24h": comp_24h.scalar() or 0,
    }


@router.get("/task-history")
async def task_history(
    limit: int = 100,
    task_name: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Recent Celery task execution history."""
    q = select(TaskHistory).order_by(TaskHistory.completed_at.desc()).limit(limit)
    if task_name:
        q = q.where(TaskHistory.task_name.ilike(f"%{task_name}%"))
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/queue-depths")
async def queue_depths():
    """Current Celery queue depths from Redis."""
    import redis

    from app.config import settings

    r = redis.from_url(settings.REDIS_URL)
    queues = [
        "satellite", "inference", "drone", "filing",
        "verification", "notification", "admin",
    ]
    depths = {}
    for q_name in queues:
        depths[q_name] = r.llen(q_name)
    return depths


@router.get("/throughput")
async def throughput(
    hours: int = 24,
    db: AsyncSession = Depends(get_db),
):
    """Hourly task throughput over the last N hours."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(
            func.date_trunc("hour", TaskHistory.completed_at).label("hour"),
            func.count(TaskHistory.id).label("count"),
            func.avg(TaskHistory.duration_seconds).label("avg_duration"),
        )
        .where(TaskHistory.completed_at >= since)
        .group_by("hour")
        .order_by("hour")
    )
    return [
        {
            "hour": r.hour.isoformat(),
            "count": r.count,
            "avg_duration_s": round(float(r.avg_duration or 0), 2),
        }
        for r in result.all()
    ]
