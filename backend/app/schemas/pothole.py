"""Pothole request/response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PotholeBase(BaseModel):
    latitude: float
    longitude: float
    severity: str | None = None
    confidence_score: float | None = None
    risk_score: float | None = None
    status: str | None = None
    nh_number: str | None = None
    district: str | None = None


class PotholeCreate(PotholeBase):
    image_path: str | None = None


class PotholeOut(PotholeBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    image_path: str | None = None
    detected_at: datetime | None = None


class PotholeDetail(PotholeOut):
    estimated_area_m2: float | None = None
    estimated_depth_cm: float | None = None
    estimated_diameter_m: float | None = None
    complaints: list[ComplaintOut] = []
    source_reports: list[SourceReportOut] = []


class ComplaintOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pothole_id: int
    complaint_text: str | None = None
    portal_ref: str | None = None
    filed_at: datetime | None = None
    portal_status: str | None = None
    escalation_level: int
    filing_proof_path: str | None = None


class SourceReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_type: str
    captured_at: datetime | None = None
    image_url: str | None = None
    confidence_boost: float | None = None


class PotholeListParams(BaseModel):
    severity: str | None = None
    nh_number: str | None = None
    status: str | None = None
    min_risk: float | None = None
    bbox: str | None = None
    offset: int = 0
    limit: int = 50
