"""Weather data service — IMD, Open-Meteo, GFS, OpenWeatherMap."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from app.config import settings

logger = structlog.get_logger(__name__)

# IMD station IDs for Chhattisgarh
IMD_STATIONS = {"Raipur": "42900", "Bilaspur": "42997", "Durg": "42895"}


async def fetch_imd_weather(station_id: str) -> dict[str, Any]:
    """Fetch current weather from IMD for a station. Completely free, no key."""
    url = f"https://city.imd.gov.in/citywx/city_weather_crop.php?id={station_id}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()
        # Parse HTML response for weather data
        html = response.text
        return {"station_id": station_id, "raw_html": html, "fetched_at": datetime.now(timezone.utc).isoformat()}


async def fetch_imd_warnings() -> dict[str, Any]:
    """Fetch heavy rain warnings from IMD. Completely free."""
    url = "https://mausam.imd.gov.in/imd_latest/contents/warning.php"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=30.0)
        response.raise_for_status()
        return {"raw_html": response.text, "fetched_at": datetime.now(timezone.utc).isoformat()}


async def fetch_open_meteo(lat: float, lon: float) -> dict[str, Any]:
    """Fetch 48-hour forecast from Open-Meteo. Completely free, no API key."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation,precipitation_probability,cloudcover,weathercode",
        "forecast_days": 2,
        "timezone": "Asia/Kolkata",
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=30.0)
        response.raise_for_status()
        data = response.json()
        hourly = data.get("hourly", {})
        precip_values = hourly.get("precipitation", [])
        total_48h = sum(p for p in precip_values if p is not None)
        return {
            "total_precipitation_48h_mm": round(total_48h, 2),
            "hourly": hourly,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }


async def fetch_gfs_forecast(lat: float, lon: float) -> dict[str, Any]:
    """Fetch GFS 7-day accumulated precipitation. Completely free."""
    try:
        from herbie import Herbie

        H = Herbie(datetime.now(timezone.utc).strftime("%Y-%m-%d"), model="gfs", product="pgrb2.0p25", fxx=168)
        ds = H.xarray(":APCP:surface")
        # Extract value at nearest grid point
        apcp = float(ds["APCP_surface"].sel(latitude=lat, longitude=lon % 360, method="nearest").values)
        return {"gfs_rain_7d_mm": round(apcp, 2), "fetched_at": datetime.now(timezone.utc).isoformat()}
    except Exception as exc:
        await logger.aexception("gfs_fetch_failed", error=str(exc))
        return {"gfs_rain_7d_mm": 0.0, "error": str(exc)}


async def fetch_openweathermap(lat: float, lon: float) -> dict[str, Any]:
    """Fetch current weather from OpenWeatherMap free tier."""
    if not settings.OPENWEATHERMAP_API_KEY:
        return {"error": "API key not configured"}
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {"lat": lat, "lon": lon, "appid": settings.OPENWEATHERMAP_API_KEY, "units": "metric"}
    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        return response.json()


def should_apply_rain_flag(
    imd_warning: str | None,
    open_meteo_48h_mm: float,
    gfs_7d_mm: float,
) -> bool:
    """Determine if rain flag should be activated."""
    if imd_warning in ("Orange", "Red"):
        return True
    if open_meteo_48h_mm > 10.0:
        return True
    if gfs_7d_mm > 50.0:
        return True
    return False
