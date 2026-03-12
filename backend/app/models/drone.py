"""Drone mission records."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DroneMission(Base):
    __tablename__ = "drone_missions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mission_name: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(30))
    operator: Mapped[str | None] = mapped_column(Text)
    mission_date: Mapped[date | None] = mapped_column(Date)
    highway: Mapped[str | None] = mapped_column(String(20))
    km_start: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    km_end: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    area_covered_sqkm: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    image_count: Mapped[int | None] = mapped_column(Integer)
    resolution_cm_px: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    processing_status: Mapped[str] = mapped_column(String(20), default="UPLOADED")
    detection_count: Mapped[int] = mapped_column(Integer, default=0)
    orthophoto_path: Mapped[str | None] = mapped_column(Text)
    dsm_path: Mapped[str | None] = mapped_column(Text)
    nodeodm_task_id: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
