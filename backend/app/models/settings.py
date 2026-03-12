"""System settings, contacts, gamification, and model registry."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str | None] = mapped_column(Text)
    value_type: Mapped[str | None] = mapped_column(String(20))
    last_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    modified_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("admin_users.id"))
    description: Mapped[str | None] = mapped_column(Text)


class GovernmentContact(Base):
    __tablename__ = "government_contacts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    authority_title: Mapped[str] = mapped_column(Text, nullable=False)
    escalation_level: Mapped[int | None] = mapped_column(Integer)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PWDOfficer(Base):
    __tablename__ = "pwd_officers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(Text)
    designation: Mapped[str | None] = mapped_column(Text)
    district: Mapped[str | None] = mapped_column(Text)
    highway_zone: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class GamificationPoints(Base):
    __tablename__ = "gamification_points"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    report_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("source_reports.id"))
    points_earned: Mapped[int | None] = mapped_column(Integer)
    point_type: Mapped[str | None] = mapped_column(String(20))
    district: Mapped[str | None] = mapped_column(Text)
    earned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    model_type: Mapped[str | None] = mapped_column(String(30))
    model_path: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str | None] = mapped_column(String(20))
    val_map50: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    val_map75: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    false_positive_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    training_images: Mapped[int | None] = mapped_column(Integer)
    trained_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    active: Mapped[bool] = mapped_column(Boolean, default=False)
