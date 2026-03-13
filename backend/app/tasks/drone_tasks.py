"""Drone processing tasks — OAM ingestion, NodeODM processing, live feed."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog

from app.tasks.celery_app import app
from app.database import async_session_factory

logger = structlog.get_logger(__name__)


@app.task(name="app.tasks.drone_tasks.ingest_openaerialmap", bind=True)
def ingest_openaerialmap(self):
    """Weekly OAM ingestion for highway corridors."""

    async def _ingest():
        from app.services.satellite_manager import query_openaerialmap
        from app.tasks.satellite_tasks import HIGHWAY_CORRIDORS

        total_images = 0
        for highway, bbox in HIGHWAY_CORRIDORS.items():
            try:
                results = await query_openaerialmap(bbox, min_resolution=0.5)
                for img in results:
                    # Queue inference for each qualifying image
                    from app.tasks.cctv_tasks import run_inference_on_tile
                    run_inference_on_tile.delay(
                        img.get("product_id") or img.get("uuid", ""), "OAM_DRONE", highway
                    )
                    total_images += 1
            except Exception as exc:
                await logger.aexception("oam_ingestion_error", highway=highway, error=str(exc))

        return {"source": "OAM", "images_queued": total_images}

    return asyncio.get_event_loop().run_until_complete(_ingest())


@app.task(name="app.tasks.drone_tasks.ingest_openaerialmap_bbox", bind=True)
def ingest_openaerialmap_bbox(
    self,
    bbox: dict,
    label: str = "custom",
    min_resolution: float = 0.8,
    limit: int = 50,
    date_from: str | None = None,
    date_to: str | None = None,
):
    """On-demand OAM ingestion for a custom bbox/date range."""

    async def _ingest():
        from app.services.satellite_manager import query_openaerialmap
        from app.tasks.cctv_tasks import run_inference_on_tile

        results = await query_openaerialmap(
            bbox,
            min_resolution=min_resolution,
            limit=limit,
            acquired_from=date_from,
            acquired_to=date_to,
        )

        queued = 0
        for img in results:
            run_inference_on_tile.delay(
                img.get("product_id") or img.get("uuid", ""),
                "OAM_DRONE",
                label,
            )
            queued += 1

        return {"source": "OAM", "label": label, "images_queued": queued}

    return asyncio.get_event_loop().run_until_complete(_ingest())


@app.task(name="app.tasks.drone_tasks.process_drone_mission", bind=True)
def process_drone_mission(self, mission_id: int, images_path: str):
    """Submit drone mission to NodeODM and poll for results."""

    async def _process():
        from app.services.drone_manager import submit_to_nodeodm, check_nodeodm_status, download_nodeodm_results
        from sqlalchemy import select
        from app.models.drone import DroneMission

        async with async_session_factory() as db:
            result = await db.execute(select(DroneMission).where(DroneMission.id == mission_id))
            mission = result.scalar_one_or_none()
            if not mission:
                return {"error": "Mission not found"}

            mission.processing_status = "PROCESSING"
            mission.submitted_at = datetime.now(timezone.utc)
            await db.commit()

            # Submit to NodeODM
            task_id = await submit_to_nodeodm(mission_id, images_path)
            if not task_id:
                mission.processing_status = "FAILED"
                await db.commit()
                return {"error": "NodeODM submission failed"}

            mission.nodeodm_task_id = task_id
            await db.commit()

            # Poll for completion
            import asyncio as aio
            for _ in range(360):  # Max 6 hours polling every 60s
                await aio.sleep(60)
                status = await check_nodeodm_status(task_id)
                if status.get("status", {}).get("code") == 40:  # COMPLETED
                    break
                if status.get("status", {}).get("code") == 30:  # FAILED
                    mission.processing_status = "FAILED"
                    await db.commit()
                    return {"error": "NodeODM processing failed"}

            # Download results
            output_dir = f"drone/missions/{mission_id}"
            results = await download_nodeodm_results(task_id, output_dir)
            mission.orthophoto_path = results.get("orthophoto")
            mission.dsm_path = results.get("dsm")
            mission.processing_status = "COMPLETED"
            mission.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Queue inference on orthophoto tiles
            from app.tasks.cctv_tasks import run_inference_on_tile
            run_inference_on_tile.delay(str(mission_id), "DRONE", mission.highway or "")

            return {"mission_id": mission_id, "status": "COMPLETED"}

    return asyncio.get_event_loop().run_until_complete(_process())


@app.task(name="app.tasks.drone_tasks.ingest_nrsc_uav", bind=True)
def ingest_nrsc_uav(self):
    """Ingest NRSC/NESAC UAV data for highway corridors."""

    async def _ingest():
        import httpx
        from app.config import settings

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.nrsc.gov.in/data/uav",
                auth=(settings.NRSC_DATA_USERNAME, settings.NRSC_DATA_PASSWORD),
                timeout=60.0,
            )
        return {"source": "NRSC_UAV", "status": "queried"}

    return asyncio.get_event_loop().run_until_complete(_ingest())
