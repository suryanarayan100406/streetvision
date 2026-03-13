"""Satellite ingestion tasks — all satellite sources."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.tasks.celery_app import app
from app.database import async_session_factory

logger = structlog.get_logger(__name__)

# Highway corridor bounding boxes for Chhattisgarh targets
HIGHWAY_CORRIDORS = {
    "NH-30": {"lat_min": 21.24, "lat_max": 22.09, "lon_min": 81.60, "lon_max": 82.15, "length_km": 115},
    "NH-53": {"lat_min": 20.50, "lat_max": 21.25, "lon_min": 80.90, "lon_max": 81.70, "length_km": 180},
    "NH-130C": {"lat_min": 21.10, "lat_max": 22.00, "lon_min": 81.30, "lon_max": 82.00, "length_km": 140},
}


def _corridor_union_bbox() -> dict[str, float]:
    return {
        "lat_min": min(item["lat_min"] for item in HIGHWAY_CORRIDORS.values()),
        "lat_max": max(item["lat_max"] for item in HIGHWAY_CORRIDORS.values()),
        "lon_min": min(item["lon_min"] for item in HIGHWAY_CORRIDORS.values()),
        "lon_max": max(item["lon_max"] for item in HIGHWAY_CORRIDORS.values()),
    }


async def _run_manual_satellite_scan(
    source_name: str,
    bbox: dict[str, float],
    label: str,
    limit: int = 12,
    max_cloud: float = 20.0,
    date_from: str | None = None,
    date_to: str | None = None,
    job_id: int | None = None,
    forward_to_inference: bool = True,
) -> dict:
    from app.models.satellite import SatelliteDownloadLog, SatelliteJob, SatelliteSource
    from app.services.satellite_manager import (
        materialize_satellite_scene,
        normalize_source_name,
        search_satellite_scenes,
    )
    from app.tasks.cctv_tasks import run_inference_on_tile

    normalized_source = normalize_source_name(source_name)

    async with async_session_factory() as db:
        source_row = None
        result = await db.execute(select(SatelliteSource).where(SatelliteSource.name == normalized_source))
        source_row = result.scalar_one_or_none()

        job = None
        if job_id is not None:
            job = await db.get(SatelliteJob, job_id)
        if job is None:
            job = SatelliteJob(
                source_id=source_row.id if source_row else None,
                status="RUNNING",
                bbox=bbox,
                tiles_total=0,
                tiles_processed=0,
                detections_count=0,
            )
            db.add(job)
            await db.flush()

        job.status = "RUNNING"
        job.bbox = bbox
        await db.commit()

        try:
            scenes = await search_satellite_scenes(
                normalized_source,
                bbox,
                limit=limit,
                max_cloud=max_cloud,
                date_from=date_from,
                date_to=date_to,
            )
        except Exception as exc:
            job = await db.get(SatelliteJob, job.id)
            job.status = "FAILED"
            job.error_message = str(exc)
            job.completed_at = datetime.now(timezone.utc)
            if source_row is not None:
                source_row.error_count = int(source_row.error_count or 0) + 1
            await db.commit()
            raise

        job = await db.get(SatelliteJob, job.id)
        job.tiles_total = 0
        job.tiles_processed = 0
        job.detections_count = 0
        await db.commit()

        queued = 0
        for scene in scenes:
            try:
                materialized = await materialize_satellite_scene(normalized_source, scene, job_id=job.id)
                dispatch_paths = materialized.get("tile_paths") or [materialized["file_path"]]
                dispatch_contexts = materialized.get("tile_contexts") or []

                log_entry = SatelliteDownloadLog(
                    job_id=job.id,
                    source_name=normalized_source,
                    product_id=str(scene.get("product_id") or ""),
                    file_path=materialized["file_path"],
                    file_size_mb=materialized.get("file_size_mb"),
                )
                db.add(log_entry)

                job = await db.get(SatelliteJob, job.id)
                job.tiles_total = int(job.tiles_total or 0) + len(dispatch_paths)
                await db.commit()

                if forward_to_inference:
                    for idx, tile_path in enumerate(dispatch_paths):
                        tile_ctx = dispatch_contexts[idx] if idx < len(dispatch_contexts) else {}
                        run_inference_on_tile.delay(
                            tile_path,
                            normalized_source,
                            label,
                            job.id,
                            {
                                "lat": tile_ctx.get("lat", scene.get("lat")),
                                "lon": tile_ctx.get("lon", scene.get("lon")),
                                "bbox": scene.get("bbox"),
                                "gsd_m_per_px": scene.get("gsd_m_per_px"),
                                "captured_at": scene.get("captured_at"),
                                "preview_url": scene.get("preview_url"),
                                "asset_url": scene.get("asset_url"),
                                "product_id": scene.get("product_id"),
                                "title": scene.get("title"),
                                "tile_index": idx,
                                "tile_path": tile_path,
                                "pixel_window": tile_ctx.get("pixel_window"),
                            },
                        )
                else:
                    job = await db.get(SatelliteJob, job.id)
                    job.tiles_processed = int(job.tiles_processed or 0) + len(dispatch_paths)
                    await db.commit()

                queued += len(dispatch_paths)
            except Exception as exc:
                db.add(
                    SatelliteDownloadLog(
                        job_id=job.id,
                        source_name=normalized_source,
                        product_id=str(scene.get("product_id") or ""),
                        file_path=None,
                        file_size_mb=None,
                    )
                )
                job = await db.get(SatelliteJob, job.id)
                job.error_message = str(exc)
                await db.commit()

        job = await db.get(SatelliteJob, job.id)
        if source_row is not None and queued > 0:
            source_row.last_successful_at = datetime.now(timezone.utc)
            source_row.error_count = 0
        elif source_row is not None and queued == 0:
            source_row.error_count = int(source_row.error_count or 0) + 1

        if not forward_to_inference or job.tiles_total == 0:
            job.status = "COMPLETED"
            job.completed_at = datetime.now(timezone.utc)
        await db.commit()
        return {"source": normalized_source, "job_id": job.id, "images_queued": queued, "tiles_total": job.tiles_total}


async def _run_satellite_ingestion(source_name: str, query_func, **kwargs) -> dict:
    """Common satellite ingestion pipeline."""
    async with async_session_factory() as db:
        from app.services.satellite_manager import SatelliteDataManager

        manager = SatelliteDataManager(db)
        total_products = 0
        total_detections = 0

        for highway, bbox in HIGHWAY_CORRIDORS.items():
            try:
                products = await query_func(bbox, **kwargs)
                for product in products:
                    product_id = product.get("product_id", "")
                    if await manager.check_idempotency(source_name, product_id):
                        continue

                    # Log download and queue inference
                    await manager.log_download(source_name, product_id, highway, success=True)

                    from app.tasks.cctv_tasks import run_inference_on_tile
                    run_inference_on_tile.delay(product_id, source_name, highway)
                    total_products += 1

                await db.commit()
            except Exception as exc:
                await logger.aexception(
                    "satellite_ingestion_error", source=source_name, highway=highway, error=str(exc)
                )
                await manager.log_download(source_name, "N/A", highway, success=False, error_message=str(exc))
                await db.commit()

    return {"source": source_name, "products": total_products}


@app.task(name="app.tasks.satellite_tasks.ingest_sentinel2", bind=True)
def ingest_sentinel2(self):
    return asyncio.get_event_loop().run_until_complete(
        _run_manual_satellite_scan("SENTINEL-2", _corridor_union_bbox(), "corridor-scan", max_cloud=20.0)
    )


@app.task(name="app.tasks.satellite_tasks.ingest_sentinel1_sar", bind=True)
def ingest_sentinel1_sar(self):
    from app.services.satellite_manager import download_sentinel1_sar
    return asyncio.get_event_loop().run_until_complete(
        _run_satellite_ingestion("SENTINEL-1", download_sentinel1_sar)
    )


@app.task(name="app.tasks.satellite_tasks.ingest_cartosat3", bind=True)
def ingest_cartosat3(self):
    from app.services.satellite_manager import query_bhoonidhi
    return asyncio.get_event_loop().run_until_complete(
        _run_satellite_ingestion("CARTOSAT-3", query_bhoonidhi, satellite="CARTOSAT-3")
    )


@app.task(name="app.tasks.satellite_tasks.ingest_cartosat2s", bind=True)
def ingest_cartosat2s(self):
    from app.services.satellite_manager import query_bhoonidhi
    return asyncio.get_event_loop().run_until_complete(
        _run_satellite_ingestion("CARTOSAT-2S", query_bhoonidhi, satellite="CARTOSAT-2S")
    )


@app.task(name="app.tasks.satellite_tasks.ingest_landsat9", bind=True)
def ingest_landsat9(self):
    return asyncio.get_event_loop().run_until_complete(
        _run_manual_satellite_scan("LANDSAT-9", _corridor_union_bbox(), "corridor-scan")
    )


@app.task(name="app.tasks.satellite_tasks.ingest_risat2b", bind=True)
def ingest_risat2b(self):
    from app.services.satellite_manager import query_bhoonidhi
    return asyncio.get_event_loop().run_until_complete(
        _run_satellite_ingestion("RISAT-2B", query_bhoonidhi, satellite="RISAT-2B")
    )


@app.task(name="app.tasks.satellite_tasks.ingest_eos04", bind=True)
def ingest_eos04(self):
    from app.services.satellite_manager import query_bhoonidhi
    return asyncio.get_event_loop().run_until_complete(
        _run_satellite_ingestion("EOS-04", query_bhoonidhi, satellite="EOS-04")
    )


@app.task(name="app.tasks.satellite_tasks.ingest_oam", bind=True)
def ingest_oam(self):
    return asyncio.get_event_loop().run_until_complete(
        _run_manual_satellite_scan("OAM", _corridor_union_bbox(), "corridor-scan")
    )


@app.task(name="app.tasks.satellite_tasks.scan_satellite_bbox", bind=True)
def scan_satellite_bbox(
    self,
    source_name: str,
    bbox: dict,
    label: str = "custom",
    limit: int = 12,
    max_cloud: float = 20.0,
    date_from: str | None = None,
    date_to: str | None = None,
    job_id: int | None = None,
    forward_to_inference: bool = True,
):
    return asyncio.get_event_loop().run_until_complete(
        _run_manual_satellite_scan(
            source_name,
            bbox,
            label,
            limit=limit,
            max_cloud=max_cloud,
            date_from=date_from,
            date_to=date_to,
            job_id=job_id,
            forward_to_inference=forward_to_inference,
        )
    )


@app.task(name="app.tasks.satellite_tasks.ingest_alos2", bind=True)
def ingest_alos2(self):
    """ALOS-2 PALSAR-2 L-band SAR for sub-surface detection."""
    async def _query_alos2(bbox, **kw):
        import httpx
        from app.config import settings
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://auig2.jaxa.jp/openam/json/realms/root/realms/a2gp/authenticate",
                auth=(settings.JAXA_AUIG2_USER, settings.JAXA_AUIG2_PASS),
                timeout=60.0,
            )
        return []  # Parsed from JAXA API response
    return asyncio.get_event_loop().run_until_complete(
        _run_satellite_ingestion("ALOS-2", _query_alos2)
    )


@app.task(name="app.tasks.satellite_tasks.ingest_modis", bind=True)
def ingest_modis(self):
    """MODIS MOD11A1 land surface temperature — daily via NASA CMR API."""
    async def _query_modis(bbox, **kw):
        import httpx
        from app.config import settings
        from datetime import timedelta

        now = datetime.now(timezone.utc)
        temporal = (
            f"{(now - timedelta(days=5)).strftime('%Y-%m-%dT00:00:00Z')},"
            f"{now.strftime('%Y-%m-%dT23:59:59Z')}"
        )
        headers: dict = {}
        token = settings.NASA_EARTHDATA_TOKEN.strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif settings.NASA_EARTHDATA_USER and settings.NASA_EARTHDATA_PASS:
            import base64
            creds = base64.b64encode(
                f"{settings.NASA_EARTHDATA_USER}:{settings.NASA_EARTHDATA_PASS}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {creds}"

        async with httpx.AsyncClient(headers=headers, follow_redirects=True) as client:
            resp = await client.get(
                "https://cmr.earthdata.nasa.gov/search/granules.json",
                params={
                    "short_name": "MOD11A1",
                    "version": "061",
                    "bounding_box": (
                        f"{bbox['lon_min']},{bbox['lat_min']},"
                        f"{bbox['lon_max']},{bbox['lat_max']}"
                    ),
                    "temporal": temporal,
                    "page_size": 20,
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            items = resp.json().get("feed", {}).get("entry", [])
        return [{"product_id": item["id"], "title": item.get("title", "")} for item in items]

    return asyncio.get_event_loop().run_until_complete(
        _run_satellite_ingestion("MODIS", _query_modis)
    )
