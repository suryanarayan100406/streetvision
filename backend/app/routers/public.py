"""Public API endpoints — no authentication required."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.functions import ST_AsGeoJSON, ST_DWithin, ST_MakePoint

from app.database import get_db
from app.models.pothole import Pothole
from app.models.complaint import Complaint
from app.schemas.pothole import PotholeOut, PotholeDetail, PotholeListParams

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/potholes", response_model=list[PotholeOut])
async def list_potholes(
    params: PotholeListParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    """List potholes with optional filters."""
    q = select(Pothole)

    if params.severity:
        q = q.where(Pothole.severity == params.severity)
    if params.nh_number:
        q = q.where(Pothole.nh_number == params.nh_number)
    if params.status:
        q = q.where(Pothole.status == params.status)
    if params.min_risk is not None:
        q = q.where(Pothole.risk_score >= params.min_risk)
    if params.bbox:
        parts = [float(x) for x in params.bbox.split(",")]
        if len(parts) == 4:
            from geoalchemy2.functions import ST_MakeEnvelope
            q = q.where(
                Pothole.geom.ST_Within(
                    ST_MakeEnvelope(parts[0], parts[1], parts[2], parts[3], 4326)
                )
            )

    q = q.order_by(Pothole.risk_score.desc())
    q = q.offset(params.offset).limit(params.limit)

    result = await db.execute(q)
    return result.scalars().all()


@router.get("/potholes/{pothole_id}", response_model=PotholeDetail)
async def get_pothole(pothole_id: int, db: AsyncSession = Depends(get_db)):
    """Get detailed pothole information including complaints and sources."""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Pothole)
        .options(
            selectinload(Pothole.complaints),
            selectinload(Pothole.source_reports),
        )
        .where(Pothole.id == pothole_id)
    )
    pothole = result.scalar_one_or_none()
    if not pothole:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Pothole not found")
    return pothole


@router.get("/potholes/nearby")
async def nearby_potholes(
    lat: float = Query(...),
    lon: float = Query(...),
    radius_m: float = Query(500, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Find potholes within radius of a point."""
    point = ST_MakePoint(lon, lat)
    q = (
        select(Pothole)
        .where(ST_DWithin(Pothole.geom, func.ST_SetSRID(point, 4326), radius_m))
        .order_by(Pothole.risk_score.desc())
        .limit(50)
    )
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/stats")
async def public_stats(db: AsyncSession = Depends(get_db)):
    """Aggregate statistics for the public dashboard."""
    total_q = await db.execute(select(func.count(Pothole.id)))
    total = total_q.scalar() or 0

    filed_q = await db.execute(
        select(func.count(Complaint.id)).where(Complaint.portal_status != None)
    )
    filed = filed_q.scalar() or 0

    repaired_q = await db.execute(
        select(func.count(Pothole.id)).where(Pothole.status == "Repaired")
    )
    repaired = repaired_q.scalar() or 0

    critical_q = await db.execute(
        select(func.count(Pothole.id)).where(Pothole.severity == "Critical")
    )
    critical = critical_q.scalar() or 0

    by_nh_q = await db.execute(
        select(Pothole.nh_number, func.count(Pothole.id))
        .group_by(Pothole.nh_number)
    )
    by_nh = {r[0]: r[1] for r in by_nh_q.all()}

    return {
        "total_potholes": total,
        "complaints_filed": filed,
        "repaired": repaired,
        "critical": critical,
        "by_highway": by_nh,
    }


@router.get("/geojson")
async def potholes_geojson(
    nh_number: str | None = None,
    severity: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """GeoJSON FeatureCollection of all potholes for map rendering."""
    q = select(
        Pothole.id,
        Pothole.latitude,
        Pothole.longitude,
        Pothole.severity,
        Pothole.risk_score,
        Pothole.status,
        Pothole.nh_number,
        Pothole.detected_at,
    )
    if nh_number:
        q = q.where(Pothole.nh_number == nh_number)
    if severity:
        q = q.where(Pothole.severity == severity)

    result = await db.execute(q)
    rows = result.all()

    features = []
    for r in rows:
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [r.longitude, r.latitude],
            },
            "properties": {
                "id": r.id,
                "severity": r.severity,
                "risk_score": float(r.risk_score) if r.risk_score else 0,
                "status": r.status,
                "nh_number": r.nh_number,
                "detected_at": r.detected_at.isoformat() if r.detected_at else None,
            },
        })

    return {
        "type": "FeatureCollection",
        "features": features,
    }
