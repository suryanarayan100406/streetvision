"""Admin satellite source management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.satellite import SatelliteSource, SatelliteJob, SatelliteDownloadLog
from app.schemas.satellite import (
    SatelliteSourceOut,
    SatelliteSourceUpdate,
    SatelliteJobOut,
    TestConnectionResult,
)

router = APIRouter(prefix="/api/admin/satellites", tags=["admin-satellites"])


@router.get("/sources", response_model=list[SatelliteSourceOut])
async def list_sources(db: AsyncSession = Depends(get_db)):
    """List all satellite data sources and their status."""
    result = await db.execute(
        select(SatelliteSource).order_by(SatelliteSource.priority)
    )
    return result.scalars().all()


@router.patch("/sources/{source_id}", response_model=SatelliteSourceOut)
async def update_source(
    source_id: int,
    body: SatelliteSourceUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Enable/disable a source or change priority."""
    result = await db.execute(
        select(SatelliteSource).where(SatelliteSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    if body.enabled is not None:
        source.enabled = body.enabled
    if body.priority is not None:
        source.priority = body.priority
    if body.credentials is not None:
        source.credentials = body.credentials

    await db.commit()
    await db.refresh(source)
    return source


@router.post("/sources/{source_id}/test", response_model=TestConnectionResult)
async def test_connection(source_id: int, db: AsyncSession = Depends(get_db)):
    """Test connectivity to a satellite source."""
    result = await db.execute(
        select(SatelliteSource).where(SatelliteSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    from app.services.satellite_manager import test_source_connection

    test_result = await test_source_connection(source)
    return test_result


@router.get("/jobs", response_model=list[SatelliteJobOut])
async def list_jobs(
    limit: int = 50,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List recent satellite ingestion jobs."""
    q = select(SatelliteJob).order_by(SatelliteJob.created_at.desc()).limit(limit)
    if status:
        q = q.where(SatelliteJob.status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/trigger/{source_name}")
async def trigger_ingestion(source_name: str):
    """Manually trigger satellite ingestion for a specific source."""
    from app.tasks.satellite_tasks import (
        ingest_sentinel2, ingest_sentinel1, ingest_bhoonidhi,
        ingest_landsat, ingest_open_aerial_map,
    )

    task_map = {
        "sentinel2": ingest_sentinel2,
        "sentinel1": ingest_sentinel1,
        "bhoonidhi": ingest_bhoonidhi,
        "landsat": ingest_landsat,
        "oam": ingest_open_aerial_map,
    }

    task = task_map.get(source_name)
    if not task:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source_name}")

    result = task.delay()
    return {"task_id": result.id, "source": source_name}


@router.get("/download-logs")
async def download_logs(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Recent satellite download logs."""
    result = await db.execute(
        select(SatelliteDownloadLog)
        .order_by(SatelliteDownloadLog.downloaded_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
