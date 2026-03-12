"""Drone mission management service."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.drone import DroneMission

logger = structlog.get_logger(__name__)


async def submit_to_nodeodm(
    mission_id: int,
    images_zip_path: str,
    options: dict[str, Any] | None = None,
) -> str | None:
    """Submit a drone mission to NodeODM for processing."""
    default_options = {
        "dsm": True,
        "orthophoto-resolution": 3,
        "feature-quality": "ultra",
        "min-num-features": 16000,
        "mesh-octree-depth": 12,
    }
    if options:
        default_options.update(options)

    async with httpx.AsyncClient() as client:
        # Create a new task
        response = await client.post(
            f"{settings.NODEODM_URL}/task/new",
            data={"options": str(default_options)},
            timeout=120.0,
        )
        response.raise_for_status()
        task_data = response.json()
        task_id = task_data.get("uuid")

        await logger.ainfo("nodeodm_task_created", mission_id=mission_id, task_id=task_id)
        return task_id


async def check_nodeodm_status(task_id: str) -> dict[str, Any]:
    """Check status of a NodeODM processing task."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{settings.NODEODM_URL}/task/{task_id}/info", timeout=30.0)
        response.raise_for_status()
        return response.json()


async def download_nodeodm_results(task_id: str, output_dir: str) -> dict[str, str]:
    """Download orthophoto and DSM from completed NodeODM task."""
    results = {}
    async with httpx.AsyncClient() as client:
        for asset in ["orthophoto.tif", "dsm.tif"]:
            response = await client.get(
                f"{settings.NODEODM_URL}/task/{task_id}/download/{asset}",
                timeout=300.0,
            )
            if response.status_code == 200:
                path = f"{output_dir}/{asset}"
                from app.services.minio_client import upload_bytes
                upload_bytes(path, response.content, content_type="image/tiff")
                results[asset.split(".")[0]] = path

    return results


def get_drone_confidence_multiplier(resolution_cm_px: float) -> float:
    """Get confidence multiplier based on drone resolution."""
    if resolution_cm_px < 10:  # < 0.1 m/px
        return 1.85
    elif resolution_cm_px < 50:  # 0.1-0.5 m/px
        return 1.7
    elif resolution_cm_px < 100:  # 0.5-1.0 m/px
        return 1.45
    return 1.3
