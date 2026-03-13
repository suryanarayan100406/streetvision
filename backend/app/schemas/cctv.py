"""CCTV camera schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CCTVNodeCreate(BaseModel):
    name: str
    rtsp_url: str
    latitude: float | None = None
    longitude: float | None = None
    nh_number: str | None = None
    chainage_km: float | None = None
    perspective_matrix: dict | None = None


class CCTVNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    rtsp_url: str
    latitude: float | None = None
    longitude: float | None = None
    nh_number: str | None = None
    chainage_km: float | None = None
    perspective_matrix: dict | None = None
    is_active: bool
    last_frame_at: datetime | None = None


class CCTVNodeUpdate(BaseModel):
    name: str | None = None
    rtsp_url: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    nh_number: str | None = None
    chainage_km: float | None = None
    perspective_matrix: dict | None = None
    is_active: bool | None = None


class CCTVTestResult(BaseModel):
    success: bool
    frame_captured: bool = False
    error: str | None = None
    thumbnail_path: str | None = None


class HomographyCalibration(BaseModel):
    src_points: list[list[float]]
    dst_points: list[list[float]]
