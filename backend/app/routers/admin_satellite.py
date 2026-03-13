"""Admin satellite source management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone

from app.config import settings
from app.database import get_db
from app.models.satellite import SatelliteSource, SatelliteJob, SatelliteDownloadLog
from app.schemas.satellite import (
    SatelliteSourceOut,
    SatelliteSourceUpdate,
    SatelliteJobOut,
    TestConnectionResult,
    OAMSearchRequest,
    OAMSearchResponse,
    OAMTriggerResponse,
    SatelliteCredentialStatusResponse,
    SatelliteDownloadLogOut,
    SatelliteSceneSearchRequest,
    SatelliteSceneSearchResponse,
    SatelliteScanLaunchResponse,
)

router = APIRouter(prefix="/api/admin/satellites", tags=["admin-satellites"])


def _default_corridor_bbox() -> dict[str, float]:
    from app.tasks.satellite_tasks import HIGHWAY_CORRIDORS

    return {
        "lon_min": min(item["lon_min"] for item in HIGHWAY_CORRIDORS.values()),
        "lat_min": min(item["lat_min"] for item in HIGHWAY_CORRIDORS.values()),
        "lon_max": max(item["lon_max"] for item in HIGHWAY_CORRIDORS.values()),
        "lat_max": max(item["lat_max"] for item in HIGHWAY_CORRIDORS.values()),
    }


def _has_real_value(value: str) -> bool:
    v = (value or "").strip()
    if not v:
        return False
    bad_tokens = ("your_", "optional_", "dev_", "placeholder", "change-me", "change_me")
    lower_v = v.lower()
    return not any(token in lower_v for token in bad_tokens)


def _parse_bbox_string(bbox: str) -> dict[str, float]:
    try:
        lon_min, lat_min, lon_max, lat_max = [float(x.strip()) for x in bbox.split(",")]
    except Exception as exc:
        raise HTTPException(status_code=400, detail="bbox must be 'lon_min,lat_min,lon_max,lat_max'") from exc

    if lon_min >= lon_max or lat_min >= lat_max:
        raise HTTPException(status_code=400, detail="Invalid bbox bounds")

    return {
        "lon_min": lon_min,
        "lat_min": lat_min,
        "lon_max": lon_max,
        "lat_max": lat_max,
    }


@router.get("/sources", response_model=list[SatelliteSourceOut])
async def list_sources(db: AsyncSession = Depends(get_db)):
    """List all satellite data sources and their status."""
    result = await db.execute(select(SatelliteSource).order_by(SatelliteSource.priority))
    sources = result.scalars().all()

    if not sources:
        defaults = [
            {"name": "SENTINEL-2", "source_type": "OPTICAL", "priority": 10, "enabled": False},
            {"name": "SENTINEL-1", "source_type": "SAR", "priority": 20, "enabled": False},
            {"name": "CARTOSAT-3", "source_type": "OPTICAL", "priority": 30, "enabled": False},
            {"name": "CARTOSAT-2S", "source_type": "OPTICAL", "priority": 40, "enabled": False},
            {"name": "LANDSAT-9", "source_type": "OPTICAL", "priority": 50, "enabled": False},
            {"name": "RISAT-2B", "source_type": "SAR", "priority": 60, "enabled": False},
            {"name": "EOS-04", "source_type": "SAR", "priority": 70, "enabled": False},
            {"name": "OAM", "source_type": "COMMUNITY", "priority": 80, "enabled": True},
        ]
        for item in defaults:
            db.add(SatelliteSource(**item))
        await db.commit()
        result = await db.execute(select(SatelliteSource).order_by(SatelliteSource.priority))
        sources = result.scalars().all()

    return sources


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


@router.post("/jobs/{job_id}/mark-stale")
async def mark_job_stale(job_id: int, db: AsyncSession = Depends(get_db)):
    """Mark a stuck satellite job as failed so dashboards can recover."""
    result = await db.execute(select(SatelliteJob).where(SatelliteJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status not in {"RUNNING", "PENDING"}:
        return {"job_id": job.id, "status": job.status, "updated": False, "reason": "not_stale"}

    job.status = "FAILED"
    if not job.error_message:
        job.error_message = "Marked stale by admin"
    job.completed_at = datetime.now(timezone.utc)
    await db.commit()

    return {"job_id": job.id, "status": job.status, "updated": True}


@router.post("/trigger/{source_name}")
async def trigger_ingestion(source_name: str, db: AsyncSession = Depends(get_db)):
    """Manually trigger satellite ingestion for a specific source."""
    from app.models.satellite import SatelliteJob, SatelliteSource
    from app.services.satellite_manager import normalize_source_name
    from app.tasks.satellite_tasks import scan_satellite_bbox

    normalized = normalize_source_name(source_name)
    if normalized not in {"SENTINEL-2", "LANDSAT-9", "LANDSAT-8", "OAM"}:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source_name}")

    source_result = await db.execute(select(SatelliteSource).where(SatelliteSource.name == normalized))
    source = source_result.scalar_one_or_none()
    job = SatelliteJob(
        source_id=source.id if source else None,
        status="PENDING",
        bbox=_default_corridor_bbox(),
        tiles_total=0,
        tiles_processed=0,
        detections_count=0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    result = scan_satellite_bbox.delay(normalized, _default_corridor_bbox(), "corridor-scan", 12, 20.0, None, None, job.id, True)
    return {"task_id": result.id, "job_id": job.id, "source": normalized}


@router.get("/download-logs", response_model=list[SatelliteDownloadLogOut])
async def download_logs(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Recent satellite download logs."""
    from app.services.minio_client import get_presigned_url

    def _public_preview_url(path: str | None) -> str | None:
        if not path:
            return None
        return get_presigned_url(path, expires_hours=6).replace("http://minio:9000", "http://localhost/minio")

    result = await db.execute(
        select(SatelliteDownloadLog)
        .order_by(SatelliteDownloadLog.downloaded_at.desc())
        .limit(limit)
    )
    rows = result.scalars().all()
    return [
        {
            "id": row.id,
            "job_id": row.job_id,
            "source_name": row.source_name,
            "product_id": row.product_id,
            "file_path": row.file_path,
            "file_size_mb": row.file_size_mb,
            "downloaded_at": row.downloaded_at,
            "preview_url": _public_preview_url(row.file_path),
        }
        for row in rows
    ]


