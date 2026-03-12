"""Admin detection review — approve, reject, merge, edit potholes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pothole import Pothole
from app.models.admin import AdminAuditLog
from app.schemas.pothole import PotholeOut

router = APIRouter(prefix="/api/admin/detections", tags=["admin-detections"])


@router.get("/pending", response_model=list[PotholeOut])
async def pending_reviews(
    confidence_below: float = Query(0.7),
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """List potholes below confidence threshold for manual review."""
    result = await db.execute(
        select(Pothole)
        .where(
            Pothole.confidence_score < confidence_below,
            Pothole.status == "Detected",
        )
        .order_by(Pothole.risk_score.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.post("/{pothole_id}/approve")
async def approve_detection(
    pothole_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Manually approve a low-confidence detection."""
    result = await db.execute(select(Pothole).where(Pothole.id == pothole_id))
    pothole = result.scalar_one_or_none()
    if not pothole:
        raise HTTPException(status_code=404, detail="Pothole not found")

    before = {"status": pothole.status, "confidence": pothole.confidence_score}
    pothole.status = "Confirmed"
    pothole.confidence_score = max(pothole.confidence_score, 0.80)

    audit = AdminAuditLog(
        admin_id=1,  # TODO: from JWT
        action="APPROVE_DETECTION",
        entity_type="pothole",
        entity_id=pothole_id,
        before_state=before,
        after_state={"status": "Confirmed", "confidence": pothole.confidence_score},
    )
    db.add(audit)
    await db.commit()

    # Trigger filing if above auto-file threshold
    if pothole.confidence_score >= 0.70:
        from app.tasks.filing_tasks import file_complaint
        file_complaint.delay(pothole_id)

    return {"approved": pothole_id}


@router.post("/{pothole_id}/reject")
async def reject_detection(
    pothole_id: int,
    reason: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Reject a false-positive detection."""
    result = await db.execute(select(Pothole).where(Pothole.id == pothole_id))
    pothole = result.scalar_one_or_none()
    if not pothole:
        raise HTTPException(status_code=404, detail="Pothole not found")

    before = {"status": pothole.status}
    pothole.status = "Rejected"

    audit = AdminAuditLog(
        admin_id=1,
        action="REJECT_DETECTION",
        entity_type="pothole",
        entity_id=pothole_id,
        before_state=before,
        after_state={"status": "Rejected", "reason": reason},
    )
    db.add(audit)
    await db.commit()
    return {"rejected": pothole_id}


@router.post("/{pothole_id}/edit")
async def edit_detection(
    pothole_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Edit pothole attributes (severity, location, etc.)."""
    result = await db.execute(select(Pothole).where(Pothole.id == pothole_id))
    pothole = result.scalar_one_or_none()
    if not pothole:
        raise HTTPException(status_code=404, detail="Pothole not found")

    allowed_fields = {
        "severity", "latitude", "longitude", "nh_number",
        "estimated_area_m2", "estimated_depth_cm",
    }
    before = {}
    after = {}

    for field, value in body.items():
        if field in allowed_fields:
            before[field] = getattr(pothole, field, None)
            setattr(pothole, field, value)
            after[field] = value

    audit = AdminAuditLog(
        admin_id=1,
        action="EDIT_DETECTION",
        entity_type="pothole",
        entity_id=pothole_id,
        before_state=before,
        after_state=after,
    )
    db.add(audit)
    await db.commit()
    return {"updated": pothole_id, "fields": list(after.keys())}


@router.post("/merge")
async def merge_detections(
    primary_id: int,
    secondary_ids: list[int],
    db: AsyncSession = Depends(get_db),
):
    """Merge duplicate detections into a single pothole."""
    result = await db.execute(select(Pothole).where(Pothole.id == primary_id))
    primary = result.scalar_one_or_none()
    if not primary:
        raise HTTPException(status_code=404, detail="Primary pothole not found")

    merged = []
    for sid in secondary_ids:
        sec_result = await db.execute(select(Pothole).where(Pothole.id == sid))
        sec = sec_result.scalar_one_or_none()
        if sec:
            sec.status = "Merged"
            sec.merged_into_id = primary_id
            # Boost confidence of primary
            primary.confidence_score = min(
                primary.confidence_score + 0.05, 1.0
            )
            merged.append(sid)

    audit = AdminAuditLog(
        admin_id=1,
        action="MERGE_DETECTIONS",
        entity_type="pothole",
        entity_id=primary_id,
        before_state={"secondary_ids": secondary_ids},
        after_state={"merged": merged},
    )
    db.add(audit)
    await db.commit()
    return {"primary": primary_id, "merged": merged}
