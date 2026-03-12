"""Satellite pipeline models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SatelliteJob(Base):
    __tablename__ = "satellite_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    highway: Mapped[str | None] = mapped_column(String(20))
    bbox: Mapped[dict | None] = mapped_column(JSONB)
    satellite_source: Mapped[str | None] = mapped_column(String(30))
    product_id: Mapped[str | None] = mapped_column(Text)
    download_date: Mapped[date | None] = mapped_column(Date)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    tile_count: Mapped[int | None] = mapped_column(Integer)
    detection_count: Mapped[int | None] = mapped_column(Integer)
    cloud_cover_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    processing_time_seconds: Mapped[int | None] = mapped_column(Integer)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SatelliteSource(Base):
    __tablename__ = "satellite_sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source_name: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(String(20))
    resolution_m: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    repeat_cycle_days: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    last_successful_download: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    credentials_configured: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[dict] = mapped_column(JSONB, server_default="{}")


class SatelliteSelectionLog(Base):
    __tablename__ = "satellite_selection_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    highway: Mapped[str | None] = mapped_column(String(20))
    selected_source: Mapped[str | None] = mapped_column(String(30))
    reason: Mapped[str | None] = mapped_column(Text)
    considered_sources: Mapped[dict | None] = mapped_column(JSONB)
    detection_cycle_date: Mapped[date | None] = mapped_column(Date)
    selected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SatelliteDownloadLog(Base):
    __tablename__ = "satellite_download_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str | None] = mapped_column(String(30))
    product_id: Mapped[str | None] = mapped_column(Text)
    highway: Mapped[str | None] = mapped_column(String(20))
    download_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    download_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    file_size_mb: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    success: Mapped[bool | None] = mapped_column(Boolean)
    error_message: Mapped[str | None] = mapped_column(Text)
    cloud_cover_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