@router.get("/credentials-status", response_model=SatelliteCredentialStatusResponse)
async def credentials_status():
    """Show which credential keys are missing for each source type."""
    matrix = [
        ("SENTINEL-1", ["SENTINEL_USER", "SENTINEL_PASS"]),
        ("SENTINEL-2", ["SENTINEL_USER", "SENTINEL_PASS"]),
        ("CARTOSAT-3", ["BHOONIDHI_USERNAME", "BHOONIDHI_PASSWORD"]),
        ("CARTOSAT-2S", ["BHOONIDHI_USERNAME", "BHOONIDHI_PASSWORD"]),
        ("RISAT-2B", ["BHOONIDHI_USERNAME", "BHOONIDHI_PASSWORD"]),
        ("EOS-04", ["BHOONIDHI_USERNAME", "BHOONIDHI_PASSWORD"]),
        ("LANDSAT-9", []),
        ("ALOS-2", ["JAXA_AUIG2_USER", "JAXA_AUIG2_PASS"]),
        ("MODIS", ["NASA_EARTHDATA_USER", "NASA_EARTHDATA_PASS"]),
        ("OAM", []),
    ]

    items = []
    for source, keys in matrix:
        missing = []
        for key in keys:
            value = getattr(settings, key, "")
            if not _has_real_value(str(value)):
                missing.append(key)

        items.append(
            {
                "source": source,
                "keys_required": keys,
                "keys_missing": missing,
                "configured": len(missing) == 0,
            }
        )

    return {"items": items}


@router.post("/search", response_model=SatelliteSceneSearchResponse)
async def search_satellite_scenes(body: SatelliteSceneSearchRequest):
    from app.services.satellite_manager import normalize_source_name, search_satellite_scenes as search_fn

    bbox = _parse_bbox_string(body.bbox)
    source = normalize_source_name(body.source)
    if source not in {"SENTINEL-2", "LANDSAT-9", "LANDSAT-8", "OAM"}:
        raise HTTPException(status_code=400, detail=f"Preview/inference not supported for {body.source}")

    items = await search_fn(
        source,
        bbox,
        limit=body.limit,
        max_cloud=body.max_cloud,
        date_from=body.date_from,
        date_to=body.date_to,
    )
    return {"source": source, "count": len(items), "items": items[: body.limit]}


@router.post("/scan", response_model=SatelliteScanLaunchResponse)
async def launch_satellite_scan(body: SatelliteSceneSearchRequest, db: AsyncSession = Depends(get_db)):
    from app.models.satellite import SatelliteJob, SatelliteSource
    from app.services.satellite_manager import normalize_source_name
    from app.tasks.satellite_tasks import scan_satellite_bbox

    bbox = _parse_bbox_string(body.bbox)
    source = normalize_source_name(body.source)
    if source not in {"SENTINEL-2", "LANDSAT-9", "LANDSAT-8", "OAM"}:
        raise HTTPException(status_code=400, detail=f"Custom scan not supported for {body.source}")

    source_result = await db.execute(select(SatelliteSource).where(SatelliteSource.name == source))
    source_row = source_result.scalar_one_or_none()
    job = SatelliteJob(
        source_id=source_row.id if source_row else None,
        status="PENDING",
        bbox=bbox,
        tiles_total=0,
        tiles_processed=0,
        detections_count=0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    task = scan_satellite_bbox.delay(
        source,
        bbox,
        "custom-scan",
        body.limit,
        body.max_cloud,
        body.date_from,
        body.date_to,
        job.id,
        body.forward_to_inference,
    )
    return {"task_id": task.id, "job_id": job.id, "source": source, "bbox": body.bbox}


@router.post("/oam/search", response_model=OAMSearchResponse)
async def oam_search(body: OAMSearchRequest):
    """Preview OAM imagery availability for a custom bbox/date range."""
    from app.services.satellite_manager import query_openaerialmap

    bbox = _parse_bbox_string(body.bbox)
    items = await query_openaerialmap(
        bbox,
        min_resolution=body.min_resolution,
        limit=body.limit,
        acquired_from=body.date_from,
        acquired_to=body.date_to,
    )

    samples = [
        {"product_id": it.get("product_id"), "title": it.get("title")}
        for it in items[:10]
    ]
    return {"count": len(items), "samples": samples}


@router.post("/oam/trigger-custom", response_model=OAMTriggerResponse)
async def trigger_oam_custom(body: OAMSearchRequest):
    """Trigger OAM ingestion for a custom bbox/date range."""
    from app.tasks.drone_tasks import ingest_openaerialmap_bbox

    bbox = _parse_bbox_string(body.bbox)
    result = ingest_openaerialmap_bbox.delay(
        bbox,
        "custom",
        body.min_resolution,
        body.limit,
        body.date_from,
        body.date_to,
    )
    return {"task_id": result.id, "source": "oam", "bbox": body.bbox}
