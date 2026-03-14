"""Admin verification module endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.complaint import Complaint
from app.models.pothole import Pothole

router = APIRouter(prefix="/api/admin/verification", tags=["admin-verification"])


@router.get("/overview")
async def verification_overview(db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    due_cutoff = now - timedelta(days=14)

    open_filter = or_(
        Complaint.portal_status.is_(None),
        Complaint.portal_status.notin_(["Resolved", "Closed"]),
    )

    due_q = await db.execute(
        select(func.count(Complaint.id)).where(
            open_filter,
            or_(Complaint.escalated_at <= due_cutoff, Complaint.filed_at <= due_cutoff),
        )
    )

    resolved_q = await db.execute(
        select(func.count(Complaint.id)).where(Complaint.portal_status.in_(["Resolved", "Closed"]))
    )

    unresolved_q = await db.execute(
        select(func.count(Complaint.id)).where(Complaint.portal_status.in_(["Unresolved", "ESCALATED"]))
    )

    scans_q = await db.execute(
        text(
            """
            SELECT s.id, s.pothole_id, s.scan_date, s.repair_status, s.ssim_score, s.siamese_score,
                   c.id AS complaint_id, c.escalation_level, c.portal_status
            FROM scans s
            LEFT JOIN complaints c ON c.pothole_id = s.pothole_id
            ORDER BY s.id DESC
            LIMIT 30
            """
        )
    )

    due_list_q = await db.execute(
        select(
            Complaint.id,
            Complaint.pothole_id,
            Complaint.portal_status,
            Complaint.escalation_level,
            Complaint.filed_at,
            Complaint.escalated_at,
            Pothole.last_repair_status,
            Pothole.last_scan_date,
        )
        .join(Pothole, Pothole.id == Complaint.pothole_id)
        .where(
            open_filter,
            or_(Complaint.escalated_at <= due_cutoff, Complaint.filed_at <= due_cutoff),
        )
        .order_by(Complaint.escalation_level.desc(), Complaint.created_at.asc())
        .limit(50)
    )

    return {
        "generated_at": now.isoformat(),
        "summary": {
            "due_reverification": int(due_q.scalar() or 0),
            "resolved_complaints": int(resolved_q.scalar() or 0),
            "unresolved_or_escalated": int(unresolved_q.scalar() or 0),
            "recent_reverify_scans": len(scans_q.all()),
        },
        "due_cases": [
            {
                "complaint_id": int(r.id),
                "pothole_id": int(r.pothole_id),
                "portal_status": r.portal_status,
                "escalation_level": int(r.escalation_level or 0),
                "filed_at": r.filed_at.isoformat() if r.filed_at else None,
                "escalated_at": r.escalated_at.isoformat() if r.escalated_at else None,
                "last_repair_status": r.last_repair_status,
                "last_scan_date": r.last_scan_date.isoformat() if r.last_scan_date else None,
            }
            for r in due_list_q.all()
        ],
        "recent_scans": [
            {
                "scan_id": int(r.id),
                "pothole_id": int(r.pothole_id),
                "complaint_id": int(r.complaint_id) if r.complaint_id is not None else None,
                "scan_date": r.scan_date.isoformat() if r.scan_date else None,
                "repair_status": r.repair_status,
                "ssim_score": float(r.ssim_score or 0.0),
                "siamese_score": float(r.siamese_score or 0.0),
                "escalation_level": int(r.escalation_level or 0) if r.escalation_level is not None else 0,
                "portal_status": r.portal_status,
            }
            for r in scans_q.all()
        ],
    }


@router.post("/run")
async def run_verification_now():
    from app.tasks.verification_tasks import verify_all_repairs

    task = verify_all_repairs.delay()
    return {"queued": True, "task_id": task.id, "task": "verify_all_repairs"}
