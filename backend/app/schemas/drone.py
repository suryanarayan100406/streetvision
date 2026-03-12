"""Drone mission schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DroneMissionCreate(BaseModel):
    mission_name: str
    source: str
    operator: str | None = None
    mission_date: date | None = None
    highway: str | None = None
    km_start: Decimal | None = None
    km_end: Decimal | None = None
    resolution_cm_px: Decimal | None = None


class DroneMissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mission_name: str | None = None
    source: str | None = None
    operator: str | None = None
    mission_date: date | None = None
    highway: str | None = None
    km_start: Decimal | None = None
    km_end: Decimal | None = None
    area_covered_sqkm: Decimal | None = None
    image_count: int | None = None
    resolution_cm_px: Decimal | None = None
    processing_status: str
    detection_count: int
    orthophoto_path: str | None = None
    submitted_at: datetime | None = None
    completed_at: datetime | None = None


class LiveDroneFeedCreate(BaseModel):
    rtsp_url: str
    drone_type: str | None = None
    operator: str | None = None
    highway: str | None = None
    km_start: Decimal | None = None
    km_end: Decimal | None = None
    expected_altitude_m: float | None = None
