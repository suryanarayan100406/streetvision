"""Source report — individual evidence records from all sources."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, String, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SourceReport(Base):
    __tablename__ = "source_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pothole_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("potholes.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    raw_payload: Mapped[dict | None] = mapped_column(JSONB)
    image_url: Mapped[str | None] = mapped_column(Text)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confidence_boost: Mapped[float | None] = mapped_column(Float, default=0.0)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pothole: Mapped["Pothole"] = relationship("Pothole", back_populates="source_reports")  # noqa: F821
