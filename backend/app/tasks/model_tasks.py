"""ML model bootstrap and warmup tasks."""

from __future__ import annotations

import hashlib
from pathlib import Path

import structlog
from sqlalchemy import select

from app.config import settings
from app.database import async_session_factory
from app.models.settings import ModelRegistry
from app.tasks.celery_app import app

logger = structlog.get_logger(__name__)


def _file_sha256_prefix(path: Path, prefix_len: int = 12) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:prefix_len]


async def _upsert_model_registry(
    *,
    model_name: str,
    version: str,
    model_type: str,
    weights_path: str,
    is_active: bool = True,
) -> None:
    async with async_session_factory() as db:
        existing_q = await db.execute(
            select(ModelRegistry).where(
                ModelRegistry.model_name == model_name,
                ModelRegistry.version == version,
                ModelRegistry.model_type == model_type,
            )
        )
        row = existing_q.scalar_one_or_none()

        if is_active:
            deactivate_q = await db.execute(
                select(ModelRegistry).where(ModelRegistry.model_type == model_type)
            )
            for model in deactivate_q.scalars().all():
                model.is_active = False

        if row is None:
            row = ModelRegistry(
                model_name=model_name,
                version=version,
                model_type=model_type,
                is_active=is_active,
                weights_path=weights_path,
            )
            db.add(row)
        else:
            row.weights_path = weights_path
            row.is_active = is_active

        await db.commit()


async def _bootstrap_models_async() -> dict:
    # 1) YOLO detector registration
    yolo_status = "registered"
    yolo_weights = settings.YOLO_MODEL_PATH
    yolo_version = "pretrained-default"
    yolo_path = Path(yolo_weights)
    if yolo_path.exists():
        yolo_version = f"trained-local-{_file_sha256_prefix(yolo_path)}"
    else:
        yolo_weights = "ultralytics:yolov8n-seg.pt"
        yolo_status = "registered_pretrained_fallback"

    # 2) MiDaS depth registration
    midas_status = "registered_pretrained_torch_hub"
    midas_weights = "torch.hub:intel-isl/MiDaS/DPT_Large"
    configured_midas = Path(settings.MIDAS_MODEL_PATH)
    if configured_midas.exists():
        midas_weights = str(configured_midas)
        midas_status = "registered_custom_checkpoint"

    # 3) Siamese verifier registration
    siamese_status = "registered"
    configured_siamese = Path(settings.SIAMESE_MODEL_PATH)
    siamese_path = str(configured_siamese)
    if configured_siamese.exists():
        siamese_status = "registered_custom_checkpoint"
    else:
        siamese_path = "torchvision:resnet18-imagenet-fallback"
        siamese_status = "registered_pretrained_fallback"

    # Register / update active models (even if one fails, register status path)
    await _upsert_model_registry(
        model_name="yolo-pothole-detector",
        version=yolo_version,
        model_type="DETECTION",
        weights_path=yolo_weights,
        is_active=True,
    )
    await _upsert_model_registry(
        model_name="midas-depth-estimator",
        version="custom-finetuned" if midas_status == "registered_custom_checkpoint" else "pretrained-default",
        model_type="DEPTH",
        weights_path=midas_weights,
        is_active=True,
    )
    await _upsert_model_registry(
        model_name="siamese-repair-verifier",
        version="custom-finetuned" if siamese_status == "registered_custom_checkpoint" else "pretrained-default",
        model_type="VERIFICATION",
        weights_path=siamese_path,
        is_active=True,
    )

    return {
        "status": "completed",
        "models": {
            "yolo": {"status": yolo_status, "weights": yolo_weights},
            "midas": {"status": midas_status, "weights": midas_weights},
            "siamese": {"status": siamese_status, "weights": siamese_path},
        },
    }


@app.task(name="app.tasks.model_tasks.bootstrap_pretrained_models", bind=True)
def bootstrap_pretrained_models(self):
    """Register active pretrained/custom model defaults for pipeline use."""
    import asyncio

    return asyncio.get_event_loop().run_until_complete(_bootstrap_models_async())
