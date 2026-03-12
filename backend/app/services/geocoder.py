"""Geocoding service using self-hosted Nominatim."""

from __future__ import annotations

from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

NOMINATIM_URL = "http://nominatim:8080"


async def reverse_geocode(lat: float, lon: float) -> dict[str, Any]:
    """Reverse geocode GPS to road name, district, landmark using self-hosted Nominatim."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{NOMINATIM_URL}/reverse",
            params={
                "lat": lat,
                "lon": lon,
                "format": "jsonv2",
                "addressdetails": 1,
                "zoom": 18,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()

        address = data.get("address", {})
        return {
            "road_name": address.get("road") or address.get("highway") or data.get("display_name", ""),
            "district": address.get("county") or address.get("state_district") or "",
            "state": address.get("state", "Chhattisgarh"),
            "nearest_landmark": address.get("hamlet") or address.get("village") or address.get("suburb") or "",
            "display_name": data.get("display_name", ""),
        }
