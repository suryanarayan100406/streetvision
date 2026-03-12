"""Pothole model — central entity of the system."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Pothole(Base):
    __tablename__ = "potholes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    geom: Mapped[str] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(8))
    area_sqm: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    depth_cm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    base_risk_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    confidence_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    source_primary: Mapped[str | None] = mapped_column(String(30))
    satellite_source: Mapped[str | None] = mapped_column(String(30))
    image_path: Mapped[str | None] = mapped_column(Text)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    road_name: Mapped[str | None] = mapped_column(Text)
    km_marker: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    district: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, default="Chhattisgarh")
    nearest_landmark: Mapped[str | None] = mapped_column(Text)
    rain_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    imd_warning_level: Mapped[str | None] = mapped_column(String(10))
    sar_first_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    alos2_detection_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    eos04_moisture_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    thermal_stress_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    drone_mission_id: Mapped[int | None] = mapped_column(BigInteger)
    critically_overdue: Mapped[bool] = mapped_column(Boolean, default=False)
    last_scan_date: Mapped[datetime | None] = mapped_column(DateTime)
    last_repair_status: Mapped[str | None] = mapped_column(String(20))
    detection_metadata: Mapped[dict] = mapped_column(JSONB, server_default="{}")

    # Relationships
    complaints: Mapped[list["Complaint"]] = relationship("Complaint", back_populates="pothole", cascade="all, delete-orphan")  # noqa: F821
    scans: Mapped[list["Scan"]] = relationship("Scan", back_populates="pothole")  # noqa: F821
    source_reports: Mapped[list["SourceReport"]] = relationship("SourceReport", back_populates="pothole")  # noqa: F821
