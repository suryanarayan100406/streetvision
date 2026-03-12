"""Weather data fetch tasks."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog

from app.tasks.celery_app import app
from app.database import async_session_factory

logger = structlog.get_logger(__name__)

# Grid cells centered on highway corridors
WEATHER_GRID_CELLS = [
    {"lat": 21.25, "lon": 81.63, "name": "Raipur"},
    {"lat": 22.08, "lon": 82.14, "name": "Bilaspur"},
    {"lat": 21.19, "lon": 81.28, "name": "Durg"},
    {"lat": 20.70, "lon": 81.10, "name": "Rajnandgaon"},
    {"lat": 21.70, "lon": 81.90, "name": "Janjgir"},
]


@app.task(name="app.tasks.weather_tasks.fetch_imd", bind=True)
def fetch_imd(self):
    """Fetch IMD weather for all stations. Every 3 hours."""

    async def _fetch():
        from app.services.weather_service import fetch_imd_weather, fetch_imd_warnings, IMD_STATIONS

        results = {}
        for name, station_id in IMD_STATIONS.items():
            try:
                data = await fetch_imd_weather(station_id)
                results[name] = {"status": "ok"}
            except Exception as exc:
                results[name] = {"status": "error", "error": str(exc)}

        try:
            warnings = await fetch_imd_warnings()
            results["warnings"] = {"status": "ok"}
        except Exception as exc:
            results["warnings"] = {"status": "error", "error": str(exc)}

        return results

    return asyncio.get_event_loop().run_until_complete(_fetch())


@app.task(name="app.tasks.weather_tasks.fetch_openmeteo", bind=True)
def fetch_openmeteo(self):
    """Fetch Open-Meteo 48-hour forecast. Every 6 hours. Completely free."""

    async def _fetch():
        from app.services.weather_service import fetch_open_meteo, should_apply_rain_flag
        from app.models.weather import WeatherCache
        from sqlalchemy import select
        from app.models.pothole import Pothole

        results = {}
        async with async_session_factory() as db:
            for cell in WEATHER_GRID_CELLS:
                try:
                    data = await fetch_open_meteo(cell["lat"], cell["lon"])
                    rain_48h = data.get("total_precipitation_48h_mm", 0)

                    # Update weather cache
                    cache = WeatherCache(
                        forecast_rain_48h_mm=rain_48h,
                        open_meteo_rain_48h_mm=rain_48h,
                        forecast_date=datetime.now(timezone.utc).date(),
                        checked_at=datetime.now(timezone.utc),
                        raw_openmeteo_response=data,
                    )
                    db.add(cache)

                    # Apply rain flags to potholes in range
                    if rain_48h > 10.0:
                        potholes = await db.execute(
                            select(Pothole).where(
                                Pothole.district.ilike(f"%{cell['name']}%")
                            )
                        )
                        for p in potholes.scalars():
                            p.rain_flag = True

                    results[cell["name"]] = {"rain_48h_mm": rain_48h}
                except Exception as exc:
                    results[cell["name"]] = {"error": str(exc)}

            await db.commit()
        return results

    return asyncio.get_event_loop().run_until_complete(_fetch())


@app.task(name="app.tasks.weather_tasks.fetch_gfs", bind=True)
def fetch_gfs(self):
    """Fetch GFS 7-day accumulated precipitation. Pre-monsoon early warning."""

    async def _fetch():
        from app.services.weather_service import fetch_gfs_forecast

        results = {}
        for cell in WEATHER_GRID_CELLS:
            try:
                data = await fetch_gfs_forecast(cell["lat"], cell["lon"])
                results[cell["name"]] = data
            except Exception as exc:
                results[cell["name"]] = {"error": str(exc)}
        return results

    return asyncio.get_event_loop().run_until_complete(_fetch())


@app.task(name="app.tasks.weather_tasks.fetch_openweathermap", bind=True)
def fetch_openweathermap(self):
    """Fetch OpenWeatherMap as tiebreaker. Free tier 1000 calls/day."""

    async def _fetch():
        from app.services.weather_service import fetch_openweathermap

        results = {}
        for cell in WEATHER_GRID_CELLS:
            try:
                data = await fetch_openweathermap(cell["lat"], cell["lon"])
                results[cell["name"]] = {"status": "ok"}
            except Exception as exc:
                results[cell["name"]] = {"error": str(exc)}
        return results

    return asyncio.get_event_loop().run_until_complete(_fetch())
