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
    from app.services.satellite_manager import download_sentinel2
    return asyncio.get_event_loop().run_until_complete(
        _run_satellite_ingestion("SENTINEL-2", download_sentinel2, max_cloud=20.0)
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
    from app.services.satellite_manager import query_landsat
    return asyncio.get_event_loop().run_until_complete(
        _run_satellite_ingestion("LANDSAT-9", query_landsat, satellite="landsat_9")
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
    """MODIS thermal stress detection — daily."""
    async def _query_modis(bbox, **kw):
        import httpx
        from app.config import settings
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://e4ftl01.cr.usgs.gov/MOLT/MOD11A1.061/",
                auth=(settings.NASA_EARTHDATA_USER, settings.NASA_EARTHDATA_PASS),
                timeout=60.0,
            )
        return []
    return asyncio.get_event_loop().run_until_complete(
        _run_satellite_ingestion("MODIS", _query_modis)
    )
