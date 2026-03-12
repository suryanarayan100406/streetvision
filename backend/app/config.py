"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ─── Core ──────────────────────────────────────────────────
    SECRET_KEY: str = "change-me"
    DATABASE_URL: str = "postgresql+asyncpg://pothole:pothole@db:5432/pothole_db"
    SYNC_DATABASE_URL: str = "postgresql://pothole:pothole@db:5432/pothole_db"
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/2"

    # ─── Sentinel / Copernicus ─────────────────────────────────
    SENTINEL_USER: str = ""
    SENTINEL_PASS: str = ""
    CDSE_CLIENT_ID: str = ""
    CDSE_CLIENT_SECRET: str = ""

    # ─── ISRO Bhoonidhi ────────────────────────────────────────
    BHOONIDHI_USERNAME: str = ""
    BHOONIDHI_PASSWORD: str = ""

    # ─── JAXA ──────────────────────────────────────────────────
    JAXA_AUIG2_USER: str = ""
    JAXA_AUIG2_PASS: str = ""

    # ─── NASA Earthdata / USGS ─────────────────────────────────
    NASA_EARTHDATA_USER: str = ""
    NASA_EARTHDATA_PASS: str = ""
    USGS_USERNAME: str = ""
    USGS_PASSWORD: str = ""
    USGS_M2M_API_KEY: str = ""

    # ─── GEE ───────────────────────────────────────────────────
    GEE_SERVICE_ACCOUNT_KEY_PATH: str = ""

    # ─── Gemini ────────────────────────────────────────────────
    GEMINI_API_KEY: str = ""
    GEMINI_FLASH_RPM: int = 14
    GEMINI_PRO_RPM: int = 2

    # ─── Weather ───────────────────────────────────────────────
    OPENWEATHERMAP_API_KEY: str = ""

    # ─── PG Portal ─────────────────────────────────────────────
    PG_PORTAL_USER: str = ""
    PG_PORTAL_PASS: str = ""

    # ─── data.gov.in ───────────────────────────────────────────
    DATAGOVIN_API_KEY: str = ""

    # ─── Mapillary ─────────────────────────────────────────────
    MAPILLARY_ACCESS_TOKEN: str = ""

    # ─── NRSC ──────────────────────────────────────────────────
    NRSC_DATA_USERNAME: str = ""
    NRSC_DATA_PASSWORD: str = ""

    # ─── SMTP ──────────────────────────────────────────────────
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""

    # ─── MinIO ─────────────────────────────────────────────────
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minioadmin"
    MINIO_BUCKET: str = "pothole-data"

    # ─── Mapbox ────────────────────────────────────────────────
    VITE_MAPBOX_TOKEN: str = ""

    # ─── Detection defaults ────────────────────────────────────
    YOLO_CONFIDENCE_THRESHOLD: float = 0.55
    YOLO_NMS_IOU: float = 0.45
    TILE_SIZE: int = 640
    TILE_OVERLAP_PCT: float = 0.10
    ROAD_BUFFER_M: float = 50.0
    UTM_EPSG: int = 32644

    # ─── Confidence thresholds ─────────────────────────────────
    AUTO_FILE_THRESHOLD: float = 0.85
    REVIEW_THRESHOLD: float = 0.65
    CCTV_SSIM_SKIP: float = 0.98

    # ─── Escalation ───────────────────────────────────────────
    ESCALATION_L1_DAYS: int = 30
    ESCALATION_L2_DAYS: int = 60
    ESCALATION_L3_DAYS: int = 90

    # ─── Risk score weights ────────────────────────────────────
    RISK_SEVERITY_WEIGHT: float = 0.35
    RISK_ACCIDENT_WEIGHT: float = 0.30
    RISK_TRAFFIC_WEIGHT: float = 0.20
    RISK_GEOMETRY_WEIGHT: float = 0.15
    WEATHER_BOOST_MULTIPLIER: float = 1.8

    # ─── NodeODM ───────────────────────────────────────────────
    NODEODM_URL: str = "http://odm_worker:3000"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
