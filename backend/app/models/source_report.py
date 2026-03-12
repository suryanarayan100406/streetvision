"""Source report — individual evidence records from all sources."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, Numeric, String, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SourceReport(Base):
    __tablename__ = "source_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pothole_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("potholes.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False)
    report_type: Mapped[str | None] = mapped_column(String(20))
    jolt_magnitude: Mapped[Decimal | None] = mapped_column(Numeric(5, 3))
    gps: Mapped[str | None] = mapped_column(Geometry("POINT", srid=4326))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    image_path: Mapped[str | None] = mapped_column(Text)
    confidence_boost: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    device_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    mapillary_image_key: Mapped[str | None] = mapped_column(Text)
    drone_mission_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("drone_missions.id"))

    pothole: Mapped["Pothole"] = relationship("Pothole", back_populates="source_reports")  # noqa: F821
