"""Task history model for completed Celery tasks."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TaskHistory(Base):
    __tablename__ = "task_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    celery_task_id: Mapped[str | None] = mapped_column(PG_UUID(as_uuid=True))
    task_name: Mapped[str | None] = mapped_column(String(100))
    queue: Mapped[str | None] = mapped_column(String(50))
    pothole_id: Mapped[int | None] = mapped_column(BigInteger)
    args_summary: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(String(20))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Decimal | None] = mapped_column(Numeric(10, 3))
    error_message: Mapped[str | None] = mapped_column(Text)
