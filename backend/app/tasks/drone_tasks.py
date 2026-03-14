"""Drone processing tasks — OAM ingestion, NodeODM processing, live feed."""

from __future__ import annotations

import asyncio
import os
import tempfile
from datetime import datetime, timezone

import structlog

from app.tasks.celery_app import app
from app.database import async_session_factory

logger = structlog.get_logger(__name__)


@app.task(name="app.tasks.drone_tasks.process_uploaded_drone_asset", bind=True)
def process_uploaded_drone_asset(self, mission_id: int, object_path: str):
    """Process uploaded drone image/video assets by queueing inference."""

    async def _process_uploaded():
        import cv2
        from sqlalchemy import select

        from app.models.drone import DroneMission
        from app.services.minio_client import download_bytes, upload_bytes
        from app.tasks.cctv_tasks import run_inference_on_tile

        ext = os.path.splitext(object_path or "")[1].lower()
        image_exts = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
        video_exts = {".mp4", ".mov", ".mkv"}

        async with async_session_factory() as db:
            result = await db.execute(select(DroneMission).where(DroneMission.id == mission_id))
            mission = result.scalar_one_or_none()
            if mission is None:
                return {"error": "Mission not found"}

            mission.processing_status = "PROCESSING"
            mission.completed_at = None
            await db.commit()

            if ext in image_exts:
                run_inference_on_tile.delay(object_path, "DRONE", mission.mission_name or "DRONE_UPLOAD")
                mission.processing_status = "COMPLETED"
                mission.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return {"mission_id": mission_id, "status": "COMPLETED", "frames_queued": 1}

            if ext not in video_exts:
                mission.processing_status = "FAILED"
                mission.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return {"error": f"Unsupported uploaded extension: {ext}"}

            raw = download_bytes(object_path)
            if not raw:
                mission.processing_status = "FAILED"
                mission.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return {"error": "Uploaded video not found in object storage"}

            frames_queued = 0
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_video:
                temp_video.write(raw)
                temp_video_path = temp_video.name

            try:
                cap = cv2.VideoCapture(temp_video_path)
                if not cap.isOpened():
                    mission.processing_status = "FAILED"
                    mission.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    return {"error": "Could not decode uploaded video"}

                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
                fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
                if fps <= 0:
                    fps = 25.0

                sample_count = 6
                frame_step = max(1, frame_count // sample_count) if frame_count > 0 else int(fps)

                for idx in range(sample_count):
                    target_frame = idx * frame_step
                    cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        continue

                    ok_enc, encoded = cv2.imencode(".jpg", frame)
                    if not ok_enc:
                        continue

                    frame_path = f"drone/frames/{mission_id}/frame_{idx:03d}.jpg"
                    upload_bytes(frame_path, encoded.tobytes(), content_type="image/jpeg")
                    run_inference_on_tile.delay(
                        frame_path,
                        "DRONE",
                        mission.mission_name or "DRONE_UPLOAD_VIDEO",
                    )
                    frames_queued += 1

                cap.release()
            finally:
                try:
                    os.remove(temp_video_path)
                except OSError:
                    pass

            if frames_queued == 0:
                mission.processing_status = "FAILED"
                mission.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return {"error": "No decodable frames found in video"}

            mission.processing_status = "COMPLETED"
            mission.completed_at = datetime.now(timezone.utc)
            await db.commit()
            return {"mission_id": mission_id, "status": "COMPLETED", "frames_queued": frames_queued}

    try:
        return asyncio.get_event_loop().run_until_complete(_process_uploaded())
    except Exception as exc:
        async def _mark_failed():
            from sqlalchemy import select
            from app.models.drone import DroneMission

            async with async_session_factory() as db:
                result = await db.execute(select(DroneMission).where(DroneMission.id == mission_id))
                mission = result.scalar_one_or_none()
                if mission is not None:
                    mission.processing_status = "FAILED"
                    mission.completed_at = datetime.now(timezone.utc)
                    await db.commit()

        asyncio.get_event_loop().run_until_complete(_mark_failed())
        raise exc


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
def process_drone_mission(self, mission_id: int, images_path: str | None = None):
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
            await db.commit()

            # Submit to NodeODM
            task_id = await submit_to_nodeodm(mission_id, images_path or "")
            if not task_id:
                mission.processing_status = "FAILED"
                mission.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return {"error": "NodeODM submission failed"}

            mission.odm_task_id = task_id
            await db.commit()

            # Poll for completion
            import asyncio as aio
            completed = False
            for _ in range(360):  # Max 6 hours polling every 60s
                await aio.sleep(60)
                status = await check_nodeodm_status(task_id)
                if status.get("status", {}).get("code") == 40:  # COMPLETED
                    completed = True
                    break
                if status.get("status", {}).get("code") == 30:  # FAILED
                    mission.processing_status = "FAILED"
                    mission.completed_at = datetime.now(timezone.utc)
                    await db.commit()
                    return {"error": "NodeODM processing failed"}

            if not completed:
                mission.processing_status = "FAILED"
                mission.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return {"error": "NodeODM processing timeout"}

            # Download results
            output_dir = f"drone/missions/{mission_id}"
            results = await download_nodeodm_results(task_id, output_dir)
            mission.orthophoto_path = results.get("orthophoto")
            mission.dsm_path = results.get("dsm")
            mission.processing_status = "COMPLETED"
            mission.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Queue inference on orthophoto tiles
            if mission.orthophoto_path:
                from app.tasks.cctv_tasks import run_inference_on_tile

                run_inference_on_tile.delay(
                    mission.orthophoto_path,
                    "DRONE",
                    mission.mission_name or "DRONE_MISSION",
                )

            return {"mission_id": mission_id, "status": "COMPLETED"}

    try:
        return asyncio.get_event_loop().run_until_complete(_process())
    except Exception as exc:
        async def _mark_failed():
            from sqlalchemy import select
            from app.models.drone import DroneMission

            async with async_session_factory() as db:
                result = await db.execute(select(DroneMission).where(DroneMission.id == mission_id))
                mission = result.scalar_one_or_none()
                if mission is not None:
                    mission.processing_status = "FAILED"
                    mission.completed_at = datetime.now(timezone.utc)
                    await db.commit()

        asyncio.get_event_loop().run_until_complete(_mark_failed())
        raise exc


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
