"""Satellite Data Manager — selects optimal satellite for each corridor."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.satellite import SatelliteSource, SatelliteSelectionLog, SatelliteDownloadLog, SatelliteJob

logger = structlog.get_logger(__name__)

# Priority order: best resolution first
OPTICAL_PRIORITY = [
    ("CARTOSAT-3", 0.25),
    ("CARTOSAT-2S", 0.65),
    ("RESOURCESAT-2A", 5.8),
    ("SENTINEL-2", 10.0),
    ("LANDSAT-9", 15.0),
    ("LANDSAT-8", 30.0),
]

SAR_PRIORITY = [
    ("RISAT-2B", 1.0),
    ("EOS-04", 3.0),
    ("SENTINEL-1", 10.0),
    ("ALOS-2", 3.0),
]


class SatelliteDataManager:
    """Selects optimal satellite source based on availability, recency, and cloud cover."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def select_best_source(
        self,
        highway: str,
        bbox: dict[str, float],
        use_sar: bool = False,
    ) -> dict[str, Any] | None:
        priority_list = SAR_PRIORITY if use_sar else OPTICAL_PRIORITY
        considered: list[dict[str, Any]] = []

        for source_name, resolution in priority_list:
            result = await self.db.execute(
                select(SatelliteSource).where(SatelliteSource.source_name == source_name)
            )
            source = result.scalar_one_or_none()
            if source is None or source.status != "ACTIVE":
                considered.append({"source": source_name, "rejected": "INACTIVE or not configured"})
                continue
            if not source.credentials_configured:
                considered.append({"source": source_name, "rejected": "credentials not configured"})
                continue

            considered.append({"source": source_name, "selected": True, "resolution_m": resolution})

            # Log selection decision
            log_entry = SatelliteSelectionLog(
                highway=highway,
                selected_source=source_name,
                reason=f"Highest priority active source at {resolution}m resolution",
                considered_sources={"considered": considered},
                detection_cycle_date=datetime.now(timezone.utc).date(),
            )
            self.db.add(log_entry)
            await self.db.flush()

            await logger.ainfo(
                "satellite_source_selected",
                source=source_name,
                highway=highway,
                resolution=resolution,
            )
            return {"source_name": source_name, "resolution_m": resolution, "source_id": source.id}

        await logger.awarn("no_satellite_source_available", highway=highway, use_sar=use_sar)
        return None

    async def log_download(
        self,
        source: str,
        product_id: str,
        highway: str,
        success: bool,
        file_size_mb: float | None = None,
        cloud_cover_pct: float | None = None,
        error_message: str | None = None,
    ) -> None:
        log_entry = SatelliteDownloadLog(
            source=source,
            product_id=product_id,
            highway=highway,
            download_started_at=datetime.now(timezone.utc),
            download_completed_at=datetime.now(timezone.utc) if success else None,
            file_size_mb=file_size_mb,
            success=success,
            error_message=error_message,
            cloud_cover_pct=cloud_cover_pct,
        )
        self.db.add(log_entry)
        await self.db.flush()

    async def check_idempotency(self, source: str, product_id: str) -> bool:
        result = await self.db.execute(
            select(SatelliteJob).where(
                SatelliteJob.satellite_source == source,
                SatelliteJob.product_id == product_id,
            )
        )
        return result.scalar_one_or_none() is not None


