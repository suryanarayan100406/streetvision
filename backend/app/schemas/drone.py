"""Drone mission schemas."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DroneMissionCreate(BaseModel):
    mission_name: str
    operator: str | None = None
    flight_date: date | None = None
    area_bbox: dict | None = None
    image_count: int | None = None
    gsd_cm: float | None = None


class DroneMissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mission_name: str | None = None
    operator: str | None = None
    flight_date: date | None = None
    area_bbox: dict | None = None
    image_count: int | None = None
    gsd_cm: float | None = None
    processing_status: str
    odm_task_id: str | None = None
    orthophoto_path: str | None = None
    dsm_path: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class LiveDroneFeedCreate(BaseModel):
    rtsp_url: str
    operator: str | None = None
    expected_altitude_m: float | None = None
