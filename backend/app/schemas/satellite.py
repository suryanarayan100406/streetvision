"""Satellite management schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SatelliteSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    source_type: str | None = None
    priority: int
    enabled: bool
    credentials: dict | None = None
    last_successful_at: datetime | None = None
    error_count: int


class SatelliteSourceUpdate(BaseModel):
    enabled: bool | None = None
    priority: int | None = None
    credentials: dict | None = None


class SatelliteJobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int | None = None
    status: str
    bbox: dict | None = None
    tiles_total: int
    tiles_processed: int
    detections_count: int
    error_message: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class SatelliteSelectionLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int | None = None
    candidates: dict | None = None
    selected_source: str | None = None
    reason: str | None = None
    created_at: datetime


class TestConnectionResult(BaseModel):
    success: bool
    product_count: int | None = None
    error: str | None = None


class OAMSearchRequest(BaseModel):
    bbox: str  # lon_min,lat_min,lon_max,lat_max
    min_resolution: float = 0.8
    limit: int = 50
    date_from: str | None = None  # YYYY-MM-DD
    date_to: str | None = None    # YYYY-MM-DD


class OAMSearchResponse(BaseModel):
    count: int
    samples: list[dict]


class OAMTriggerResponse(BaseModel):
    task_id: str
    source: str
    bbox: str


class SatelliteScenePreviewOut(BaseModel):
    product_id: str
    title: str | None = None
    preview_url: str | None = None
    asset_url: str | None = None
    captured_at: str | None = None
    gsd_m_per_px: float | None = None
    lat: float | None = None
    lon: float | None = None


class SatelliteSceneSearchRequest(BaseModel):
    source: str
    bbox: str  # lon_min,lat_min,lon_max,lat_max
    limit: int = 12
    max_cloud: float = 20.0
    date_from: str | None = None
    date_to: str | None = None
    forward_to_inference: bool = True


class SatelliteSceneSearchResponse(BaseModel):
    source: str
    count: int
    items: list[SatelliteScenePreviewOut]


class SatelliteScanLaunchResponse(BaseModel):
    task_id: str
    job_id: int
    source: str
    bbox: str


class SatelliteDownloadLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_id: int | None = None
    source_name: str | None = None
    product_id: str | None = None
    file_path: str | None = None
    file_size_mb: float | None = None
    downloaded_at: datetime
    preview_url: str | None = None


class SatelliteCredentialStatusItem(BaseModel):
    source: str
    keys_required: list[str]
    keys_missing: list[str]
    configured: bool


class SatelliteCredentialStatusResponse(BaseModel):
    items: list[SatelliteCredentialStatusItem]
