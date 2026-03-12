"""CCTV camera nodes."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CCTVNode(Base):
    __tablename__ = "cctv_nodes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    camera_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    geom: Mapped[str] = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    highway: Mapped[str | None] = mapped_column(String(20))
    km_marker: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    rtsp_url: Mapped[str | None] = mapped_column(Text)
    atms_zone: Mapped[str | None] = mapped_column(String(30))
    perspective_matrix: Mapped[dict | None] = mapped_column(JSONB)
    mounting_height_m: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    camera_angle_degrees: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    last_active: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
