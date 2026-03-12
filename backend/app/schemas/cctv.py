"""CCTV camera schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CCTVNodeCreate(BaseModel):
    camera_id: str
    latitude: float
    longitude: float
    rtsp_url: str
    highway: str | None = None
    km_marker: Decimal | None = None
    atms_zone: str | None = None
    camera_angle_degrees: Decimal | None = None
    mounting_height_m: Decimal | None = None
    description: str | None = None


class CCTVNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    camera_id: str
    highway: str | None = None
    km_marker: Decimal | None = None
    atms_zone: str | None = None
    last_active: datetime | None = None
    status: str
    mounting_height_m: Decimal | None = None
    camera_angle_degrees: Decimal | None = None


class CCTVNodeUpdate(BaseModel):
    rtsp_url: str | None = None
    highway: str | None = None
    km_marker: Decimal | None = None
    atms_zone: str | None = None
    status: str | None = None
    camera_angle_degrees: Decimal | None = None
    mounting_height_m: Decimal | None = None


class CCTVTestResult(BaseModel):
    success: bool
    frame_captured: bool = False
    error: str | None = None
    thumbnail_path: str | None = None


class HomographyCalibration(BaseModel):
    image_points: list[list[float]]  # 4 points [[x,y], ...]
    real_width_m: float = 3.5
    real_length_m: float = 5.0
