"""Escalation module tasks: portal sync + timed escalation of unresolved complaints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import select, or_

from app.tasks.celery_app import app
from app.database import async_session_factory
from app.models.task import TaskHistory

logger = structlog.get_logger(__name__)


ESCALATION_TARGETS = {
    1: "Executive Engineer, PWD Roads Division",
    2: "District Collector",
    3: "Principal Secretary, Public Works Department",
}


def _open_status_filter():
    from app.models.complaint import Complaint

    return or_(
        Complaint.portal_status.is_(None),
        Complaint.portal_status.notin_(["Resolved", "Closed"]),
    )


async def _record_history(task_name: str, task_id: str | None, status: str, result: dict):
    async with async_session_factory() as db:
        row = TaskHistory(
            task_name=task_name,
            task_id=task_id,
            status=status,
            result=result,
            duration_seconds=0.0,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(row)
        await db.commit()


@app.task(name="app.tasks.escalation_tasks.sync_detected_potholes_to_portal", bind=True)
def sync_detected_potholes_to_portal(self, limit: int = 200):
    """Queue portal complaint filing for all detected/confirmed potholes with no complaint yet."""

    async def _run():
        from app.models.complaint import Complaint
        from app.models.pothole import Pothole
        from app.tasks.filing_tasks import file_complaint

        async with async_session_factory() as db:
            complaint_subq = select(Complaint.pothole_id).distinct().subquery()

            result = await db.execute(
                select(Pothole.id)
                .where(
                    Pothole.status.in_(["Detected", "Confirmed"]),
                    ~Pothole.id.in_(select(complaint_subq.c.pothole_id)),
                )
                .order_by(Pothole.detected_at.asc())
                .limit(limit)
            )
            pothole_ids = [int(r[0]) for r in result.all()]

            for pothole_id in pothole_ids:
                file_complaint.delay(pothole_id)

        payload = {"queued": len(pothole_ids), "pothole_ids": pothole_ids}
        await _record_history(
            "sync_detected_potholes_to_portal",
            getattr(self.request, "id", None),
            "SUCCESS",
            payload,
        )
        return payload

    return asyncio.get_event_loop().run_until_complete(_run())


@app.task(name="app.tasks.escalation_tasks.check_all_escalations", bind=True)
def check_all_escalations(self):
    """Daily task: sync detected potholes + check unresolved complaints for escalation."""

    async def _run():
        from app.models.complaint import Complaint

        sync_detected_potholes_to_portal.delay()

        async with async_session_factory() as db:
            result = await db.execute(
                select(Complaint).where(
                    _open_status_filter(),
                    Complaint.escalation_level < 3,
                )
            )
            complaints = result.scalars().all()

            queued = 0
            for c in complaints:
                escalate_single_complaint.delay(c.id)
                queued += 1

            payload = {"queued": queued}
            await _record_history(
                "check_all_escalations",
                getattr(self.request, "id", None),
                "SUCCESS",
                payload,
            )

            return payload

    return asyncio.get_event_loop().run_until_complete(_run())


@app.task(name="app.tasks.escalation_tasks.escalate_single_complaint", bind=True)
def escalate_single_complaint(self, complaint_id: int):
    """Escalate unresolved complaint after 14 days and re-file to next authority."""

    async def _run():
        from app.models.complaint import Complaint
        from app.models.pothole import Pothole
        from app.tasks.filing_tasks import file_complaint

        async with async_session_factory() as db:
            result = await db.execute(
                select(Complaint).where(Complaint.id == complaint_id)
            )
            complaint = result.scalar_one_or_none()
            if not complaint:
                return {"error": "Complaint not found"}

            if complaint.portal_status in ("Resolved", "Closed"):
                return {"complaint_id": complaint_id, "action": "already_resolved"}

            if (complaint.escalation_level or 0) >= 3:
                ph_result = await db.execute(
                    select(Pothole).where(Pothole.id == complaint.pothole_id)
                )
                pothole = ph_result.scalar_one_or_none()
                if pothole:
                    pothole.critically_overdue = True
                    await db.commit()
                return {"complaint_id": complaint_id, "action": "at_max_level"}

            baseline_time = complaint.escalated_at or complaint.filed_at or complaint.created_at
            if baseline_time is None:
                return {"complaint_id": complaint_id, "action": "missing_dates"}

            due_after = baseline_time + timedelta(days=14)
            if datetime.now(timezone.utc) < due_after:
                return {
                    "complaint_id": complaint_id,
                    "action": "not_due",
                    "due_at": due_after.isoformat(),
                }

            old_level = int(complaint.escalation_level or 0)
            new_level = min(old_level + 1, 3)

            complaint.escalation_level = new_level
            complaint.escalated_at = datetime.now(timezone.utc)
            complaint.escalation_target = ESCALATION_TARGETS.get(new_level)
            complaint.portal_status = "ESCALATED"

            # Mark pothole as critically overdue at level 3
            if new_level >= 3:
                ph_result = await db.execute(
                    select(Pothole).where(Pothole.id == complaint.pothole_id)
                )
                pothole = ph_result.scalar_one_or_none()
                if pothole:
                    pothole.critically_overdue = True

            await db.commit()

            # Re-file complaint at higher authority
            file_complaint.delay(complaint.pothole_id)

            logger.info(
                "escalated_complaint",
                complaint_id=complaint_id,
                old_level=old_level,
                new_level=new_level,
                target=complaint.escalation_target,
            )

            await _record_history(
                "escalate_single_complaint",
                getattr(self.request, "id", None),
                "SUCCESS",
                {
                    "complaint_id": complaint_id,
                    "old_level": old_level,
                    "new_level": new_level,
                    "target": complaint.escalation_target,
                },
            )
            return {
                "complaint_id": complaint_id,
                "old_level": old_level,
                "new_level": new_level,
            }

    return asyncio.get_event_loop().run_until_complete(_run())
