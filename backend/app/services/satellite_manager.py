"""Satellite Data Manager — selects optimal satellite for each corridor."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlparse

import httpx
import numpy as np
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.satellite import SatelliteSource, SatelliteSelectionLog, SatelliteDownloadLog
from app.services.minio_client import upload_bytes

logger = structlog.get_logger(__name__)

SOURCE_ALIASES = {
    "sentinel2": "SENTINEL-2",
    "sentinel-2": "SENTINEL-2",
    "sentinel1": "SENTINEL-1",
    "sentinel-1": "SENTINEL-1",
    "landsat9": "LANDSAT-9",
    "landsat-9": "LANDSAT-9",
    "landsat8": "LANDSAT-8",
    "landsat-8": "LANDSAT-8",
    "oam": "OAM",
    "openaerialmap": "OAM",
    "cartosat3": "CARTOSAT-3",
    "cartosat-3": "CARTOSAT-3",
    "cartosat2s": "CARTOSAT-2S",
    "cartosat-2s": "CARTOSAT-2S",
    "risat2b": "RISAT-2B",
    "risat-2b": "RISAT-2B",
    "eos04": "EOS-04",
    "eos-04": "EOS-04",
    "modis": "MODIS",
}

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
                select(SatelliteSource).where(SatelliteSource.name == source_name)
            )
            source = result.scalar_one_or_none()
            if source is None or not source.enabled:
                considered.append({"source": source_name, "rejected": "disabled or not configured"})
                continue
            if not source.credentials:
                considered.append({"source": source_name, "rejected": "credentials not configured"})
                continue

            considered.append({"source": source_name, "selected": True, "resolution_m": resolution})

            # Log selection decision
            log_entry = SatelliteSelectionLog(
                selected_source=source_name,
                reason=f"Highest priority active source at {resolution}m resolution",
                candidates={"considered": considered, "highway": highway, "bbox": bbox, "use_sar": use_sar},
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
        file_path: str | None = None,
        file_size_mb: float | None = None,
        cloud_cover_pct: float | None = None,
        error_message: str | None = None,
    ) -> None:
        file_path = file_path or (f"{source}/{highway}/{product_id}" if success else None)
        log_entry = SatelliteDownloadLog(
            source_name=source,
            product_id=product_id,
            file_path=file_path,
            file_size_mb=file_size_mb,
        )
        self.db.add(log_entry)
        await self.db.flush()

    async def check_idempotency(self, source: str, product_id: str) -> bool:
        result = await self.db.execute(
            select(SatelliteDownloadLog).where(
                SatelliteDownloadLog.source_name == source,
                SatelliteDownloadLog.product_id == product_id,
            )
        )
        return result.scalar_one_or_none() is not None


def _has_real_creds(*values: str) -> bool:
    normalized = [v.strip() for v in values if isinstance(v, str)]
    if not normalized or any(not v for v in normalized):
        return False
    placeholders = ("your_", "optional_", "dev_", "change_me", "placeholder")
    return not any(any(v.lower().startswith(p) or p in v.lower() for p in placeholders) for v in normalized)


def normalize_source_name(source_name: str) -> str:
    key = (source_name or "").strip().lower()
    return SOURCE_ALIASES.get(key, (source_name or "").strip().upper())


def _bbox_center(bbox: list[float] | None) -> tuple[float | None, float | None]:
    if not bbox or len(bbox) != 4:
        return None, None
    return float((bbox[1] + bbox[3]) / 2.0), float((bbox[0] + bbox[2]) / 2.0)


def _sanitize_product_id(product_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", product_id or "scene")
    return cleaned.strip("_")[:180] or "scene"


def _normalize_temporal_value(value: str | None, end_of_day: bool = False) -> str | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    if "T" in raw:
        return raw
    suffix = "T23:59:59Z" if end_of_day else "T00:00:00Z"
    return f"{raw}{suffix}"


def _guess_extension(url: str, content_type: str | None = None) -> str:
    path = urlparse(url).path
    ext = Path(path).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"}:
        return ext
    if content_type:
        lowered = content_type.lower()
        if "png" in lowered:
            return ".png"
        if "jpeg" in lowered or "jpg" in lowered:
            return ".jpg"
        if "tiff" in lowered or "tif" in lowered:
            return ".tif"
    return ".jpg"


def _normalize_band_to_uint8(band: np.ndarray) -> np.ndarray:
    arr = band.astype(np.float32)
    arr = arr[np.isfinite(arr)] if np.issubdtype(arr.dtype, np.floating) else arr
    if arr.size == 0:
        return np.zeros_like(band, dtype=np.uint8)
    lo = float(np.percentile(arr, 2))
    hi = float(np.percentile(arr, 98))
    if hi <= lo:
        hi = lo + 1.0
    clipped = np.clip(band.astype(np.float32), lo, hi)
    norm = ((clipped - lo) / (hi - lo) * 255.0).astype(np.uint8)
    return norm


def _encode_rgb_preview(rgb: np.ndarray) -> bytes:
    import cv2

    ok, encoded = cv2.imencode(".jpg", rgb)
    if not ok:
        raise ValueError("Failed to encode preview image")
    return encoded.tobytes()


def _tile_raster_payload(
    payload: bytes,
    tile_size: int,
    overlap_pct: float,
) -> list[dict[str, Any]]:
    from rasterio.io import MemoryFile

    stride = max(64, int(tile_size * (1.0 - overlap_pct)))
    tiles: list[dict[str, Any]] = []

    with MemoryFile(payload) as mem_file:
        with mem_file.open() as dataset:
            width = int(dataset.width)
            height = int(dataset.height)
            transform = dataset.transform
            band_count = int(dataset.count)

            row_starts = list(range(0, max(1, height - tile_size + 1), stride))
            col_starts = list(range(0, max(1, width - tile_size + 1), stride))
            if row_starts[-1] != max(0, height - tile_size):
                row_starts.append(max(0, height - tile_size))
            if col_starts[-1] != max(0, width - tile_size):
                col_starts.append(max(0, width - tile_size))

            for row in row_starts:
                for col in col_starts:
                    row_end = min(height, row + tile_size)
                    col_end = min(width, col + tile_size)

                    window = ((row, row_end), (col, col_end))
                    data = dataset.read(window=window)
                    if data.size == 0:
                        continue

                    if band_count >= 3:
                        r = _normalize_band_to_uint8(data[0])
                        g = _normalize_band_to_uint8(data[1])
                        b = _normalize_band_to_uint8(data[2])
                        rgb = np.stack([r, g, b], axis=-1)
                    else:
                        gray = _normalize_band_to_uint8(data[0])
                        rgb = np.stack([gray, gray, gray], axis=-1)

                    tile_bytes = _encode_rgb_preview(rgb)

                    center_col = col + (col_end - col) / 2.0
                    center_row = row + (row_end - row) / 2.0
                    center_x, center_y = transform * (center_col, center_row)

                    tiles.append(
                        {
                            "bytes": tile_bytes,
                            "lat": float(center_y),
                            "lon": float(center_x),
                            "pixel_window": {
                                "row_start": int(row),
                                "row_end": int(row_end),
                                "col_start": int(col),
                                "col_end": int(col_end),
                            },
                        }
                    )

    return tiles


async def test_source_connection(source: SatelliteSource) -> dict[str, Any]:
    source_name = normalize_source_name(source.name or "")

    if not source.enabled:
        return {"success": False, "product_count": 0, "error": "Source is disabled"}

    if source_name in {"SENTINEL-2", "SENTINEL-1"}:
        ok = _has_real_creds(settings.CDSE_CLIENT_ID, settings.CDSE_CLIENT_SECRET) or _has_real_creds(
            settings.SENTINEL_USER, settings.SENTINEL_PASS
        )
        return {
            "success": ok,
            "product_count": None,
            "error": None if ok else "Set real CDSE_CLIENT_ID + CDSE_CLIENT_SECRET (or SENTINEL_USER + SENTINEL_PASS) in .env",
        }

    if source_name in {"CARTOSAT-3", "CARTOSAT-2S", "RISAT-2B", "EOS-04"}:
        return {
            "success": False,
            "product_count": 0,
            "error": "Bhoonidhi NRSC is browser-only — order data manually at https://bhoonidhi.nrsc.gov.in/",
        }

    if source_name in {"LANDSAT-9", "LANDSAT-8"}:
        # LandsatLook STAC API is public — no credentials required
        return {"success": True, "product_count": None, "error": None}

    if source_name in {"OAM", "OPENAERIALMAP"}:
        return {"success": True, "product_count": None, "error": None}

    return {"success": False, "product_count": 0, "error": f"No tester implemented for {source.name}"}


async def _cdse_bearer_token() -> str:
    """Get OAuth2 Bearer token from Copernicus Data Space Ecosystem using account credentials."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "cdse-public",
                "username": settings.SENTINEL_USER,
                "password": settings.SENTINEL_PASS,
            },
            timeout=30.0,
        )
        resp.raise_for_status()
        return resp.json()["access_token"]


