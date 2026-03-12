"""Admin logs & audit trail endpoints."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.admin import AdminAuditLog, GeminiAudit

router = APIRouter(prefix="/api/admin/logs", tags=["admin-logs"])


@router.get("/audit")
async def list_audit_logs(
    action: str | None = None,
    entity_type: str | None = None,
    admin_id: int | None = None,
    days: int = Query(30, le=365),
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List admin audit trail entries."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        select(AdminAuditLog)
        .where(AdminAuditLog.created_at >= since)
        .order_by(AdminAuditLog.created_at.desc())
        .limit(limit)
    )
    if action:
        q = q.where(AdminAuditLog.action == action)
    if entity_type:
        q = q.where(AdminAuditLog.entity_type == entity_type)
    if admin_id:
        q = q.where(AdminAuditLog.admin_id == admin_id)

    result = await db.execute(q)
    return result.scalars().all()


@router.get("/audit/actions")
async def audit_action_types(db: AsyncSession = Depends(get_db)):
    """List distinct audit action types."""
    result = await db.execute(
        select(AdminAuditLog.action).distinct()
    )
    return [r[0] for r in result.all()]


@router.get("/gemini")
async def list_gemini_logs(
    days: int = Query(7, le=90),
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List Gemini API usage audit logs."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        select(GeminiAudit)
        .where(GeminiAudit.created_at >= since)
        .order_by(GeminiAudit.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/gemini/usage")
async def gemini_usage_stats(
    days: int = Query(7, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Gemini API usage statistics."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.count(GeminiAudit.id).label("total_calls"),
            func.sum(GeminiAudit.input_tokens).label("total_input_tokens"),
            func.sum(GeminiAudit.output_tokens).label("total_output_tokens"),
            func.avg(GeminiAudit.latency_ms).label("avg_latency_ms"),
            func.sum(
                func.cast(GeminiAudit.success.is_(False), type_=func.INTEGER)
            ).label("failures"),
        )
        .where(GeminiAudit.created_at >= since)
    )
    row = result.first()
    return {
        "total_calls": row.total_calls or 0,
        "total_input_tokens": row.total_input_tokens or 0,
        "total_output_tokens": row.total_output_tokens or 0,
        "avg_latency_ms": round(float(row.avg_latency_ms or 0), 1),
        "failures": row.failures or 0,
    }


@router.get("/system")
async def system_logs(
    level: str = Query("ERROR", description="Minimum log level"),
    limit: int = 100,
):
    """Fetch recent application logs from Loki via Grafana API."""
    import httpx
    from app.config import settings

    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(
                f"http://loki:3100/loki/api/v1/query_range",
                params={
                    "query": f'{{app="pothole-api"}} |= "{level}"',
                    "limit": limit,
                    "direction": "backward",
                },
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass

    return {"message": "Loki not available", "logs": []}
