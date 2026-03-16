"""Admin ML model management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from celery.result import AsyncResult
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.settings import ModelRegistry
from app.models.pothole import Pothole
from app.models.weather import WeatherCache
from app.tasks.celery_app import app as celery_app

router = APIRouter(prefix="/api/admin/models", tags=["admin-models"])


@router.get("/prediction-insights")
async def prediction_insights(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """Return prediction factors with road-leveling priority using weather and accident signals."""
    capped_limit = min(max(limit, 1), 200)

    weather_row = (
        await db.execute(
            select(WeatherCache)
            .order_by(WeatherCache.checked_at.desc().nullslast(), WeatherCache.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    weather_48h = float(getattr(weather_row, "open_meteo_rain_48h_mm", 0) or 0)
    weather_7d = float(getattr(weather_row, "gfs_rain_7d_mm", 0) or 0)
    warning = (getattr(weather_row, "imd_warning_level", "") or "").strip().lower()
    rain_alert = warning in {"orange", "red"} or weather_48h >= 10 or weather_7d >= 50

    potholes = (
        await db.execute(
            select(Pothole)
            .order_by(Pothole.risk_score.desc().nullslast(), Pothole.id.desc())
            .limit(capped_limit)
        )
    ).scalars().all()

    rows = []
    for pothole in potholes:
        accident_count = 0
        if pothole.latitude is not None and pothole.longitude is not None:
            accident_count = int(
                (
                    await db.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM road_accidents
                            WHERE geom IS NOT NULL
                              AND ST_DWithin(
                                geom,
                                ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                                0.02
                              )
                            """
                        ),
                        {"lon": float(pothole.longitude), "lat": float(pothole.latitude)},
                    )
                ).scalar()
                or 0
            )

        risk_score = float(pothole.risk_score or 0)
        accident_weight = min(accident_count * 4.0, 30.0)
        weather_weight = 20.0 if rain_alert or pothole.rain_flag else 0.0
        traffic_weight = 20.0 if (pothole.aadt or 0) >= 15000 else 12.0 if (pothole.aadt or 0) >= 5000 else 6.0
        geometry_weight = 0.0
        if pothole.near_junction:
            geometry_weight += 5.0
        if pothole.on_curve or pothole.on_blind_spot:
            geometry_weight += 5.0
        if pothole.thermal_stress_flag:
            geometry_weight += 4.0

        road_leveling_priority = round(
            min(100.0, (risk_score * 0.55) + accident_weight + weather_weight + (traffic_weight * 0.3) + geometry_weight),
            2,
        )

        if road_leveling_priority >= 80:
            leveling_action = "Immediate leveling and patch crew dispatch"
        elif road_leveling_priority >= 60:
            leveling_action = "Priority leveling in current cycle"
        elif road_leveling_priority >= 40:
            leveling_action = "Schedule preventive leveling"
        else:
            leveling_action = "Monitor and include in routine maintenance"

        rows.append(
            {
                "id": pothole.id,
                "nh_number": pothole.nh_number,
                "district": pothole.district,
                "severity": pothole.severity,
                "status": pothole.status,
                "risk_score": risk_score,
                "road_leveling_priority": road_leveling_priority,
                "leveling_action": leveling_action,
                "factors": {
                    "accident_count_2km": accident_count,
                    "accident_weight": round(accident_weight, 2),
                    "weather_warning": warning or "none",
                    "weather_48h_mm": weather_48h,
                    "weather_7d_mm": weather_7d,
                    "weather_weight": round(weather_weight, 2),
                    "aadt": int(pothole.aadt or 0),
                    "traffic_weight": round(traffic_weight, 2),
                    "geometry_weight": round(geometry_weight, 2),
                },
            }
        )

    return {
        "count": len(rows),
        "rain_alert": rain_alert,
        "weather": {
            "imd_warning": warning or None,
            "open_meteo_rain_48h_mm": weather_48h,
            "gfs_rain_7d_mm": weather_7d,
        },
        "rows": rows,
    }


@router.get("/")
async def list_models(db: AsyncSession = Depends(get_db)):
    """List all registered ML models."""
    result = await db.execute(
        select(ModelRegistry).order_by(ModelRegistry.model_name)
    )
    return result.scalars().all()


@router.get("/{model_id}")
async def get_model(model_id: int, db: AsyncSession = Depends(get_db)):
    """Get model details and metrics."""
    result = await db.execute(
        select(ModelRegistry).where(ModelRegistry.id == model_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.post("/register", status_code=201)
async def register_model(
    model_name: str,
    version: str,
    model_type: str,
    db: AsyncSession = Depends(get_db),
):
    """Register a new model version."""
    model = ModelRegistry(
        model_name=model_name,
        version=version,
        model_type=model_type,
        is_active=False,
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


@router.post("/bootstrap")
async def bootstrap_models():
    """Trigger pretrained model bootstrap/warmup in background."""
    from app.tasks.model_tasks import bootstrap_pretrained_models

    task = bootstrap_pretrained_models.delay()
    return {
        "queued": True,
        "task_id": task.id,
        "message": "Model bootstrap queued (YOLO + MiDaS + Siamese).",
    }


@router.get("/bootstrap/{task_id}")
async def bootstrap_status(task_id: str):
    """Get background model bootstrap task status/result."""
    result = AsyncResult(task_id, app=celery_app)
    payload = {
        "task_id": task_id,
        "state": result.state,
    }
    if result.successful():
        payload["result"] = result.result
    elif result.failed():
        payload["error"] = str(result.result)
    return payload


@router.post("/{model_id}/activate")
async def activate_model(model_id: int, db: AsyncSession = Depends(get_db)):
    """Activate a model (deactivates other models of the same type)."""
    result = await db.execute(
        select(ModelRegistry).where(ModelRegistry.id == model_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    # Deactivate same-type models
    same_type_q = await db.execute(
        select(ModelRegistry).where(
            ModelRegistry.model_type == model.model_type,
            ModelRegistry.id != model_id,
        )
    )
    for m in same_type_q.scalars().all():
        m.is_active = False

    model.is_active = True
    await db.commit()
    return {"activated": model_id, "model_name": model.model_name}


@router.post("/{model_id}/upload-weights")
async def upload_weights(
    model_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload model weights to MinIO."""
    result = await db.execute(
        select(ModelRegistry).where(ModelRegistry.id == model_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    from app.services.minio_client import upload_bytes

    data = await file.read()
    path = f"models/{model.model_name}/{model.version}/{file.filename}"
    upload_bytes(path, data)

    model.weights_path = path
    await db.commit()
    return {"uploaded": path, "size_mb": round(len(data) / 1024 / 1024, 2)}


@router.put("/{model_id}/metrics")
async def update_metrics(
    model_id: int,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    """Update model evaluation metrics."""
    result = await db.execute(
        select(ModelRegistry).where(ModelRegistry.id == model_id)
    )
    model = result.scalar_one_or_none()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    if "precision" in body:
        model.precision = body["precision"]
    if "recall" in body:
        model.recall = body["recall"]
    if "f1_score" in body:
        model.f1_score = body["f1_score"]
    if "map50" in body:
        model.map50 = body["map50"]

    await db.commit()
    return {"updated": model_id}