async def download_sentinel2(bbox: dict[str, float], max_cloud: float = 20.0) -> list[dict[str, Any]]:
    """Query Sentinel-2 L2A products via Copernicus Data Space Ecosystem OData API."""
    token = await _cdse_bearer_token()
    footprint = (
        f"POLYGON(({bbox['lon_min']} {bbox['lat_min']},"
        f"{bbox['lon_max']} {bbox['lat_min']},"
        f"{bbox['lon_max']} {bbox['lat_max']},"
        f"{bbox['lon_min']} {bbox['lat_max']},"
        f"{bbox['lon_min']} {bbox['lat_min']}))"
    )
    start = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    filter_str = (
        f"Collection/Name eq 'SENTINEL-2' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{footprint}') and "
        f"ContentDate/Start gt {start} and ContentDate/Start lt {end} and "
        f"Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
        f"and att/OData.CSC.DoubleAttribute/Value le {max_cloud})"
    )
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as client:
        resp = await client.get(
            "https://catalogue.dataspace.copernicus.eu/odata/v1/Products",
            params={"$filter": filter_str, "$orderby": "ContentDate/Start desc", "$top": 20},
            timeout=60.0,
        )
        resp.raise_for_status()
        items = resp.json().get("value", [])
    return [{"product_id": item["Id"], "title": item["Name"], "cloud_cover": None} for item in items]


