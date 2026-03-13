"""Pothole model — central entity of the system."""

from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Pothole(Base):
    __tablename__ = "potholes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[str] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    severity: Mapped[str | None] = mapped_column(String(20))
    confidence_score: Mapped[float | None] = mapped_column(Float, default=0.0)
    risk_score: Mapped[float | None] = mapped_column(Float, default=0.0)
    status: Mapped[str | None] = mapped_column(String(30), default="Detected")
    nh_number: Mapped[str | None] = mapped_column(String(20))
    chainage_km: Mapped[float | None] = mapped_column(Float)
    district: Mapped[str | None] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(Text)
    estimated_area_m2: Mapped[float | None] = mapped_column(Float)
    estimated_depth_cm: Mapped[float | None] = mapped_column(Float)
    estimated_diameter_m: Mapped[float | None] = mapped_column(Float)
    image_path: Mapped[str | None] = mapped_column(Text)
    mask_path: Mapped[str | None] = mapped_column(Text)
    rain_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    thermal_stress_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    moisture_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    near_junction: Mapped[bool] = mapped_column(Boolean, default=False)
    on_curve: Mapped[bool] = mapped_column(Boolean, default=False)
    on_blind_spot: Mapped[bool] = mapped_column(Boolean, default=False)
    aadt: Mapped[int] = mapped_column(Integer, default=0)
    last_repair_status: Mapped[str | None] = mapped_column(String(30))
    last_scan_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    critically_overdue: Mapped[bool] = mapped_column(Boolean, default=False)
    merged_into_id: Mapped[int | None] = mapped_column(Integer)
    detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    complaints: Mapped[list["Complaint"]] = relationship("Complaint", back_populates="pothole", cascade="all, delete-orphan")  # noqa: F821
    scans: Mapped[list["Scan"]] = relationship("Scan", back_populates="pothole")  # noqa: F821
    source_reports: Mapped[list["SourceReport"]] = relationship("SourceReport", back_populates="pothole")  # noqa: F821
