"""Admin escalation and reverify module endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.complaint import Complaint
from app.models.pothole import Pothole
from app.models.scan import Scan

router = APIRouter(prefix="/api/admin/escalation", tags=["admin-escalation"])


@router.get("/overview")
async def escalation_overview(db: AsyncSession = Depends(get_db)):
    """Live escalation and reverify state from complaints and scans."""
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

    cutoff = datetime.now(timezone.utc) - timedelta(days=14)
    due_reverify_q = await db.execute(
        select(func.count(Complaint.id)).where(
            unresolved_filter,
            or_(Complaint.escalated_at <= cutoff, Complaint.filed_at <= cutoff),
        )
    )

    scans_q = await db.execute(
        select(
            Scan.id,
            Scan.pothole_id,
            Scan.scan_date,
            Scan.repair_status,
            Scan.ssim_score,
            Scan.siamese_score,
            Scan.scan_source,
        )
        .order_by(Scan.id.desc())
        .limit(20)
    )
    scans = scans_q.all()

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
                "id": int(s.id),
                "pothole_id": int(s.pothole_id),
                "scan_date": s.scan_date.isoformat() if s.scan_date else None,
                "repair_status": s.repair_status,
                "ssim_score": float(s.ssim_score or 0.0),
                "siamese_score": float(s.siamese_score or 0.0),
                "scan_source": s.scan_source,
            }
            for s in scans
        ],
    }


@router.post("/run-escalation")
async def run_escalation_logic():
    """Trigger escalation eligibility checks."""
    from app.tasks.escalation_tasks import check_all_escalations

    task = check_all_escalations.delay()
    return {"queued": True, "task_id": task.id, "task": "check_all_escalations"}


@router.post("/run-portal-sync")
async def run_portal_sync_logic():
    """Queue complaint filing for detected potholes not yet filed on portal."""
    from app.tasks.escalation_tasks import sync_detected_potholes_to_portal

    task = sync_detected_potholes_to_portal.delay()
    return {"queued": True, "task_id": task.id, "task": "sync_detected_potholes_to_portal"}


@router.post("/run-reverify")
async def run_reverify_logic():
    """Trigger auto reverify checks for due potholes."""
    from app.tasks.verification_tasks import verify_all_repairs

    task = verify_all_repairs.delay()
    return {"queued": True, "task_id": task.id, "task": "verify_all_repairs"}
