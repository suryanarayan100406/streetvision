"""Admin scheduler management — view, pause, resume, modify beat tasks."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.admin import SchedulerTaskOut, SchedulerTaskUpdate

router = APIRouter(prefix="/api/admin/scheduler", tags=["admin-scheduler"])


def _get_beat_schedule() -> dict:
    """Get the current Celery beat schedule."""
    from app.tasks.beat_schedule import BEAT_SCHEDULE
    return BEAT_SCHEDULE


@router.get("/tasks", response_model=list[SchedulerTaskOut])
async def list_scheduled_tasks():
    """List all scheduled Celery beat tasks."""
    schedule = _get_beat_schedule()
    tasks = []
    for name, conf in schedule.items():
        sched = conf.get("schedule")
        tasks.append(
            SchedulerTaskOut(
                name=name,
                task=conf["task"],
                schedule_repr=str(sched),
                enabled=conf.get("enabled", True),
                args=conf.get("args"),
                kwargs=conf.get("kwargs"),
                queue=conf.get("options", {}).get("queue"),
            )
        )
    return tasks


@router.patch("/tasks/{task_name}")
async def update_task(task_name: str, body: SchedulerTaskUpdate):
    """Update a scheduled task (enable/disable, change schedule)."""
    schedule = _get_beat_schedule()
    if task_name not in schedule:
        raise HTTPException(status_code=404, detail="Task not found in schedule")

    if body.enabled is not None:
        schedule[task_name]["enabled"] = body.enabled

    return {"updated": task_name, "enabled": schedule[task_name].get("enabled", True)}


@router.post("/tasks/{task_name}/run-now")
async def run_task_now(task_name: str):
    """Manually trigger a scheduled task immediately."""
    schedule = _get_beat_schedule()
    if task_name not in schedule:
        raise HTTPException(status_code=404, detail="Task not found in schedule")

    from app.tasks.celery_app import app as celery_app

    task_path = schedule[task_name]["task"]
    result = celery_app.send_task(task_path)
    return {"task_id": result.id, "task": task_path}


@router.get("/workers")
async def list_workers():
    """List active Celery workers and their status."""
    from app.tasks.celery_app import app as celery_app

    inspect = celery_app.control.inspect()
    active = inspect.active() or {}
    stats = inspect.stats() or {}

    workers = []
    for worker_name, tasks in active.items():
        worker_stats = stats.get(worker_name, {})
        workers.append({
            "name": worker_name,
            "active_tasks": len(tasks),
            "concurrency": worker_stats.get("pool", {}).get("max-concurrency"),
            "uptime": worker_stats.get("uptime"),
        })

    return workers
