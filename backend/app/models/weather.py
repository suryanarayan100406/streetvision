"""Weather cache model."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, Date, DateTime, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class WeatherCache(Base):
    __tablename__ = "weather_cache"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    grid_cell_geom: Mapped[str | None] = mapped_column(Geometry("POLYGON", srid=4326))
    forecast_rain_48h_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    gfs_rain_7d_mm: Mapped[Decimal | None] = mapped_column(Numeric(7, 2))
    imd_warning_level: Mapped[str | None] = mapped_column(String(10))
    open_meteo_rain_48h_mm: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    forecast_date: Mapped[date | None] = mapped_column(Date)
    priority_boost_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_imd_response: Mapped[dict | None] = mapped_column(JSONB)
    raw_openmeteo_response: Mapped[dict | None] = mapped_column(JSONB)
