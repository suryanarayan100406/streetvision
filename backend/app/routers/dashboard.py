"""Dashboard API — public analytics endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, case, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pothole import Pothole
from app.models.complaint import Complaint
from app.models.scan import Scan

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/trend")
async def detection_trend(
    days: int = Query(30, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Daily detection count over the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date_trunc("day", Pothole.detected_at).label("day"),
            func.count(Pothole.id).label("count"),
        )
        .where(Pothole.detected_at >= since)
        .group_by("day")
        .order_by("day")
    )
    return [{"date": r.day.isoformat(), "count": r.count} for r in result.all()]


@router.get("/severity-distribution")
async def severity_distribution(db: AsyncSession = Depends(get_db)):
    """Count of potholes by severity."""
    result = await db.execute(
        select(Pothole.severity, func.count(Pothole.id))
        .group_by(Pothole.severity)
    )
    return {r[0]: r[1] for r in result.all()}


@router.get("/complaint-funnel")
async def complaint_funnel(db: AsyncSession = Depends(get_db)):
    """Complaint lifecycle funnel: detected → filed → acknowledged → resolved."""
    total = (await db.execute(select(func.count(Pothole.id)))).scalar() or 0
    filed = (await db.execute(
        select(func.count(Complaint.id))
    )).scalar() or 0
    acknowledged = (await db.execute(
        select(func.count(Complaint.id))
        .where(Complaint.portal_status.in_(["Under Process", "Resolved", "Closed"]))
    )).scalar() or 0
    resolved = (await db.execute(
        select(func.count(Complaint.id))
        .where(Complaint.portal_status.in_(["Resolved", "Closed"]))
    )).scalar() or 0

    return {
        "detected": total,
        "filed": filed,
        "acknowledged": acknowledged,
        "resolved": resolved,
    }


@router.get("/highway-comparison")
async def highway_comparison(db: AsyncSession = Depends(get_db)):
    """Per-highway breakdown of potholes, avg risk, repair rate."""
    result = await db.execute(
        select(
            Pothole.nh_number,
            func.count(Pothole.id).label("total"),
            func.avg(Pothole.risk_score).label("avg_risk"),
            func.sum(
                case((Pothole.status == "Repaired", 1), else_=0)
            ).label("repaired"),
        )
        .group_by(Pothole.nh_number)
    )
    return [
        {
            "nh_number": r.nh_number,
            "total": r.total,
            "avg_risk": round(float(r.avg_risk or 0), 2),
            "repaired": r.repaired,
            "repair_rate": round(r.repaired / r.total * 100, 1) if r.total > 0 else 0,
        }
        for r in result.all()
    ]


@router.get("/resolution-time")
async def avg_resolution_time(db: AsyncSession = Depends(get_db)):
    """Average days between complaint filing and resolution."""
    result = await db.execute(
        select(
            func.avg(
                extract("epoch", Complaint.resolved_at - Complaint.filed_at) / 86400
            ).label("avg_days"),
        )
        .where(Complaint.resolved_at.isnot(None))
    )
    row = result.first()
    return {"avg_resolution_days": round(float(row.avg_days or 0), 1)}


@router.get("/source-breakdown")
async def source_breakdown(db: AsyncSession = Depends(get_db)):
    """Count of detections by source type."""
    from app.models.source_report import SourceReport

    result = await db.execute(
        select(SourceReport.source_type, func.count(SourceReport.id))
        .group_by(SourceReport.source_type)
    )
    return {r[0]: r[1] for r in result.all()}


@router.get("/leaderboard")
async def leaderboard(
    limit: int = Query(20, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Top contributors from mobile reports."""
    from app.models.settings import GamificationPoints

    result = await db.execute(
        select(GamificationPoints)
        .order_by(GamificationPoints.total_points.desc())
        .limit(limit)
    )
    entries = result.scalars().all()
    return [
        {
            "rank": i + 1,
            "user_id": e.user_id,
            "display_name": e.display_name,
            "total_points": e.total_points,
            "reports_count": e.reports_count,
        }
        for i, e in enumerate(entries)
    ]
