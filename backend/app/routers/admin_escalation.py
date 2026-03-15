"""Admin escalation and reverify module endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.complaint import Complaint
from app.models.pothole import Pothole
from app.models.scan import Scan
from app.services.minio_client import get_presigned_url

router = APIRouter(prefix="/api/admin/escalation", tags=["admin-escalation"])

ESCALATION_TARGETS = {
    1: "Executive Engineer, PWD Roads Division",
    2: "District Collector",
    3: "Principal Secretary, Public Works Department",
}


@router.get("/overview")
async def escalation_overview(db: AsyncSession = Depends(get_db)):
    """Live escalation and reverify state from complaints and scans."""

    def _proof_url(path: str | None) -> str | None:
        if not path:
            return None
        try:
            return get_presigned_url(path, expires_hours=6).replace("http://minio:9000", "http://localhost/minio")
        except Exception:
            return None

    def _sla_fields(anchor: datetime | None) -> dict[str, int | str | None]:
        if anchor is None:
            return {
                "sla_due_at": None,
                "sla_overdue_days": 0,
                "sla_days_to_due": 0,
                "sla_status": "UNKNOWN",
            }
        due_at = anchor + timedelta(days=14)
        days_to_due = (due_at - now).days
        overdue_days = max(0, (now - due_at).days)
        if overdue_days > 0:
            status = "OVERDUE"
        elif days_to_due <= 2:
            status = "DUE_SOON"
        else:
            status = "ON_TRACK"
        return {
            "sla_due_at": due_at.isoformat(),
            "sla_overdue_days": overdue_days,
            "sla_days_to_due": days_to_due,
            "sla_status": status,
        }

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

    pothole_ids = [int(c.pothole_id) for c in complaints]
    potholes_q = await db.execute(
        select(Pothole.id, Pothole.severity, Pothole.nh_number, Pothole.chainage_km)
        .where(Pothole.id.in_(pothole_ids))
    )
    pothole_meta = {
        int(row.id): {
            "severity": row.severity,
            "nh_number": row.nh_number,
            "chainage_km": row.chainage_km,
        }
        for row in potholes_q.all()
    }

    scan_by_pothole: dict[int, list] = defaultdict(list)
    for scan in scans:
        scan_by_pothole[int(scan.pothole_id)].append(scan)

    recent_open_complaints = []
    for c in complaints[:20]:
        anchor = c.escalated_at or c.filed_at or c.created_at
        sla = _sla_fields(anchor)
        recent_open_complaints.append(
            {
                "id": c.id,
                "pothole_id": c.pothole_id,
                "portal_ref": c.portal_ref,
                "portal_status": c.portal_status,
                "escalation_level": c.escalation_level,
                "escalation_target": c.escalation_target,
                "filing_method": c.filing_method,
                "filing_proof_path": c.filing_proof_path,
                "filing_proof_url": _proof_url(c.filing_proof_path),
                "recipient_authority": c.escalation_target
                or ESCALATION_TARGETS.get(int(c.escalation_level or 0), ESCALATION_TARGETS[1]),
                "subject_line": (
                    f"Urgent: {(pothole_meta.get(int(c.pothole_id), {}).get('severity') or 'Unknown')} Severity Pothole on "
                    f"{(pothole_meta.get(int(c.pothole_id), {}).get('nh_number') or 'Unknown Road')} at KM "
                    f"{(pothole_meta.get(int(c.pothole_id), {}).get('chainage_km') or 'N/A')} — "
                    f"Escalation Level {int(c.escalation_level or 0)}"
                ),
                "filed_at": c.filed_at.isoformat() if c.filed_at else None,
                "escalated_at": c.escalated_at.isoformat() if c.escalated_at else None,
                "last_filed_at": (c.filed_at or c.created_at).isoformat() if (c.filed_at or c.created_at) else None,
                "escalation_age_days": max(0, (now - anchor).days) if anchor else 0,
                "sla_due_at": sla["sla_due_at"],
                "sla_overdue_days": sla["sla_overdue_days"],
                "sla_days_to_due": sla["sla_days_to_due"],
                "sla_status": sla["sla_status"],
                "days_open": max(0, (now - (c.filed_at or c.created_at)).days) if (c.filed_at or c.created_at) else 0,
                "complaint_preview": (c.complaint_text or "")[:220],
                "complaint_text": c.complaint_text or "",
                "latest_verification_status": scan_by_pothole.get(int(c.pothole_id), [None])[0].repair_status if scan_by_pothole.get(int(c.pothole_id)) else None,
                "latest_verification_date": scan_by_pothole.get(int(c.pothole_id), [None])[0].scan_date.isoformat() if scan_by_pothole.get(int(c.pothole_id)) and scan_by_pothole.get(int(c.pothole_id), [None])[0].scan_date else None,
                "latest_ssim_score": float(scan_by_pothole.get(int(c.pothole_id), [None])[0].ssim_score or 0.0) if scan_by_pothole.get(int(c.pothole_id)) else None,
                "latest_siamese_score": float(scan_by_pothole.get(int(c.pothole_id), [None])[0].siamese_score or 0.0) if scan_by_pothole.get(int(c.pothole_id)) else None,
            }
        )

    status_priority = {"OVERDUE": 0, "DUE_SOON": 1, "ON_TRACK": 2, "UNKNOWN": 3}
    recent_open_complaints.sort(
        key=lambda row: (
            status_priority.get(str(row.get("sla_status")), 3),
            -int(row.get("sla_overdue_days") or 0),
            -int(row.get("days_open") or 0),
        )
    )

    sla_counts = {
        "OVERDUE": 0,
        "DUE_SOON": 0,
        "ON_TRACK": 0,
        "UNKNOWN": 0,
    }
    for row in recent_open_complaints:
        status = str(row.get("sla_status") or "UNKNOWN")
        if status not in sla_counts:
            status = "UNKNOWN"
        sla_counts[status] += 1

    return {
        "generated_at": now.isoformat(),
        "summary": {
            "open_complaints": len(complaints),
            "due_reverify": int(due_reverify_q.scalar() or 0),
            "recent_scans": len(scans),
            "sla_overdue": int(sla_counts["OVERDUE"]),
            "sla_due_soon": int(sla_counts["DUE_SOON"]),
            "sla_on_track": int(sla_counts["ON_TRACK"]),
        },
        "escalation_levels": [
            {"level": int(row[0] or 0), "count": int(row[1] or 0)}
            for row in level_counts_q.all()
        ],
        "recent_open_complaints": recent_open_complaints,
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
