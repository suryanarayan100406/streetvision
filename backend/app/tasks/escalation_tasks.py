"""Escalation check tasks: promote unresolved complaints to higher authority."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from app.tasks.celery_app import app
from app.database import async_session_factory

logger = structlog.get_logger(__name__)


@app.task(name="app.tasks.escalation_tasks.check_all_escalations", bind=True)
def check_all_escalations(self):
    """Daily task: check all open complaints for escalation eligibility."""

    async def _run():
        from app.models.complaint import Complaint

        async with async_session_factory() as db:
            result = await db.execute(
                select(Complaint).where(
                    Complaint.portal_status.notin_(["Resolved", "Closed"]),
                    Complaint.escalation_level < 3,
                )
            )
            complaints = result.scalars().all()

            escalated = 0
            for c in complaints:
                escalate_single_complaint.delay(c.id)
                escalated += 1

            return {"queued": escalated}

    return asyncio.get_event_loop().run_until_complete(_run())


@app.task(name="app.tasks.escalation_tasks.escalate_single_complaint", bind=True)
def escalate_single_complaint(self, complaint_id: int):
    """Evaluate and escalate a single complaint if it meets time thresholds."""

    async def _run():
        from app.models.complaint import Complaint
        from app.models.pothole import Pothole
        from app.services.escalation_engine import check_escalation

        async with async_session_factory() as db:
            result = await db.execute(
                select(Complaint).where(Complaint.id == complaint_id)
            )
            complaint = result.scalar_one_or_none()
            if not complaint:
                return {"error": "Complaint not found"}

            esc = check_escalation(complaint)
            if not esc["should_escalate"]:
                return {"complaint_id": complaint_id, "action": "no_escalation"}

            old_level = complaint.escalation_level
            complaint.escalation_level = esc["new_level"]
            complaint.escalated_at = datetime.now(timezone.utc)
            complaint.escalation_target = esc["target_authority"]

            # Mark pothole as critically overdue at level 3
            if esc["new_level"] >= 3:
                ph_result = await db.execute(
                    select(Pothole).where(Pothole.id == complaint.pothole_id)
                )
                pothole = ph_result.scalar_one_or_none()
                if pothole:
                    pothole.critically_overdue = True

            await db.commit()

            # Re-file complaint at higher authority
            from app.tasks.filing_tasks import file_complaint
            file_complaint.delay(complaint.pothole_id)

            logger.info(
                "escalated_complaint",
                complaint_id=complaint_id,
                old_level=old_level,
                new_level=esc["new_level"],
                target=esc["target_authority"],
            )
            return {
                "complaint_id": complaint_id,
                "old_level": old_level,
                "new_level": esc["new_level"],
            }

    return asyncio.get_event_loop().run_until_complete(_run())
