"""Mobile app schemas."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class VisualReport(BaseModel):
    latitude: float
    longitude: float
    speed_kmh: float
    heading: float | None = None
    altitude: float | None = None
    accuracy_m: float | None = None
    device_id: UUID
    jolt_magnitude: Decimal | None = None


class VibrationReport(BaseModel):
    latitude: float
    longitude: float
    speed_kmh: float
    jolt_magnitude: Decimal
    device_id: UUID
    heading: float | None = None


class LeaderboardEntry(BaseModel):
    district: str
    device_id_short: str
    total_points: int
    visual_count: int
    pocket_count: int
    rank: int


class MobileReportResponse(BaseModel):
    report_id: int
    points_earned: int
    message: str = "Report received"
