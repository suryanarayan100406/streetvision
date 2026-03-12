"""Complaint model — PG Portal filed complaints."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Complaint(Base):
    __tablename__ = "complaints"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pothole_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("potholes.id", ondelete="CASCADE"), nullable=False)
    complaint_text: Mapped[str] = mapped_column(Text, nullable=False)
    portal_ref: Mapped[str | None] = mapped_column(String(100))
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rain_flag: Mapped[bool | None] = mapped_column(Boolean)
    gemini_model: Mapped[str | None] = mapped_column(String(50))
    filing_proof_path: Mapped[str | None] = mapped_column(Text)
    filing_source: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    pothole: Mapped["Pothole"] = relationship("Pothole", back_populates="complaints")  # noqa: F821
