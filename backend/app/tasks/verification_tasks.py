"""Repair verification and re-scan tasks."""

from __future__ import annotations

import asyncio
from datetime import datetime, date, timezone

import structlog
from sqlalchemy import select, or_, and_, text

from app.tasks.celery_app import app
from app.database import async_session_factory
from app.models.task import TaskHistory

logger = structlog.get_logger(__name__)


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


@app.task(name="app.tasks.verification_tasks.verify_all_repairs", bind=True)
def verify_all_repairs(self):
    """Daily task: verify escalated complaints due for 14-day re-check."""

    async def _verify():
        from datetime import timedelta

        from app.models.complaint import Complaint
        from app.models.pothole import Pothole

        async with async_session_factory() as db:
            cutoff_dt = datetime.now(timezone.utc) - timedelta(days=14)
            result = await db.execute(
                select(Pothole.id)
                .join(Complaint, Complaint.pothole_id == Pothole.id)
                .where(
                    or_(
                        Complaint.portal_status.is_(None),
                        Complaint.portal_status.notin_(["Resolved", "Closed"]),
                    ),
                    Complaint.escalation_level >= 0,
                    or_(
                        Complaint.escalated_at <= cutoff_dt,
                        and_(Complaint.escalated_at.is_(None), Complaint.filed_at <= cutoff_dt),
                    ),
                    Pothole.status.in_(["Detected", "Confirmed", "Unresolved"]),
                )
                .distinct()
                .limit(200)
            )
            pothole_ids = [int(r[0]) for r in result.all()]

            queued = 0
            for pothole_id in pothole_ids:
                verify_single_pothole.delay(pothole_id)
                queued += 1

            payload = {"queued": queued, "pothole_ids": pothole_ids}
            await _record_history(
                "verify_all_repairs",
                getattr(self.request, "id", None),
                "SUCCESS",
                payload,
            )

            return payload

    return asyncio.get_event_loop().run_until_complete(_verify())


@app.task(name="app.tasks.verification_tasks.verify_single_pothole", bind=True)
def verify_single_pothole(self, pothole_id: int):
    """Verify repair status for a single pothole."""

    async def _verify():
        from app.models.complaint import Complaint
        from app.models.pothole import Pothole
        from app.models.source_report import SourceReport
        from app.models.settings import ModelRegistry
        from app.services.repair_verifier import verify_repair
        from app.tasks.escalation_tasks import escalate_single_complaint

        async with async_session_factory() as db:
            result = await db.execute(select(Pothole).where(Pothole.id == pothole_id))
            pothole = result.scalar_one_or_none()
            if not pothole:
                return {"error": "No pothole found"}

            complaint_result = await db.execute(
                select(Complaint)
                .where(
                    Complaint.pothole_id == pothole_id,
                    or_(Complaint.portal_status.is_(None), Complaint.portal_status.notin_(["Resolved", "Closed"])),
                )
                .order_by(Complaint.created_at.desc())
                .limit(1)
            )
            complaint = complaint_result.scalar_one_or_none()
            if not complaint:
                return {"error": "No open complaint"}

            before_result = await db.execute(
                select(SourceReport.image_url)
                .where(
                    SourceReport.pothole_id == pothole_id,
                    SourceReport.image_url.is_not(None),
                )
                .order_by(SourceReport.created_at.asc())
                .limit(1)
            )
            before_path = before_result.scalar_one_or_none() or pothole.image_path

            latest_result = await db.execute(
                select(SourceReport.image_url)
                .where(
                    SourceReport.pothole_id == pothole_id,
                    SourceReport.image_url.is_not(None),
                )
                .order_by(SourceReport.created_at.desc())
                .limit(1)
            )
            latest_source_image = latest_result.scalar_one_or_none()

            latest_scan_result = await db.execute(
                text(
                    """
                    SELECT after_image_path
                    FROM scans
                    WHERE pothole_id = :pothole_id
                    ORDER BY id DESC
                    LIMIT 1
                    """
                ),
                {"pothole_id": pothole_id},
            )
            latest_scan_row = latest_scan_result.first()
            latest_scan_image = latest_scan_row[0] if latest_scan_row else None

            after_path = latest_source_image or latest_scan_image
            if after_path == before_path:
                after_path = latest_scan_image if latest_scan_image and latest_scan_image != before_path else None

            if not after_path:
                return {"error": "No after image available"}

            active_verify_model_q = await db.execute(
                select(ModelRegistry)
                .where(
                    ModelRegistry.model_type == "VERIFICATION",
                    ModelRegistry.is_active.is_(True),
                )
                .order_by(ModelRegistry.id.desc())
                .limit(1)
            )
            active_verify_model = active_verify_model_q.scalar_one_or_none()

            repair_result = await verify_repair(
                before_path=before_path,
                after_path=after_path,
                siamese_model_path=active_verify_model.weights_path if active_verify_model else None,
            )

            await db.execute(
                text(
                    """
                    INSERT INTO scans
                    (pothole_id, scan_date, before_image_path, after_image_path, ssim_score, siamese_score, repair_status, scan_source)
                    VALUES
                    (:pothole_id, :scan_date, :before_image_path, :after_image_path, :ssim_score, :siamese_score, :repair_status, :scan_source)
                    """
                ),
                {
                    "pothole_id": pothole_id,
                    "scan_date": date.today(),
                    "before_image_path": before_path,
                    "after_image_path": after_path,
                    "ssim_score": repair_result.get("ssim_score"),
                    "siamese_score": repair_result.get("siamese_score"),
                    "repair_status": repair_result["repair_status"],
                    "scan_source": "AUTO_REVERIFY",
                },
            )

            pothole.last_scan_date = datetime.now(timezone.utc)
            pothole.last_repair_status = repair_result["repair_status"]

            if repair_result["repair_status"] == "Repaired":
                pothole.critically_overdue = False
                pothole.status = "Resolved"
                complaint.portal_status = "Resolved"
                complaint.resolved_at = datetime.now(timezone.utc)
            else:
                pothole.status = "Unresolved"
                complaint.portal_status = "Unresolved"

            await db.commit()

            if repair_result["repair_status"] != "Repaired":
                escalate_single_complaint.delay(complaint.id)

            payload = {
                "pothole_id": pothole_id,
                "status": repair_result["repair_status"],
                "ssim_score": repair_result.get("ssim_score"),
                "siamese_score": repair_result.get("siamese_score"),
            }
            await _record_history(
                "verify_single_pothole",
                getattr(self.request, "id", None),
                "SUCCESS",
                payload,
            )
            return payload

    return asyncio.get_event_loop().run_until_complete(_verify())
