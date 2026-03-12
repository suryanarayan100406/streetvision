"""Satellite management schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class SatelliteSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_name: str
    display_name: str | None = None
    source_type: str | None = None
    resolution_m: Decimal | None = None
    repeat_cycle_days: int | None = None
    status: str
    last_successful_download: datetime | None = None
    last_attempt: datetime | None = None
    last_error: str | None = None
    credentials_configured: bool
    config: dict


class SatelliteSourceUpdate(BaseModel):
    status: str | None = None
    cloud_cover_threshold: float | None = None
    schedule_cron: str | None = None
    highway_filter: list[str] | None = None
    tile_size: int | None = None
    overlap_pct: float | None = None
    config: dict | None = None


class SatelliteJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    highway: str | None = None
    satellite_source: str | None = None
    product_id: str | None = None
    download_date: datetime | None = None
    processed: bool
    tile_count: int | None = None
    detection_count: int | None = None
    cloud_cover_pct: Decimal | None = None
    processing_time_seconds: int | None = None


class SatelliteSelectionLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    highway: str | None = None
    selected_source: str | None = None
    reason: str | None = None
    considered_sources: dict | None = None
    detection_cycle_date: datetime | None = None
    selected_at: datetime


class TestConnectionResult(BaseModel):
    success: bool
    product_count: int | None = None
    error: str | None = None
