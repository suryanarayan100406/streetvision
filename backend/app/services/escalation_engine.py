"""Escalation engine — 3-tier government escalation."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.complaint import Complaint
from app.models.pothole import Pothole
from app.models.settings import GovernmentContact

logger = structlog.get_logger(__name__)


async def check_escalation(db: AsyncSession, pothole_id: int) -> int | None:
    """Check if a pothole complaint needs escalation. Returns new level or None."""
    result = await db.execute(
        select(Complaint)
        .where(Complaint.pothole_id == pothole_id, Complaint.status == "FILED")
        .order_by(Complaint.filed_at.asc())
        .limit(1)
    )
    first_complaint = result.scalar_one_or_none()
    if first_complaint is None or first_complaint.filed_at is None:
        return None

    days_since = (datetime.now(timezone.utc) - first_complaint.filed_at).days
    current_level = first_complaint.escalation_level

    if days_since >= settings.ESCALATION_L3_DAYS and current_level < 3:
        return 3
    elif days_since >= settings.ESCALATION_L2_DAYS and current_level < 2:
        return 2
    elif days_since >= settings.ESCALATION_L1_DAYS and current_level < 1:
        return 1

    return None


async def get_authority_contact(db: AsyncSession, escalation_level: int) -> dict[str, str] | None:
    """Get government contact for escalation level."""
    result = await db.execute(
        select(GovernmentContact).where(GovernmentContact.escalation_level == escalation_level)
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        return None
    return {
        "authority_title": contact.authority_title,
        "email": contact.email,
        "department": contact.department or "",
    }


async def escalate_pothole(db: AsyncSession, pothole_id: int, new_level: int) -> dict[str, Any]:
    """Execute escalation for a pothole."""
    pothole_result = await db.execute(select(Pothole).where(Pothole.id == pothole_id))
    pothole = pothole_result.scalar_one_or_none()
    if pothole is None:
        return {"error": "Pothole not found"}

    # Mark as critically overdue at Level 3
    if new_level >= 3:
        pothole.critically_overdue = True

    await db.flush()

    await logger.ainfo(
        "pothole_escalated",
        pothole_id=pothole_id,
        new_level=new_level,
        critically_overdue=new_level >= 3,
    )

    return {
        "pothole_id": pothole_id,
        "new_level": new_level,
        "critically_overdue": new_level >= 3,
    }
