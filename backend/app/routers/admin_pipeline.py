"""Admin pipeline monitoring endpoints."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.task import TaskHistory
from app.models.pothole import Pothole
from app.models.complaint import Complaint
from app.models.source_report import SourceReport
from app.models.settings import ModelRegistry

router = APIRouter(prefix="/api/admin/pipeline", tags=["admin-pipeline"])


def _sha256_prefix(path: Path, prefix_len: int = 16) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:prefix_len]


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
    rows = result.scalars().all()
    return [
        {
            "id": row.id,
            "task_name": row.task_name,
            "task_id": row.task_id,
            "status": row.status,
            "result": row.result,
            "duration_seconds": row.duration_seconds,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        }
        for row in rows
    ]


@router.get("/queue-depths")
async def queue_depths():
    """Current Celery queue depths from Redis."""
    import redis

    from app.config import settings

    r = redis.from_url(settings.REDIS_URL)
    queue_map = {
        "satellite": "satellite_queue",
        "inference": "inference_queue",
        "drone": "drone_queue",
        "filing": "filing_queue",
        "verification": "verification_queue",
        "notification": "notification_queue",
        "admin": "admin_queue",
    }
    depths = {}
    for label, redis_queue in queue_map.items():
        depths[label] = r.llen(redis_queue)
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


@router.get("/full-test-report")
async def full_test_report(db: AsyncSession = Depends(get_db)):
    """Comprehensive pipeline validation snapshot for admin testing page."""
    import redis

    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)

    checks: list[dict] = []

    db_ok = True
    db_error = None
    try:
        await db.execute(select(func.count(Pothole.id)).limit(1))
    except Exception as exc:
        db_ok = False
        db_error = str(exc)
    checks.append(
        {
            "name": "database",
            "ok": db_ok,
            "detail": "DB query succeeded" if db_ok else db_error,
        }
    )

    redis_ok = True
    redis_error = None
    queue_depths: dict[str, int] = {}
    try:
        client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=2, socket_timeout=2)
        redis_ok = bool(client.ping())
        queue_map = {
            "satellite": "satellite_queue",
            "inference": "inference_queue",
            "drone": "drone_queue",
            "filing": "filing_queue",
            "verification": "verification_queue",
            "notification": "notification_queue",
            "admin": "admin_queue",
        }
        for label, redis_queue in queue_map.items():
            queue_depths[label] = int(client.llen(redis_queue))
    except Exception as exc:
        redis_ok = False
        redis_error = str(exc)
    checks.append(
        {
            "name": "redis",
            "ok": redis_ok,
            "detail": "Redis ping succeeded" if redis_ok else redis_error,
        }
    )

    yolo_path = Path("/models/yolov8x-seg-pothole.pt")
    model_exists = yolo_path.exists() and yolo_path.is_file()
    model_size_mb = round(yolo_path.stat().st_size / (1024 * 1024), 2) if model_exists else 0.0
    model_hash = _sha256_prefix(yolo_path)
    checks.append(
        {
            "name": "yolo_weights",
            "ok": model_exists,
            "detail": (
                f"{yolo_path} ({model_size_mb} MB)"
                if model_exists
                else f"Missing model file at {yolo_path}"
            ),
        }
    )

    active_model_q = await db.execute(
        select(ModelRegistry)
        .where(ModelRegistry.model_type == "DETECTION", ModelRegistry.is_active.is_(True))
        .order_by(ModelRegistry.id.desc())
        .limit(1)
    )
    active_model = active_model_q.scalar_one_or_none()
    registry_ok = active_model is not None
    checks.append(
        {
            "name": "model_registry",
            "ok": registry_ok,
            "detail": (
                f"Active detection model: {active_model.model_name} ({active_model.version})"
                if active_model
                else "No active DETECTION model in registry"
            ),
        }
    )

    reports_q = await db.execute(
        select(func.count(SourceReport.id)).where(SourceReport.created_at >= last_24h)
    )
    potholes_q = await db.execute(
        select(func.count(Pothole.id)).where(Pothole.detected_at >= last_24h)
    )
    tasks_success_q = await db.execute(
        select(func.count(TaskHistory.id)).where(
            TaskHistory.completed_at >= last_24h,
            TaskHistory.status == "SUCCESS",
        )
    )
    tasks_failed_q = await db.execute(
        select(func.count(TaskHistory.id)).where(
            TaskHistory.completed_at >= last_24h,
            TaskHistory.status == "FAILED",
        )
    )

    recent_fail_q = await db.execute(
        select(TaskHistory)
        .where(TaskHistory.status == "FAILED")
        .order_by(TaskHistory.completed_at.desc())
        .limit(8)
    )
    recent_failures = recent_fail_q.scalars().all()

    reports_24h = int(reports_q.scalar() or 0)
    potholes_24h = int(potholes_q.scalar() or 0)
    task_success_24h = int(tasks_success_q.scalar() or 0)
    task_failed_24h = int(tasks_failed_q.scalar() or 0)

    checks.append(
        {
            "name": "pipeline_activity",
            "ok": reports_24h > 0 or potholes_24h > 0 or (task_success_24h + task_failed_24h) > 0,
            "detail": (
                f"reports_24h={reports_24h}, potholes_24h={potholes_24h}, "
                f"task_success_24h={task_success_24h}, task_failed_24h={task_failed_24h}"
            ),
        }
    )

    overall_ok = all(item["ok"] for item in checks[:4])

    return {
        "generated_at": now.isoformat(),
        "overall_status": "healthy" if overall_ok else "degraded",
        "checks": checks,
        "model": {
            "path": str(yolo_path),
            "exists": model_exists,
            "size_mb": model_size_mb,
            "sha256_prefix": model_hash,
            "active_registry_model": (
                {
                    "name": active_model.model_name,
                    "version": active_model.version,
                    "weights_path": active_model.weights_path,
                }
                if active_model
                else None
            ),
        },
        "queues": queue_depths,
        "activity_24h": {
            "source_reports": reports_24h,
            "potholes_detected": potholes_24h,
            "tasks_success": task_success_24h,
            "tasks_failed": task_failed_24h,
        },
        "recent_failed_tasks": [
            {
                "id": row.id,
                "task_name": row.task_name,
                "task_id": row.task_id,
                "completed_at": row.completed_at.isoformat() if row.completed_at else None,
                "duration_seconds": row.duration_seconds,
                "result": row.result,
            }
            for row in recent_failures
        ],
    }
