"""Helpers for resolving active model weights from ModelRegistry with safe fallback."""

from __future__ import annotations

from pathlib import Path

import structlog
from sqlalchemy import select

from app.database import async_session_factory
from app.models.settings import ModelRegistry

logger = structlog.get_logger(__name__)


async def get_active_model_weights(
    model_type: str,
    fallback: str,
    virtual_prefixes: tuple[str, ...] = (),
) -> str:
    """Resolve active model weights path for a model type.

    Returns registry path if active and usable; otherwise returns provided fallback.
    """
    async with async_session_factory() as db:
        result = await db.execute(
            select(ModelRegistry)
            .where(
                ModelRegistry.model_type == model_type,
                ModelRegistry.is_active.is_(True),
            )
            .order_by(ModelRegistry.id.desc())
            .limit(1)
        )
        active = result.scalar_one_or_none()

    if active is None or not active.weights_path:
        return fallback

    weights_path = str(active.weights_path)
    if virtual_prefixes and weights_path.startswith(virtual_prefixes):
        return weights_path

    if Path(weights_path).exists():
        return weights_path

    logger.warning(
        "active_model_weights_unavailable_fallback",
        model_type=model_type,
        weights_path=weights_path,
        fallback=fallback,
    )
    return fallback