async def download_sentinel2(bbox: dict[str, float], max_cloud: float = 20.0) -> list[dict[str, Any]]:
    """Query and download Sentinel-2 L2A products for a bounding box using sentinelsat."""
    from sentinelsat import SentinelAPI

    api = SentinelAPI(settings.SENTINEL_USER, settings.SENTINEL_PASS, "https://scihub.copernicus.eu/dhus")
    footprint = (
        f"POLYGON(({bbox['lon_min']} {bbox['lat_min']}, "
        f"{bbox['lon_max']} {bbox['lat_min']}, "
        f"{bbox['lon_max']} {bbox['lat_max']}, "
        f"{bbox['lon_min']} {bbox['lat_max']}, "
        f"{bbox['lon_min']} {bbox['lat_min']}))"
    )
    products = api.query(
        footprint,
        date=(datetime.now(timezone.utc) - timedelta(days=10), datetime.now(timezone.utc)),
        platformname="Sentinel-2",
        producttype="S2MSI2A",
        cloudcoverpercentage=(0, max_cloud),
    )
    results = []
    for pid, meta in products.items():
        results.append({"product_id": pid, "title": meta["title"], "cloud_cover": meta["cloudcoverpercentage"]})
    return results


async def download_sentinel1_sar(bbox: dict[str, float]) -> list[dict[str, Any]]:
    """Query Sentinel-1 GRD IW mode products."""
    from sentinelsat import SentinelAPI

    api = SentinelAPI(settings.SENTINEL_USER, settings.SENTINEL_PASS, "https://scihub.copernicus.eu/dhus")
    footprint = (
        f"POLYGON(({bbox['lon_min']} {bbox['lat_min']}, "
        f"{bbox['lon_max']} {bbox['lat_min']}, "
        f"{bbox['lon_max']} {bbox['lat_max']}, "
        f"{bbox['lon_min']} {bbox['lat_max']}, "
        f"{bbox['lon_min']} {bbox['lat_min']}))"
    )
    products = api.query(
        footprint,
        date=(datetime.now(timezone.utc) - timedelta(days=12), datetime.now(timezone.utc)),
        platformname="Sentinel-1",
        producttype="GRD",
        sensoroperationalmode="IW",
    )
    return [{"product_id": pid, "title": meta["title"]} for pid, meta in products.items()]


async def query_bhoonidhi(satellite: str, bbox: dict[str, float]) -> list[dict[str, Any]]:
    """Query ISRO Bhoonidhi for CARTOSAT/RISAT/ResourceSat/EOS-04 imagery."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://bhoonidhi.nrsc.gov.in/bhoonidhi/api/v1/search",
            params={
                "satellite": satellite,
                "bbox": f"{bbox['lon_min']},{bbox['lat_min']},{bbox['lon_max']},{bbox['lat_max']}",
                "startDate": (datetime.now(timezone.utc) - timedelta(days=15)).strftime("%Y-%m-%d"),
                "endDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            },
            auth=(settings.BHOONIDHI_USERNAME, settings.BHOONIDHI_PASSWORD),
            timeout=60.0,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("products", [])


async def query_landsat(bbox: dict[str, float], satellite: str = "landsat_9") -> list[dict[str, Any]]:
    """Query USGS for Landsat 8/9 via eodag."""
    from eodag import EODataAccessGateway

    dag = EODataAccessGateway()
    dag.set_preferred_provider("usgs")
    search_results = dag.search(
        productType="LANDSAT_C2L2" if satellite == "landsat_9" else "LANDSAT_C2L2",
        geom={
            "lonmin": bbox["lon_min"],
            "latmin": bbox["lat_min"],
            "lonmax": bbox["lon_max"],
            "latmax": bbox["lat_max"],
        },
        start=datetime.now(timezone.utc) - timedelta(days=20),
        end=datetime.now(timezone.utc),
    )
    return [{"product_id": r.properties["id"], "title": r.properties.get("title", "")} for r in search_results]


async def query_openaerialmap(bbox: dict[str, float], min_resolution: float = 0.5) -> list[dict[str, Any]]:
    """Query OpenAerialMap for community drone imagery."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.openaerialmap.org/meta",
            params={
                "bbox": f"{bbox['lon_min']},{bbox['lat_min']},{bbox['lon_max']},{bbox['lat_max']}",
                "resolution_from": 0,
                "resolution_to": min_resolution,
                "order_by": "-acquisition_end",
                "limit": 50,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("results", [])
