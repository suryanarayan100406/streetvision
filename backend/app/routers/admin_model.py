"""Admin ML model management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.settings import ModelRegistry

router = APIRouter(prefix="/api/admin/models", tags=["admin-models"])


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
    url = await upload_bytes("ml-models", path, data)

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
