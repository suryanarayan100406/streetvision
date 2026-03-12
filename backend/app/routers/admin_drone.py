"""Admin drone mission management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.drone import DroneMission
from app.schemas.drone import DroneMissionCreate, DroneMissionOut

router = APIRouter(prefix="/api/admin/drones", tags=["admin-drones"])


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
    process_drone_mission.delay(mission.id)

    return mission


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

    mission.processing_status = "PENDING"
    await db.commit()

    from app.tasks.drone_tasks import process_drone_mission
    process_drone_mission.delay(mission.id)

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
