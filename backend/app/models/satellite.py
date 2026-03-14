"""Satellite pipeline models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SatelliteJob(Base):
    __tablename__ = "satellite_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    bbox: Mapped[dict | None] = mapped_column(JSONB)
    tiles_total: Mapped[int] = mapped_column(Integer, default=0)
    tiles_processed: Mapped[int] = mapped_column(Integer, default=0)
    tiles_forwarded_to_inference: Mapped[int] = mapped_column(Integer, default=0)
    monitoring_only_tiles: Mapped[int] = mapped_column(Integer, default=0)
    detections_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SatelliteSource(Base):
    __tablename__ = "satellite_sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(20))
    priority: Mapped[int] = mapped_column(Integer, default=50)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    credentials: Mapped[dict | None] = mapped_column(JSONB)
    last_successful_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_count: Mapped[int] = mapped_column(Integer, default=0)


class SatelliteSelectionLog(Base):
    __tablename__ = "satellite_selection_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[int | None] = mapped_column(BigInteger)
    candidates: Mapped[dict | None] = mapped_column(JSONB)
    selected_source: Mapped[str | None] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SatelliteDownloadLog(Base):
    __tablename__ = "satellite_download_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[int | None] = mapped_column(BigInteger)
    source_name: Mapped[str | None] = mapped_column(String(100))
    product_id: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(Text)
    file_size_mb: Mapped[float | None] = mapped_column(Float)
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
