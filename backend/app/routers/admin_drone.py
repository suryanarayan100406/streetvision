"""Admin drone mission management endpoints."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.drone import DroneMission
from app.schemas.drone import DroneMissionCreate, DroneMissionOut

router = APIRouter(prefix="/api/admin/drones", tags=["admin-drones"])

ALLOWED_DRONE_UPLOAD_EXTENSIONS = {
    ".zip",
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".mp4",
    ".mov",
    ".mkv",
}


def _is_image_extension(ext: str) -> bool:
    return ext in {".jpg", ".jpeg", ".png", ".tif", ".tiff"}


def _is_video_extension(ext: str) -> bool:
    return ext in {".mp4", ".mov", ".mkv"}


@router.get("/missions", response_model=list[DroneMissionOut])
async def list_missions(
    limit: int = 50,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List drone missions."""
    q = select(DroneMission).order_by(DroneMission.created_at.desc()).limit(limit)
    if status:
        q = q.where(DroneMission.processing_status == status)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/missions", response_model=DroneMissionOut, status_code=201)
async def create_mission(
    body: DroneMissionCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new drone processing mission."""
    mission = DroneMission(
        mission_name=body.mission_name,
        operator=body.operator,
        flight_date=body.flight_date,
        area_bbox=body.area_bbox,
        image_count=body.image_count,
        gsd_cm=body.gsd_cm,
        processing_status="PENDING",
    )
    db.add(mission)
    await db.commit()
    await db.refresh(mission)

    # Trigger NodeODM processing
    from app.tasks.drone_tasks import process_drone_mission
    process_drone_mission.delay(mission.id, None)

    return mission


@router.post("/missions/upload", status_code=201)
async def upload_mission_footage(
    file: UploadFile = File(...),
    mission_name: str | None = Form(None),
    operator: str | None = Form(None),
    flight_date: str | None = Form(None),
    area_bbox: str | None = Form(None),
    gsd_cm: float | None = Form(None),
    image_count: int | None = Form(None),
    auto_process: bool = Form(True),
    db: AsyncSession = Depends(get_db),
):
    """Upload drone footage (image/video/zip) and create mission record."""
    filename = file.filename or "upload.bin"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_DRONE_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Allowed: zip, jpg, jpeg, png, tif, tiff, mp4, mov, mkv",
        )

    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(payload) > 1024 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 1GB)")

    bbox_obj = None
    if area_bbox:
        try:
            bbox_obj = json.loads(area_bbox)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="area_bbox must be valid JSON") from exc

    parsed_flight_date = None
    if flight_date:
        from datetime import date

        try:
            parsed_flight_date = date.fromisoformat(flight_date)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="flight_date must be YYYY-MM-DD") from exc

    safe_name = os.path.basename(filename).replace(" ", "_")
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    object_path = f"drone/uploads/{ts}_{safe_name}"

    from app.services.minio_client import upload_bytes

    upload_bytes(
        object_path,
        payload,
        content_type=file.content_type or "application/octet-stream",
    )

    mission = DroneMission(
        mission_name=mission_name or f"upload-{ts}",
        operator=operator,
        flight_date=parsed_flight_date,
        area_bbox=bbox_obj,
        image_count=image_count,
        gsd_cm=gsd_cm,
        processing_status="UPLOADED",
        orthophoto_path=object_path,
    )
    db.add(mission)
    await db.commit()
    await db.refresh(mission)

    queued_for_inference = False
    if auto_process and (_is_image_extension(ext) or _is_video_extension(ext)):
        from app.tasks.drone_tasks import process_uploaded_drone_asset

        process_uploaded_drone_asset.delay(mission.id, object_path)
        queued_for_inference = True

    return {
        "mission_id": mission.id,
        "mission_name": mission.mission_name,
        "uploaded_file": object_path,
        "file_type": ext,
        "processing_status": mission.processing_status,
        "queued_for_inference": queued_for_inference,
        "message": (
            "Uploaded successfully and queued for inference"
            if queued_for_inference
            else "Uploaded successfully. Manual/NodeODM processing can be triggered later"
        ),
    }


@router.get("/missions/{mission_id}", response_model=DroneMissionOut)
async def get_mission(mission_id: int, db: AsyncSession = Depends(get_db)):
    """Get mission details."""
    result = await db.execute(
        select(DroneMission).where(DroneMission.id == mission_id)
    )
    mission = result.scalar_one_or_none()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")
    return mission


@router.post("/missions/{mission_id}/reprocess")
async def reprocess_mission(mission_id: int, db: AsyncSession = Depends(get_db)):
    """Re-trigger NodeODM processing for a mission."""
    result = await db.execute(
        select(DroneMission).where(DroneMission.id == mission_id)
    )
    mission = result.scalar_one_or_none()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    previous_status = mission.processing_status
    uploaded_path = mission.orthophoto_path or mission.dsm_path
    upload_ext = os.path.splitext(uploaded_path or "")[1].lower()

    if previous_status == "UPLOADED" and not uploaded_path:
        raise HTTPException(
            status_code=400,
            detail="This uploaded mission was created before upload-path tracking. Please re-upload the video and reprocess.",
        )

    mission.processing_status = "PENDING"
    mission.completed_at = None
    await db.commit()

    if uploaded_path and upload_ext in ALLOWED_DRONE_UPLOAD_EXTENSIONS:
        from app.tasks.drone_tasks import process_uploaded_drone_asset

        process_uploaded_drone_asset.delay(mission.id, uploaded_path)
    else:
        from app.tasks.drone_tasks import process_drone_mission

        process_drone_mission.delay(mission.id, mission.orthophoto_path)

    return {"status": "reprocessing", "mission_id": mission_id}


@router.delete("/missions/{mission_id}")
async def delete_mission(mission_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a drone mission."""
    result = await db.execute(
        select(DroneMission).where(DroneMission.id == mission_id)
    )
    mission = result.scalar_one_or_none()
    if not mission:
        raise HTTPException(status_code=404, detail="Mission not found")

    await db.delete(mission)
    await db.commit()
    return {"deleted": mission_id}
