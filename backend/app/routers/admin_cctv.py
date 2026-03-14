"""Admin CCTV camera management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.cctv import CCTVNode
from app.schemas.cctv import CCTVNodeCreate, CCTVNodeOut, CCTVNodeUpdate, CCTVTestResult

router = APIRouter(prefix="/api/admin/cctv", tags=["admin-cctv"])


@router.get("/nodes", response_model=list[CCTVNodeOut])
async def list_nodes(
    active_only: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """List all CCTV camera nodes."""
    q = select(CCTVNode).order_by(CCTVNode.name)
    if active_only:
        q = q.where(CCTVNode.is_active.is_(True))
    result = await db.execute(q)
    return result.scalars().all()


@router.post("/nodes", response_model=CCTVNodeOut, status_code=201)
async def create_node(
    body: CCTVNodeCreate,
    db: AsyncSession = Depends(get_db),
):
    """Register a new CCTV camera node."""
    node = CCTVNode(
        name=body.name,
        rtsp_url=body.rtsp_url,
        latitude=body.latitude,
        longitude=body.longitude,
        nh_number=body.nh_number,
        chainage_km=body.chainage_km,
        perspective_matrix=body.perspective_matrix,
        is_active=True,
    )
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return node


@router.patch("/nodes/{node_id}", response_model=CCTVNodeOut)
async def update_node(
    node_id: int,
    body: CCTVNodeUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update CCTV node configuration."""
    result = await db.execute(select(CCTVNode).where(CCTVNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(node, field, value)

    await db.commit()
    await db.refresh(node)
    return node


@router.post("/nodes/{node_id}/test", response_model=CCTVTestResult)
async def test_node(node_id: int, db: AsyncSession = Depends(get_db)):
    """Test RTSP connection to a CCTV node."""
    result = await db.execute(select(CCTVNode).where(CCTVNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    from app.services.cctv_manager import test_rtsp_connection
    test_result = test_rtsp_connection(node.rtsp_url)
    return test_result


@router.post("/nodes/{node_id}/calibrate")
async def calibrate_homography(
    node_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Set homography calibration points for perspective correction."""
    result = await db.execute(select(CCTVNode).where(CCTVNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    from app.services.cctv_manager import compute_homography
    matrix = compute_homography(
        body.get("src_points", []),
        body.get("dst_points", []),
    )

    node.perspective_matrix = matrix.tolist() if matrix is not None else None
    await db.commit()

    return {"node_id": node_id, "calibrated": matrix is not None}


@router.delete("/nodes/{node_id}")
async def delete_node(node_id: int, db: AsyncSession = Depends(get_db)):
    """Deactivate a CCTV node."""
    result = await db.execute(select(CCTVNode).where(CCTVNode.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    node.is_active = False
    await db.commit()
    return {"deactivated": node_id}
