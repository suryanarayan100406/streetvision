"""Road segments and accident models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, Date, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class RoadSegment(Base):
    __tablename__ = "road_segments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    geom: Mapped[str] = mapped_column(Geometry("LINESTRING", srid=4326), nullable=False)
    highway: Mapped[str | None] = mapped_column(String(20))
    km_start: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    km_end: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    segment_length_km: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    accident_count: Mapped[int] = mapped_column(Integer, default=0)
    traffic_volume_category: Mapped[str | None] = mapped_column(String(10))
    has_curves: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blind_spot: Mapped[bool] = mapped_column(Boolean, default=False)
    slope_angle_degrees: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    priority_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    thermal_stress_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    junction_within_200m: Mapped[bool] = mapped_column(Boolean, default=False)
    data_source: Mapped[str | None] = mapped_column(String(20))


class RoadAccident(Base):
    __tablename__ = "road_accidents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    geom: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
    highway: Mapped[str | None] = mapped_column(String(20))
    km_marker: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    accident_date: Mapped[date | None] = mapped_column(Date)
    severity: Mapped[str | None] = mapped_column(String(20))
    casualty_count: Mapped[int | None] = mapped_column(Integer)
    vehicle_count: Mapped[int | None] = mapped_column(Integer)
    data_source: Mapped[str | None] = mapped_column(String(30))
    year: Mapped[int | None] = mapped_column(Integer)
