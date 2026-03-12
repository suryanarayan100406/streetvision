"""Pothole request/response schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PotholeBase(BaseModel):
    latitude: float
    longitude: float
    severity: str | None = None
    area_sqm: Decimal | None = None
    depth_cm: Decimal | None = None
    road_name: str | None = None
    km_marker: Decimal | None = None
    district: str | None = None


class PotholeCreate(PotholeBase):
    source_primary: str
    satellite_source: str | None = None
    image_path: str | None = None


class PotholeOut(PotholeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    risk_score: Decimal | None = None
    base_risk_score: Decimal | None = None
    confidence_score: Decimal | None = None
    source_primary: str | None = None
    satellite_source: str | None = None
    image_path: str | None = None
    detected_at: datetime
    state: str
    nearest_landmark: str | None = None
    rain_flag: bool
    imd_warning_level: str | None = None
    sar_first_detected_at: datetime | None = None
    critically_overdue: bool
    last_repair_status: str | None = None


class PotholeDetail(PotholeOut):
    alos2_detection_date: datetime | None = None
    eos04_moisture_flag: bool
    thermal_stress_flag: bool
    drone_mission_id: int | None = None
    last_scan_date: datetime | None = None
    detection_metadata: dict = {}
    complaints: list[ComplaintOut] = []
    source_reports: list[SourceReportOut] = []


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pothole_id: int
    complaint_text: str
    portal_ref: str | None = None
    filed_at: datetime | None = None
    status: str
    escalation_level: int
    gemini_model: str | None = None
    filing_proof_path: str | None = None


class SourceReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    report_type: str | None = None
    jolt_magnitude: Decimal | None = None
    timestamp: datetime
    image_path: str | None = None
    confidence_boost: Decimal | None = None


class PotholeListParams(BaseModel):
    highway: str | None = None
    severity: str | None = None
    min_risk: float | None = None
    max_risk: float | None = None
    rain_flag: bool | None = None
    critically_overdue: bool | None = None
    page: int = 1
    per_page: int = 50