async def download_sentinel1_sar(bbox: dict[str, float]) -> list[dict[str, Any]]:
    """Query Sentinel-1 GRD IW mode products via CDSE OData API."""
    token = await _cdse_bearer_token()
    footprint = (
        f"POLYGON(({bbox['lon_min']} {bbox['lat_min']},"
        f"{bbox['lon_max']} {bbox['lat_min']},"
        f"{bbox['lon_max']} {bbox['lat_max']},"
        f"{bbox['lon_min']} {bbox['lat_max']},"
        f"{bbox['lon_min']} {bbox['lat_min']}))"
    )
    start = (datetime.now(timezone.utc) - timedelta(days=12)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    filter_str = (
        f"Collection/Name eq 'SENTINEL-1' and "
        f"OData.CSC.Intersects(area=geography'SRID=4326;{footprint}') and "
        f"ContentDate/Start gt {start} and ContentDate/Start lt {end} and "
        f"Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
        f"and att/OData.CSC.StringAttribute/Value eq 'GRD')"
    )
    async with httpx.AsyncClient(headers={"Authorization": f"Bearer {token}"}) as client:
        resp = await client.get(
            "https://catalogue.dataspace.copernicus.eu/odata/v1/Products",
            params={"$filter": filter_str, "$orderby": "ContentDate/Start desc", "$top": 20},
            timeout=60.0,
        )
        resp.raise_for_status()
        items = resp.json().get("value", [])
    return [{"product_id": item["Id"], "title": item["Name"]} for item in items]


async def query_bhoonidhi(satellite: str, bbox: dict[str, float]) -> list[dict[str, Any]]:
    """
    ISRO Bhoonidhi is a browser-based portal (https://bhoonidhi.nrsc.gov.in/) with no public
    programmatic API — it uses government SSO that cannot be automated with a simple API key.
    Data must be manually ordered from the portal. This function is a no-op placeholder.
    """
    await logger.awarn(
        "bhoonidhi_browser_only",
        satellite=satellite,
        message="Bhoonidhi NRSC requires browser login — download data manually at https://bhoonidhi.nrsc.gov.in/",
    )
    return []


async def query_landsat(bbox: dict[str, float], satellite: str = "landsat_9") -> list[dict[str, Any]]:
    """Query Landsat 8/9 Collection 2 Level-2 via USGS LandsatLook STAC API.
    No authentication required — public endpoint.
    M2M requires separate approval at https://ers.cr.usgs.gov/profilePersonalize/requestApi
    """
    collection = "landsat-c2l2-sr"  # Surface Reflectance (both Landsat 8 and 9)
    start = (datetime.now(timezone.utc) - timedelta(days=20)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        resp = await client.post(
            "https://landsatlook.usgs.gov/stac-server/search",
            json={
                "bbox": [bbox["lon_min"], bbox["lat_min"], bbox["lon_max"], bbox["lat_max"]],
                "datetime": f"{start}/{end}",
                "collections": [collection],
                "limit": 20,
            },
            timeout=60.0,
        )
        resp.raise_for_status()
        items = resp.json().get("features", [])
    return [{"product_id": item["id"], "title": item.get("id", "")} for item in items]


async def query_openaerialmap(
    bbox: dict[str, float],
    min_resolution: float = 0.5,
    limit: int = 50,
    acquired_from: str | None = None,
    acquired_to: str | None = None,
) -> list[dict[str, Any]]:
    """Query OpenAerialMap for community drone imagery."""
    async with httpx.AsyncClient() as client:
        params = {
            "bbox": f"{bbox['lon_min']},{bbox['lat_min']},{bbox['lon_max']},{bbox['lat_max']}",
            "resolution_from": 0,
            "resolution_to": min_resolution,
            "order_by": "-acquisition_end",
            "limit": max(1, min(limit, 200)),
        }
        if acquired_from:
            params["acquisition_from"] = acquired_from
        if acquired_to:
            params["acquisition_to"] = acquired_to

        response = await client.get("https://api.openaerialmap.org/meta", params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])

        # Fallback: if strict resolution yields no hits, retry without resolution caps.
        if not results:
            fallback = await client.get(
                "https://api.openaerialmap.org/meta",
                params={
                    "bbox": f"{bbox['lon_min']},{bbox['lat_min']},{bbox['lon_max']},{bbox['lat_max']}",
                    "order_by": "-acquisition_end",
                    "limit": max(1, min(limit, 200)),
                },
                timeout=30.0,
            )
            fallback.raise_for_status()
            results = fallback.json().get("results", [])

        normalized: list[dict[str, Any]] = []
        for item in results:
            product_id = item.get("uuid") or item.get("id") or item.get("_id")
            if not product_id:
                continue
            normalized.append(
                {
                    "product_id": str(product_id),
                    "title": item.get("title") or item.get("provider") or "OAM imagery",
                    "raw": item,
                }
            )

        return normalized


async def search_satellite_scenes(
    source_name: str,
    bbox: dict[str, float],
    limit: int = 12,
    max_cloud: float = 20.0,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    normalized = normalize_source_name(source_name)

    if normalized == "OAM":
        items = await query_openaerialmap(
            bbox,
            min_resolution=0.8,
            limit=limit,
            acquired_from=date_from,
            acquired_to=date_to,
        )
        scenes: list[dict[str, Any]] = []
        for item in items:
            raw = item.get("raw") or {}
            raw_bbox = raw.get("bbox") or (raw.get("geojson") or {}).get("bbox")
            lat, lon = _bbox_center(raw_bbox)
            asset_url = item.get("product_id") if str(item.get("product_id", "")).startswith("http") else raw.get("uuid")
            scenes.append(
                {
                    "product_id": str(item.get("product_id") or ""),
                    "title": item.get("title"),
                    "preview_url": (raw.get("properties") or {}).get("thumbnail"),
                    "asset_url": asset_url,
                    "captured_at": raw.get("acquisition_end") or raw.get("acquisition_start"),
                    "bbox": raw_bbox,
                    "lat": lat,
                    "lon": lon,
                    "gsd_m_per_px": raw.get("gsd"),
                    "raw": raw,
                }
            )
        return scenes

    if normalized in {"LANDSAT-9", "LANDSAT-8"}:
        start = _normalize_temporal_value(date_from) or (datetime.now(timezone.utc) - timedelta(days=20)).strftime("%Y-%m-%dT00:00:00Z")
        end = _normalize_temporal_value(date_to, end_of_day=True) or datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59Z")
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.post(
                "https://planetarycomputer.microsoft.com/api/stac/v1/search",
                json={
                    "bbox": [bbox["lon_min"], bbox["lat_min"], bbox["lon_max"], bbox["lat_max"]],
                    "datetime": f"{start}/{end}",
                    "collections": ["landsat-c2-l2"],
                    "limit": max(1, min(limit, 50)),
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            items = resp.json().get("features", [])

        scenes = []
        for item in items:
            platform = str((item.get("properties") or {}).get("platform") or "").upper().replace("-", "_")
            item_id = str(item.get("id") or "").upper()
            if normalized == "LANDSAT-9" and "LANDSAT_9" not in platform and not item_id.startswith("LC09"):
                continue
            if normalized == "LANDSAT-8" and "LANDSAT_8" not in platform and not item_id.startswith("LC08"):
                continue
            item_bbox = item.get("bbox")
            lat, lon = _bbox_center(item_bbox)
            rendered_preview = (
                f"https://planetarycomputer.microsoft.com/api/data/v1/item/preview.png"
                f"?collection=landsat-c2-l2&item={item.get('id')}"
                f"&assets=red&assets=green&assets=blue"
                f"&color_formula=gamma+RGB+2.7%2C+saturation+1.5%2C+sigmoidal+RGB+15+0.55&format=png"
            )
            scenes.append(
                {
                    "product_id": item.get("id"),
                    "title": item.get("id"),
                    "preview_url": rendered_preview,
                    "asset_url": rendered_preview,
                    "captured_at": (item.get("properties") or {}).get("datetime"),
                    "bbox": item_bbox,
                    "lat": lat,
                    "lon": lon,
                    "gsd_m_per_px": 30.0,
                    "raw": item,
                }
            )
        return scenes

    if normalized == "SENTINEL-2":
        start = _normalize_temporal_value(date_from) or (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%dT00:00:00Z")
        end = _normalize_temporal_value(date_to, end_of_day=True) or datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59Z")
        async with httpx.AsyncClient(follow_redirects=True) as client:
            resp = await client.post(
                "https://earth-search.aws.element84.com/v1/search",
                json={
                    "bbox": [bbox["lon_min"], bbox["lat_min"], bbox["lon_max"], bbox["lat_max"]],
                    "datetime": f"{start}/{end}",
                    "collections": ["sentinel-2-c1-l2a"],
                    "limit": max(1, min(limit, 50)),
                    "query": {"eo:cloud_cover": {"lte": max_cloud}},
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            items = resp.json().get("features", [])

        scenes = []
        for item in items:
            item_bbox = item.get("bbox")
            centroid = ((item.get("properties") or {}).get("proj:centroid") or {})
            lat = centroid.get("lat")
            lon = centroid.get("lon")
            if lat is None or lon is None:
                lat, lon = _bbox_center(item_bbox)
            assets = item.get("assets") or {}
            scenes.append(
                {
                    "product_id": item.get("id"),
                    "title": item.get("id"),
                    "preview_url": ((assets.get("thumbnail") or {}).get("href")
                                    or (assets.get("preview") or {}).get("href")),
                    "asset_url": ((assets.get("thumbnail") or {}).get("href")
                                  or (assets.get("preview") or {}).get("href")
                                  or (assets.get("visual") or {}).get("href")
                                  or (assets.get("thumbnail") or {}).get("href")),
                    "captured_at": (item.get("properties") or {}).get("datetime"),
                    "bbox": item_bbox,
                    "lat": float(lat) if lat is not None else None,
                    "lon": float(lon) if lon is not None else None,
                    "gsd_m_per_px": 10.0,
                    "raw": item,
                }
            )
        return scenes

    if normalized == "MODIS":
        return []

    return []


async def materialize_satellite_scene(source_name: str, scene: dict[str, Any], job_id: int | None = None) -> dict[str, Any]:
    asset_url = scene.get("asset_url") or scene.get("preview_url")
    if not asset_url:
        raise ValueError(f"No downloadable asset URL for {source_name} scene {scene.get('product_id')}")

    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(asset_url, timeout=120.0)
        response.raise_for_status()
        payload = response.content
        content_type = response.headers.get("content-type", "application/octet-stream")

    if "text/html" in content_type.lower():
        raise ValueError(f"Provider returned HTML instead of imagery for {scene.get('product_id')}")

    source_slug = normalize_source_name(source_name).lower().replace("-", "_")
    product_slug = _sanitize_product_id(str(scene.get("product_id") or "scene"))
    extension = _guess_extension(asset_url, content_type)
    prefix = f"satellite/{source_slug}"
    if job_id is not None:
        prefix = f"{prefix}/job_{job_id}"
    object_name = f"{prefix}/{product_slug}{extension}"

    tile_paths: list[str] = []
    tile_contexts: list[dict[str, Any]] = []

    is_tiff = extension in {".tif", ".tiff"} or "tiff" in content_type.lower()
    if is_tiff:
        from app.config import settings

        tiles = _tile_raster_payload(payload, settings.TILE_SIZE, settings.TILE_OVERLAP_PCT)
        for idx, tile in enumerate(tiles):
            tile_path = f"{prefix}/tiles/{product_slug}_tile_{idx:04d}.jpg"
            upload_bytes(tile_path, tile["bytes"], content_type="image/jpeg")
            tile_paths.append(tile_path)
            tile_contexts.append(
                {
                    "lat": tile.get("lat"),
                    "lon": tile.get("lon"),
                    "pixel_window": tile.get("pixel_window"),
                }
            )

        if tiles:
            object_name = tile_paths[0]
        else:
            upload_bytes(object_name, payload, content_type=content_type)
    else:
        upload_bytes(object_name, payload, content_type=content_type)

    return {
        "file_path": object_name,
        "tile_paths": tile_paths,
        "tile_contexts": tile_contexts,
        "file_size_mb": round(len(payload) / 1024 / 1024, 3),
        "content_type": content_type,
    }
