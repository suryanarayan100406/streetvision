"""Celery beat schedule — all 30+ periodic tasks."""

from celery.schedules import crontab
from datetime import timedelta

CELERY_BEAT_SCHEDULE = {
    # ─── Satellite Ingestion ──────────────────────────────────
    "satellite_s2_job": {
        "task": "app.tasks.satellite_tasks.ingest_sentinel2",
        "schedule": crontab(hour=2, minute=0, day_of_week="*/5"),
        "options": {"queue": "satellite_queue"},
    },
    "satellite_cartosat3_job": {
        "task": "app.tasks.satellite_tasks.ingest_cartosat3",
        "schedule": crontab(hour=3, minute=0, day_of_week="*/4"),
        "options": {"queue": "satellite_queue"},
    },
    "satellite_cartosat2s_job": {
        "task": "app.tasks.satellite_tasks.ingest_cartosat2s",
        "schedule": crontab(hour=3, minute=30, day_of_week="*/3"),
        "options": {"queue": "satellite_queue"},
    },
    "satellite_landsat9_job": {
        "task": "app.tasks.satellite_tasks.ingest_landsat9",
        "schedule": crontab(hour=4, minute=0, day_of_week="*/8"),
        "options": {"queue": "satellite_queue"},
    },
    "satellite_sar_sentinel1_job": {
        "task": "app.tasks.satellite_tasks.ingest_sentinel1_sar",
        "schedule": crontab(hour=2, minute=30, day_of_week="*/6"),
        "options": {"queue": "satellite_queue"},
    },
    "satellite_risat2b_job": {
        "task": "app.tasks.satellite_tasks.ingest_risat2b",
        "schedule": crontab(hour=5, minute=0, day_of_week="*/2"),
        "options": {"queue": "satellite_queue"},
    },
    "satellite_eos04_job": {
        "task": "app.tasks.satellite_tasks.ingest_eos04",
        "schedule": crontab(hour=5, minute=30, day_of_week="*/3"),
        "options": {"queue": "satellite_queue"},
    },
    "satellite_alos2_job": {
        "task": "app.tasks.satellite_tasks.ingest_alos2",
        "schedule": crontab(hour=6, minute=0, day_of_week="*/14"),
        "options": {"queue": "satellite_queue"},
    },
    "satellite_modis_job": {
        "task": "app.tasks.satellite_tasks.ingest_modis",
        "schedule": crontab(hour=1, minute=0),  # Daily
        "options": {"queue": "satellite_queue"},
    },
    # ─── Drone / Imagery Ingestion ────────────────────────────
    "oam_ingestion_job": {
        "task": "app.tasks.drone_tasks.ingest_openaerialmap",
        "schedule": crontab(hour=8, minute=0, day_of_week="1"),  # Weekly Monday
        "options": {"queue": "drone_queue"},
    },
    "mapillary_ingestion_job": {
        "task": "app.tasks.data_ingestion_tasks.ingest_mapillary",
        "schedule": crontab(hour=9, minute=0, day_of_week="1"),
        "options": {"queue": "satellite_queue"},
    },
    "kartaview_ingestion_job": {
        "task": "app.tasks.data_ingestion_tasks.ingest_kartaview",
        "schedule": crontab(hour=9, minute=30, day_of_week="1"),
        "options": {"queue": "satellite_queue"},
    },
    "cctv_polling_job": {
        "task": "app.tasks.cctv_tasks.poll_active_cctv_nodes",
        "schedule": timedelta(seconds=30),
        "options": {"queue": "inference_queue"},
    },
    # ─── Weather ──────────────────────────────────────────────
    "imd_weather_job": {
        "task": "app.tasks.weather_tasks.fetch_imd",
        "schedule": crontab(minute=0, hour="*/3"),  # Every 3 hours
        "options": {"queue": "satellite_queue"},
    },
    "openmeteo_weather_job": {
        "task": "app.tasks.weather_tasks.fetch_openmeteo",
        "schedule": crontab(minute=0, hour="*/6"),  # Every 6 hours
        "options": {"queue": "satellite_queue"},
    },
    "gfs_weather_job": {
        "task": "app.tasks.weather_tasks.fetch_gfs",
        "schedule": crontab(hour="0,6,12,18", minute=30),  # 4x daily after GFS runs
        "options": {"queue": "satellite_queue"},
    },
    "openweathermap_job": {
        "task": "app.tasks.weather_tasks.fetch_openweathermap",
        "schedule": crontab(minute=0, hour="*/4"),
        "options": {"queue": "satellite_queue"},
    },
    # ─── Government Data ──────────────────────────────────────
    "accident_data_refresh_job": {
        "task": "app.tasks.data_ingestion_tasks.refresh_accident_data",
        "schedule": crontab(hour=7, minute=0, day_of_month="1"),  # Monthly
        "options": {"queue": "satellite_queue"},
    },
    "ncrb_refresh_job": {
        "task": "app.tasks.data_ingestion_tasks.refresh_ncrb",
        "schedule": crontab(hour=8, minute=0, month_of_year="1", day_of_month="15"),  # Jan 15
        "options": {"queue": "satellite_queue"},
    },
    "nhai_traffic_job": {
        "task": "app.tasks.data_ingestion_tasks.refresh_nhai_traffic",
        "schedule": crontab(hour=7, minute=30, day_of_month="1"),
        "options": {"queue": "satellite_queue"},
    },
    "osm_geometry_refresh_job": {
        "task": "app.tasks.data_ingestion_tasks.refresh_osm_geometry",
        "schedule": crontab(hour=0, minute=0, day_of_month="1"),
        "options": {"queue": "satellite_queue"},
    },
    "bhuvan_nhai_refresh_job": {
        "task": "app.tasks.data_ingestion_tasks.refresh_bhuvan_nhai",
        "schedule": crontab(hour=1, minute=0, day_of_month="1"),
        "options": {"queue": "satellite_queue"},
    },
    "osm_notes_ingestion_job": {
        "task": "app.tasks.data_ingestion_tasks.ingest_osm_notes",
        "schedule": crontab(hour=10, minute=0, day_of_week="1"),
        "options": {"queue": "satellite_queue"},
    },
    # ─── Core Pipeline ────────────────────────────────────────
    "verify_repairs_job": {
        "task": "app.tasks.verification_tasks.verify_all_repairs",
        "schedule": crontab(hour=14, minute=0),  # Daily 2 PM
        "options": {"queue": "verification_queue"},
    },
    "portal_sync_job": {
        "task": "app.tasks.escalation_tasks.sync_detected_potholes_to_portal",
        "schedule": crontab(minute=30, hour="*/2"),  # Every 2 hours
        "options": {"queue": "notification_queue"},
    },
    "escalation_check_job": {
        "task": "app.tasks.escalation_tasks.check_all_escalations",
        "schedule": crontab(hour=6, minute=0),  # Daily 6 AM
        "options": {"queue": "notification_queue"},
    },
    # ─── Reporting ────────────────────────────────────────────
    "leaderboard_refresh_job": {
        "task": "app.tasks.data_ingestion_tasks.refresh_leaderboard",
        "schedule": crontab(hour="*/6", minute=15),
        "options": {"queue": "satellite_queue"},
    },
    "gemini_monthly_report_job": {
        "task": "app.tasks.filing_tasks.generate_monthly_report",
        "schedule": crontab(hour=10, minute=0, day_of_month="1"),
        "options": {"queue": "filing_queue"},
    },
    # ─── Maintenance ──────────────────────────────────────────
    "nominatim_update_job": {
        "task": "app.tasks.data_ingestion_tasks.update_nominatim",
        "schedule": crontab(hour=3, minute=0, day_of_month="15"),
        "options": {"queue": "satellite_queue"},
    },
    "model_metrics_refresh_job": {
        "task": "app.tasks.data_ingestion_tasks.refresh_model_metrics",
        "schedule": crontab(hour=0, minute=30),
        "options": {"queue": "satellite_queue"},
    },
    "minio_cleanup_job": {
        "task": "app.tasks.data_ingestion_tasks.cleanup_minio",
        "schedule": crontab(hour=4, minute=0, day_of_week="0"),
        "options": {"queue": "satellite_queue"},
    },
    "database_backup_job": {
        "task": "app.tasks.data_ingestion_tasks.backup_database",
        "schedule": crontab(hour=2, minute=0),  # Daily
        "options": {"queue": "satellite_queue"},
    },
}

# Backward-compatible alias used by admin scheduler endpoints.
BEAT_SCHEDULE = CELERY_BEAT_SCHEDULE
