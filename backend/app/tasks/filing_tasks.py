"""Filing tasks — Gemini complaint generation + PG Portal filing."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog

from app.tasks.celery_app import app
from app.database import async_session_factory

logger = structlog.get_logger(__name__)


@app.task(name="app.tasks.filing_tasks.file_complaint", bind=True)
def file_complaint(self, pothole_id: int):
    """Generate Gemini complaint and file on PG Portal."""

    async def _file():
        from sqlalchemy import select, func
        from app.models.pothole import Pothole
        from app.models.complaint import Complaint
        from app.models.source_report import SourceReport
        from app.services.gemini_service import generate_complaint, generate_fallback_complaint
        from app.services.complaint_filer import file_complaint_pg_portal, send_email_fallback
        from app.services.escalation_engine import get_authority_contact

        async with async_session_factory() as db:
            result = await db.execute(select(Pothole).where(Pothole.id == pothole_id))
            pothole = result.scalar_one_or_none()
            if not pothole:
                return {"error": "Pothole not found"}

            # Count existing complaints
            complaint_count_result = await db.execute(
                select(func.count(Complaint.id)).where(Complaint.pothole_id == pothole_id)
            )
            prev_complaint_count = complaint_count_result.scalar() or 0

            # Count sources
            source_result = await db.execute(
                select(SourceReport.source_type).where(SourceReport.pothole_id == pothole_id).distinct()
            )
            sources = [r[0] for r in source_result if r[0]]

            first_complaint_result = await db.execute(
                select(Complaint)
                .where(Complaint.pothole_id == pothole_id)
                .order_by(Complaint.created_at.asc())
                .limit(1)
            )
            first_complaint = first_complaint_result.scalar_one_or_none()
            days_since_filing = 0
            if first_complaint and first_complaint.filed_at:
                days_since_filing = max(
                    0,
                    (datetime.now(timezone.utc) - first_complaint.filed_at).days,
                )

            # Build pothole data dict
            pothole_data = {
                "pothole_id": pothole.id,
                "road_name": pothole.nh_number or "Unknown Road",
                "km_marker": str(pothole.chainage_km or "N/A"),
                "district": pothole.district or "Raipur",
                "latitude": pothole.latitude or 0,
                "longitude": pothole.longitude or 0,
                "nearest_landmark": pothole.address or "N/A",
                "area_sqm": str(pothole.estimated_area_m2 or 0),
                "depth_cm": str(pothole.estimated_depth_cm or 0),
                "severity": pothole.severity,
                "risk_score": str(pothole.risk_score or 0),
                "source_count": len(sources),
                "sources_list": ", ".join(sources) if sources else "drone",
                "detection_date": pothole.detected_at.isoformat() if pothole.detected_at else "N/A",
                "accident_count": 0,
                "traffic_volume_category": "High",
                "rain_imminent": pothole.rain_flag,
                "forecast_rain_48h_mm": 0,
                "prev_complaint_count": prev_complaint_count,
                "days_since_filing": days_since_filing,
            }

            # Determine escalation level
            escalation_level = 0
            last_complaint_result = await db.execute(
                select(Complaint)
                .where(Complaint.pothole_id == pothole_id)
                .order_by(Complaint.created_at.desc())
                .limit(1)
            )
            last_complaint = last_complaint_result.scalar_one_or_none()
            if last_complaint and last_complaint.escalation_level:
                escalation_level = last_complaint.escalation_level

            # Generate complaint text via Gemini
            gemini_result = await generate_complaint(db, pothole_data, escalation_level)

            if gemini_result is None:
                # Fallback template
                gemini_result = generate_fallback_complaint(pothole_data, escalation_level)

            # File on PG Portal
            filing_result = await file_complaint_pg_portal(
                complaint_text=gemini_result.get("body", ""),
                subject=gemini_result.get("subject", "Pothole Complaint"),
                pothole_data=pothole_data,
                image_path=pothole.image_path,
            )

            # Store complaint
            portal_status = filing_result.get("status", "PENDING")
            complaint = Complaint(
                pothole_id=pothole_id,
                complaint_text=gemini_result.get("body", ""),
                portal_ref=filing_result.get("portal_ref"),
                portal_status=portal_status,
                filed_at=datetime.now(timezone.utc) if portal_status == "FILED" else None,
                escalation_level=escalation_level,
                filing_proof_path=filing_result.get("filing_proof_path"),
                filing_method="PG_PORTAL",
            )
            db.add(complaint)

            # Email fallback if PG Portal failed
            if filing_result.get("status") == "PENDING_RETRY":
                contact = await get_authority_contact(db, escalation_level)
                if contact:
                    await send_email_fallback(
                        to_email=contact["email"],
                        subject=gemini_result.get("subject", "Pothole Complaint"),
                        body=gemini_result.get("body", ""),
                        pothole_id=pothole_id,
                    )
                    complaint.filing_method = "EMAIL_FALLBACK"

            await db.commit()
            return {
                "pothole_id": pothole_id,
                "portal_ref": filing_result.get("portal_ref"),
                "status": filing_result.get("status"),
            }

    return asyncio.get_event_loop().run_until_complete(_file())


@app.task(name="app.tasks.filing_tasks.generate_monthly_report", bind=True)
def generate_monthly_report(self):
    """Generate monthly district accountability report via Gemini."""

    async def _generate():
        from app.services.gemini_service import generate_complaint

        async with async_session_factory() as db:
            # Aggregate monthly stats
            # This would query real DB data for the report
            return {"status": "report_generated"}

    return asyncio.get_event_loop().run_until_complete(_generate())
