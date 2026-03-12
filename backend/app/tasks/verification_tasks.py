"""Repair verification and re-scan tasks."""

from __future__ import annotations

import asyncio
from datetime import datetime, date, timezone

import structlog
from sqlalchemy import select, or_

from app.tasks.celery_app import app
from app.database import async_session_factory

logger = structlog.get_logger(__name__)


@app.task(name="app.tasks.verification_tasks.verify_all_repairs", bind=True)
def verify_all_repairs(self):
    """Daily task: verify repairs for all unrepaired potholes due for re-scan."""

    async def _verify():
        from app.models.pothole import Pothole
        from datetime import timedelta

        async with async_session_factory() as db:
            cutoff = date.today() - timedelta(days=14)
            result = await db.execute(
                select(Pothole).where(
                    Pothole.last_repair_status != "Repaired",
                    or_(
                        Pothole.last_scan_date <= cutoff,
                        Pothole.last_scan_date.is_(None),
                    ),
                ).limit(100)
            )
            potholes = result.scalars().all()

            queued = 0
            for p in potholes:
                verify_single_pothole.delay(p.id)
                queued += 1

            return {"queued": queued}

    return asyncio.get_event_loop().run_until_complete(_verify())


@app.task(name="app.tasks.verification_tasks.verify_single_pothole", bind=True)
def verify_single_pothole(self, pothole_id: int):
    """Verify repair status for a single pothole."""

    async def _verify():
        from app.models.pothole import Pothole
        from app.models.scan import Scan
        from app.services.repair_verifier import verify_repair

        async with async_session_factory() as db:
            result = await db.execute(select(Pothole).where(Pothole.id == pothole_id))
            pothole = result.scalar_one_or_none()
            if not pothole or not pothole.image_path:
                return {"error": "No pothole or no before image"}

            # Get latest scan image (after)
            # In production: re-acquire from best available source
            after_path = pothole.image_path  # Would be new scan image

            if not after_path:
                return {"error": "No after image available"}

            repair_result = await verify_repair(
                before_path=pothole.image_path,
                after_path=after_path,
            )

            scan = Scan(
                pothole_id=pothole_id,
                scan_date=date.today(),
                before_image_path=pothole.image_path,
                after_image_path=after_path,
                ssim_score=repair_result.get("ssim_score"),
                siamese_score=repair_result.get("siamese_score"),
                repair_status=repair_result["repair_status"],
                scan_source="AUTO_RESCAN",
            )
            db.add(scan)

            pothole.last_scan_date = datetime.now(timezone.utc)
            pothole.last_repair_status = repair_result["repair_status"]

            # If partial repair, file new complaint
            if repair_result["repair_status"] == "Partially_Repaired":
                from app.tasks.filing_tasks import file_complaint
                file_complaint.delay(pothole_id)

            # Reset persistence on full repair
            if repair_result["repair_status"] == "Repaired":
                pothole.critically_overdue = False

            await db.commit()
            return {"pothole_id": pothole_id, "status": repair_result["repair_status"]}

    return asyncio.get_event_loop().run_until_complete(_verify())
