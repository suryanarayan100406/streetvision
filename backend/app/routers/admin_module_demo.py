"""Admin module demo endpoints for step-by-step pipeline showcase."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.complaint import Complaint
from app.models.pothole import Pothole
from app.models.scan import Scan
from app.models.settings import ModelRegistry
from app.models.source_report import SourceReport
from app.models.task import TaskHistory

router = APIRouter(prefix="/api/admin/module-demo", tags=["admin-module-demo"])


@router.get("/detection-output")
async def detection_output(db: AsyncSession = Depends(get_db)):
    """Detection module output: recent potholes, source reports and aggregates."""
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)

    potholes_24h = (
        await db.execute(select(func.count(Pothole.id)).where(Pothole.detected_at >= last_24h))
    ).scalar() or 0

    reports_24h = (
        await db.execute(select(func.count(SourceReport.id)).where(SourceReport.created_at >= last_24h))
    ).scalar() or 0

    by_source_q = await db.execute(
        select(SourceReport.source_type, func.count(SourceReport.id))
        .group_by(SourceReport.source_type)
        .order_by(desc(func.count(SourceReport.id)))
    )

    recent_potholes_q = await db.execute(
        select(Pothole)
        .order_by(Pothole.detected_at.desc())
        .limit(20)
    )
    recent_potholes = recent_potholes_q.scalars().all()

    return {
        "generated_at": now.isoformat(),
        "summary": {
            "potholes_last_24h": int(potholes_24h),
            "source_reports_last_24h": int(reports_24h),
            "total_potholes": int((await db.execute(select(func.count(Pothole.id)))).scalar() or 0),
        },
        "by_source": [
            {"source": row[0] or "UNKNOWN", "count": int(row[1] or 0)}
            for row in by_source_q.all()
        ],
        "recent_potholes": [
            {
                "id": p.id,
                "severity": p.severity,
                "confidence": float(p.confidence_score or 0.0),
                "risk_score": float(p.risk_score or 0.0),
                "status": p.status,
                "nh_number": p.nh_number,
                "image_path": p.image_path,
                "detected_at": p.detected_at.isoformat() if p.detected_at else None,
            }
            for p in recent_potholes
        ],
    }


@router.get("/model-predictions")
async def model_predictions(db: AsyncSession = Depends(get_db)):
    """Model prediction module output: active models + inference execution snapshot."""
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)

    active_models_q = await db.execute(
        select(ModelRegistry)
        .where(ModelRegistry.is_active.is_(True))
        .order_by(ModelRegistry.model_type.asc(), ModelRegistry.id.desc())
    )
    active_models = active_models_q.scalars().all()

    inference_tasks_q = await db.execute(
        select(TaskHistory)
        .where(
            TaskHistory.completed_at >= last_24h,
            TaskHistory.task_name.ilike("%run_inference_on_tile%"),
        )
        .order_by(TaskHistory.completed_at.desc())
        .limit(40)
    )
    inference_tasks = inference_tasks_q.scalars().all()

    success = sum(1 for t in inference_tasks if (t.status or "").upper() == "SUCCESS")
    failed = sum(1 for t in inference_tasks if (t.status or "").upper() == "FAILED")

    return {
        "generated_at": now.isoformat(),
        "summary": {
            "inference_tasks_last_24h": len(inference_tasks),
            "inference_success": success,
            "inference_failed": failed,
        },
        "active_models": [
            {
                "id": m.id,
                "model_name": m.model_name,
                "version": m.version,
                "model_type": m.model_type,
                "weights_path": m.weights_path,
                "precision": float(m.precision or 0.0),
                "recall": float(m.recall or 0.0),
                "f1_score": float(m.f1_score or 0.0),
                "map50": float(m.map50 or 0.0),
            }
            for m in active_models
        ],
        "recent_inference_tasks": [
            {
                "task_id": t.task_id,
                "status": t.status,
                "duration_seconds": float(t.duration_seconds or 0.0),
                "completed_at": t.completed_at.isoformat() if t.completed_at else None,
                "result": t.result,
            }
            for t in inference_tasks[:20]
        ],
    }


@router.get("/escalation-logic")
async def escalation_logic(db: AsyncSession = Depends(get_db)):
    """Escalation and reverify module output: complaint ladder + scan state."""
    now = datetime.now(timezone.utc)
    unresolved_filter = or_(
        Complaint.portal_status.is_(None),
        Complaint.portal_status.notin_(["Resolved", "Closed"]),
    )

    complaints_q = await db.execute(
        select(Complaint)
        .where(unresolved_filter)
        .order_by(Complaint.created_at.desc())
        .limit(50)
    )
    complaints = complaints_q.scalars().all()

    level_counts_q = await db.execute(
        select(Complaint.escalation_level, func.count(Complaint.id))
        .where(unresolved_filter)
        .group_by(Complaint.escalation_level)
        .order_by(Complaint.escalation_level.asc())
    )

    cutoff = date.today() - timedelta(days=14)
    due_reverify_q = await db.execute(
        select(func.count(Pothole.id)).where(
            Pothole.last_repair_status != "Repaired",
            or_(Pothole.last_scan_date <= cutoff, Pothole.last_scan_date.is_(None)),
        )
    )

    scans_q = await db.execute(
        select(Scan)
        .order_by(Scan.id.desc())
        .limit(20)
    )
    scans = scans_q.scalars().all()

    return {
        "generated_at": now.isoformat(),
        "summary": {
            "open_complaints": len(complaints),
            "due_reverify": int(due_reverify_q.scalar() or 0),
            "recent_scans": len(scans),
        },
        "escalation_levels": [
            {"level": int(row[0] or 0), "count": int(row[1] or 0)}
            for row in level_counts_q.all()
        ],
        "recent_open_complaints": [
            {
                "id": c.id,
                "pothole_id": c.pothole_id,
                "portal_ref": c.portal_ref,
                "portal_status": c.portal_status,
                "escalation_level": c.escalation_level,
                "escalation_target": c.escalation_target,
                "filed_at": c.filed_at.isoformat() if c.filed_at else None,
                "escalated_at": c.escalated_at.isoformat() if c.escalated_at else None,
            }
            for c in complaints[:20]
        ],
        "recent_scans_list": [
            {
                "id": s.id,
                "pothole_id": s.pothole_id,
                "scan_date": s.scan_date.isoformat() if s.scan_date else None,
                "repair_status": s.repair_status,
                "ssim_score": float(s.ssim_score or 0.0),
                "siamese_score": float(s.siamese_score or 0.0),
                "scan_source": s.scan_source,
            }
            for s in scans
        ],
    }


@router.post("/escalation-logic/run-escalation")
async def run_escalation_logic():
    """Trigger escalation eligibility checks."""
    from app.tasks.escalation_tasks import check_all_escalations

    task = check_all_escalations.delay()
    return {"queued": True, "task_id": task.id, "task": "check_all_escalations"}


@router.post("/escalation-logic/run-reverify")
async def run_reverify_logic():
    """Trigger auto reverify checks for due potholes."""
    from app.tasks.verification_tasks import verify_all_repairs

    task = verify_all_repairs.delay()
    return {"queued": True, "task_id": task.id, "task": "verify_all_repairs"}


@router.get("/compiled-pipeline")
async def compiled_pipeline(db: AsyncSession = Depends(get_db)):
    """Combined module snapshot to demonstrate end-to-end integration."""
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)

    detections_24h = (
        await db.execute(select(func.count(Pothole.id)).where(Pothole.detected_at >= last_24h))
    ).scalar() or 0
    reports_24h = (
        await db.execute(select(func.count(SourceReport.id)).where(SourceReport.created_at >= last_24h))
    ).scalar() or 0

    inference_success_24h = (
        await db.execute(
            select(func.count(TaskHistory.id)).where(
                TaskHistory.completed_at >= last_24h,
                TaskHistory.task_name.ilike("%run_inference_on_tile%"),
                TaskHistory.status == "SUCCESS",
            )
        )
    ).scalar() or 0
    inference_failed_24h = (
        await db.execute(
            select(func.count(TaskHistory.id)).where(
                TaskHistory.completed_at >= last_24h,
                TaskHistory.task_name.ilike("%run_inference_on_tile%"),
                TaskHistory.status == "FAILED",
            )
        )
    ).scalar() or 0

    open_complaints = (
        await db.execute(
            select(func.count(Complaint.id)).where(
                or_(Complaint.portal_status.is_(None), Complaint.portal_status.notin_(["Resolved", "Closed"]))
            )
        )
    ).scalar() or 0

    due_reverify = (
        await db.execute(
            select(func.count(Pothole.id)).where(
                Pothole.last_repair_status != "Repaired",
                or_(Pothole.last_scan_date.is_(None), Pothole.last_scan_date <= (date.today() - timedelta(days=14))),
            )
        )
    ).scalar() or 0

    return {
        "generated_at": now.isoformat(),
        "modules": {
            "detection_output": {
                "ok": int(reports_24h) > 0 or int(detections_24h) > 0,
                "detections_24h": int(detections_24h),
                "source_reports_24h": int(reports_24h),
            },
            "model_predictions": {
                "ok": int(inference_success_24h + inference_failed_24h) > 0,
                "inference_success_24h": int(inference_success_24h),
                "inference_failed_24h": int(inference_failed_24h),
            },
            "escalation_reverify": {
                "ok": True,
                "open_complaints": int(open_complaints),
                "due_reverify": int(due_reverify),
            },
        },
        "overall_ok": True,
    }
