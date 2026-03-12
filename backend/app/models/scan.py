"""Scan model — repair verification records."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import BigInteger, Date, Numeric, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pothole_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("potholes.id"), nullable=False)
    scan_date: Mapped[date] = mapped_column(Date, nullable=False)
    before_image_path: Mapped[str | None] = mapped_column(Text)
    after_image_path: Mapped[str | None] = mapped_column(Text)
    ssim_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    siamese_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    repair_status: Mapped[str | None] = mapped_column(String(20))
    scan_source: Mapped[str | None] = mapped_column(String(30))
    scan_satellite: Mapped[str | None] = mapped_column(String(30))

    pothole: Mapped["Pothole"] = relationship("Pothole", back_populates="scans")  # noqa: F821
