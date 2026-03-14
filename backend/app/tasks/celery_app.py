"""Celery application and configuration."""

from __future__ import annotations

from celery import Celery

from app.config import settings

app = Celery(
    "pothole_intelligence",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.tasks.satellite_tasks.*": {"queue": "satellite_queue"},
        "app.tasks.drone_tasks.*": {"queue": "drone_queue"},
        "app.tasks.cctv_tasks.*": {"queue": "inference_queue"},
        "app.tasks.filing_tasks.*": {"queue": "filing_queue"},
        "app.tasks.verification_tasks.*": {"queue": "verification_queue"},
        "app.tasks.escalation_tasks.*": {"queue": "notification_queue"},
        "app.tasks.weather_tasks.*": {"queue": "satellite_queue"},
        "app.tasks.data_ingestion_tasks.*": {"queue": "satellite_queue"},
        "app.tasks.model_tasks.*": {"queue": "admin_queue"},
    },
)

# Import beat schedule
from app.tasks.beat_schedule import CELERY_BEAT_SCHEDULE

app.conf.beat_schedule = CELERY_BEAT_SCHEDULE

# Auto-discover tasks
app.autodiscover_tasks([
    "app.tasks.satellite_tasks",
    "app.tasks.drone_tasks",
    "app.tasks.cctv_tasks",
    "app.tasks.weather_tasks",
    "app.tasks.filing_tasks",
    "app.tasks.verification_tasks",
    "app.tasks.escalation_tasks",
    "app.tasks.data_ingestion_tasks",
    "app.tasks.model_tasks",
])
