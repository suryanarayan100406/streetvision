"""Drone mission records."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Integer, Float, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DroneMission(Base):
    __tablename__ = "drone_missions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mission_name: Mapped[str | None] = mapped_column(Text)
    operator: Mapped[str | None] = mapped_column(Text)
    flight_date: Mapped[date | None] = mapped_column(Date)
    area_bbox: Mapped[dict | None] = mapped_column(JSONB)
    image_count: Mapped[int | None] = mapped_column(Integer)
    gsd_cm: Mapped[float | None] = mapped_column(Float)
    processing_status: Mapped[str] = mapped_column(String(30), default="PENDING")
    odm_task_id: Mapped[str | None] = mapped_column(String(100))
    orthophoto_path: Mapped[str | None] = mapped_column(Text)
    dsm_path: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
