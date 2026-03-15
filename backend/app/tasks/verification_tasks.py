"""Repair verification and re-scan tasks."""

from __future__ import annotations

import asyncio
from datetime import datetime, date, timezone

import structlog
from sqlalchemy import select, or_, and_, text, func

from app.tasks.celery_app import app
from app.database import async_session_factory
from app.models.task import TaskHistory

logger = structlog.get_logger(__name__)


SOURCE_FRESHNESS_PRIORITY = {
    "DRONE": 100,
    "OAM_DRONE": 95,
    "CCTV": 90,
    "CARTOSAT-3": 85,
    "CARTOSAT-2S": 80,
    "RISAT-2B": 75,
    "EOS-04": 74,
    "SENTINEL-2": 60,
    "SENTINEL-1": 58,
    "LANDSAT-9": 45,
    "LANDSAT-8": 44,
}


def _source_rank(source_type: str | None) -> int:
    return SOURCE_FRESHNESS_PRIORITY.get(str(source_type or "").upper(), 10)


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


async def _queue_nearby_cctv_refresh(db, pothole_id: int, latitude: float | None, longitude: float | None) -> list[int]:
    from app.models.cctv import CCTVNode
    from app.tasks.cctv_tasks import process_cctv_node

    if latitude is None or longitude is None:
        return []

    result = await db.execute(
        select(CCTVNode.id)
        .where(
            CCTVNode.is_active.is_(True),
            CCTVNode.latitude.is_not(None),
            CCTVNode.longitude.is_not(None),
            func.abs(CCTVNode.latitude - latitude) <= 0.03,
            func.abs(CCTVNode.longitude - longitude) <= 0.03,
        )
        .order_by(
            (func.abs(CCTVNode.latitude - latitude) + func.abs(CCTVNode.longitude - longitude)).asc()
        )
        .limit(3)
    )
    node_ids = [int(r[0]) for r in result.all()]
    for node_id in node_ids:
        process_cctv_node.delay(node_id)
    return node_ids


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

            baseline_time = complaint.escalated_at or complaint.filed_at or complaint.created_at

            source_rows_result = await db.execute(
                select(
                    SourceReport.image_url,
                    SourceReport.source_type,
                    func.coalesce(SourceReport.captured_at, SourceReport.created_at).label("evidence_time"),
                )
                .where(
                    SourceReport.pothole_id == pothole_id,
                    SourceReport.image_url.is_not(None),
                )
                .order_by(func.coalesce(SourceReport.captured_at, SourceReport.created_at).asc())
            )
            source_rows = source_rows_result.all()

            before_candidates = [
                row for row in source_rows if baseline_time is None or row.evidence_time is None or row.evidence_time <= baseline_time
            ]
            if before_candidates:
                before_choice = sorted(
                    before_candidates,
                    key=lambda row: (_source_rank(row.source_type), row.evidence_time or datetime.min.replace(tzinfo=timezone.utc)),
                    reverse=True,
                )[0]
                before_path = before_choice.image_url
            else:
                before_path = (source_rows[0].image_url if source_rows else None) or pothole.image_path

            after_candidates = [
                row
                for row in source_rows
                if row.image_url
                and row.image_url != before_path
                and (baseline_time is None or row.evidence_time is None or row.evidence_time > baseline_time)
            ]

            latest_source_image = None
            if after_candidates:
                after_choice = sorted(
                    after_candidates,
                    key=lambda row: (
                        row.evidence_time or datetime.min.replace(tzinfo=timezone.utc),
                        _source_rank(row.source_type),
                    ),
                    reverse=True,
                )[0]
                latest_source_image = after_choice.image_url

            latest_scan_result = await db.execute(
                text(
                    """
                    SELECT after_image_path, scan_date
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
            latest_scan_date = latest_scan_row[1] if latest_scan_row else None

            after_path = latest_source_image or latest_scan_image
            if after_path == before_path:
                after_path = latest_scan_image if latest_scan_image and latest_scan_image != before_path else None

            if not after_path:
                queued_nodes = await _queue_nearby_cctv_refresh(db, pothole_id, pothole.latitude, pothole.longitude)
                payload = {
                    "pothole_id": pothole_id,
                    "status": "AWAITING_FRESH_IMAGERY",
                    "queued_cctv_nodes": queued_nodes,
                }
                await _record_history(
                    "verify_single_pothole",
                    getattr(self.request, "id", None),
                    "PENDING",
                    payload,
                )
                return payload

            if latest_scan_image and latest_source_image is None and latest_scan_date is not None and baseline_time is not None:
                baseline_date = baseline_time.date()
                if latest_scan_date <= baseline_date:
                    queued_nodes = await _queue_nearby_cctv_refresh(db, pothole_id, pothole.latitude, pothole.longitude)
                    payload = {
                        "pothole_id": pothole_id,
                        "status": "STALE_AFTER_IMAGE",
                        "queued_cctv_nodes": queued_nodes,
                        "baseline_time": baseline_time.isoformat() if baseline_time else None,
                    }
                    await _record_history(
                        "verify_single_pothole",
                        getattr(self.request, "id", None),
                        "PENDING",
                        payload,
                    )
                    return payload

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
                "before_path": before_path,
                "after_path": after_path,
            }
            await _record_history(
                "verify_single_pothole",
                getattr(self.request, "id", None),
                "SUCCESS",
                payload,
            )
            return payload

    return asyncio.get_event_loop().run_until_complete(_verify())
