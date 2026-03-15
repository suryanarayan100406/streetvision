"""Filing tasks — Gemini complaint generation + PG Portal filing."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import func, select, text

from app.tasks.celery_app import app
from app.database import async_session_factory

logger = structlog.get_logger(__name__)


async def _record_history(task_name: str, task_id: str | None, status: str, result: dict):
    from app.models.task import TaskHistory

    async with async_session_factory() as db:
        row = TaskHistory(
            task_name=task_name,
            task_id=task_id,
            status=status,
            result=result,
            duration_seconds=0.0,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(row)
        await db.commit()


@app.task(name="app.tasks.filing_tasks.file_complaint", bind=True)
def file_complaint(self, pothole_id: int, force: bool = False, escalation_level_override: int | None = None, source_complaint_id: int | None = None):
    """Generate Gemini complaint and file on PG Portal."""

    async def _file():
        from app.config import settings
        from app.models.pothole import Pothole
        from app.models.complaint import Complaint
        from app.models.scan import Scan
        from app.models.source_report import SourceReport
        from app.services.gemini_service import generate_complaint, generate_fallback_complaint
        from app.services.complaint_filer import file_complaint_pg_portal, send_email_fallback
        from app.services.escalation_engine import get_authority_contact
        from app.services.weather_service import fetch_open_meteo

        def infer_road_type(road_name: str | None) -> str:
            if not road_name:
                return "Road"
            normalized = road_name.upper()
            if normalized.startswith("NH"):
                return "National Highway"
            if normalized.startswith("SH"):
                return "State Highway"
            if normalized.startswith("MDR"):
                return "Major District Road"
            return "Road"

        def infer_traffic_category(segment: dict[str, object] | None, aadt: int | None) -> str:
            volume = int(aadt or ((segment or {}).get("aadt") or 0) or 0)
            if volume >= 15000:
                return "High"
            if volume >= 5000:
                return "Medium"
            return "Low"

        async def load_context(pothole: Pothole) -> dict[str, object]:
            schema_result = await db.execute(
                text(
                    """
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'road_accidents'
                          AND column_name = 'geom'
                    )
                    """
                )
            )
            road_accidents_has_geom = bool(schema_result.scalar())

            if road_accidents_has_geom:
                accident_result = await db.execute(
                    text(
                        """
                        SELECT COUNT(*)
                        FROM road_accidents
                        WHERE ST_DWithin(
                            geom,
                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                            0.02
                        )
                        """
                    ),
                    {"lon": float(pothole.longitude), "lat": float(pothole.latitude)},
                )
                accident_count = int(accident_result.scalar() or 0)
            elif pothole.district:
                accident_result = await db.execute(
                    text(
                        """
                        SELECT COALESCE(SUM(total_accidents), 0)
                        FROM road_accidents
                        WHERE lower(district) = lower(:district)
                        """
                    ),
                    {"district": str(pothole.district)},
                )
                accident_count = int(accident_result.scalar() or 0)
            else:
                accident_count = 0

            segment_result = await db.execute(
                text(
                    """
                    SELECT nh_number, chainage_km, aadt, is_curve, is_blind_spot, is_junction, thermal_stress_zone
                    FROM road_segments
                    ORDER BY ST_Distance(
                        geom,
                        ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)
                    )
                    LIMIT 1
                    """
                ),
                {"lon": float(pothole.longitude), "lat": float(pothole.latitude)},
            )
            segment = segment_result.mappings().first()

            weather_summary = "No forecast summary available"
            forecast_rain_48h_mm = 0.0
            try:
                forecast = await fetch_open_meteo(float(pothole.latitude), float(pothole.longitude))
                forecast_rain_48h_mm = float(forecast.get("total_precipitation_48h_mm") or 0.0)
                weather_summary = (
                    f"Forecast precipitation over next 48h: {forecast_rain_48h_mm} mm"
                    if forecast_rain_48h_mm > 0
                    else "No material rainfall forecast in next 48h"
                )
            except Exception as exc:
                await logger.awarn("complaint_weather_context_failed", pothole_id=pothole.id, error=str(exc))

            road_name = pothole.nh_number or ((segment or {}).get("nh_number") or None) or "Unknown Road"
            km_marker = pothole.chainage_km
            if km_marker is None and segment and segment.get("chainage_km") is not None:
                km_marker = float(segment["chainage_km"])

            complaint_rows_result = await db.execute(
                select(
                    Complaint.portal_ref,
                    Complaint.portal_status,
                    Complaint.filed_at,
                    Complaint.escalated_at,
                    Complaint.escalation_level,
                    Complaint.escalation_target,
                )
                .where(Complaint.pothole_id == pothole.id)
                .order_by(Complaint.created_at.asc())
            )
            complaint_rows = complaint_rows_result.all()
            prior_refs = [row.portal_ref for row in complaint_rows if row.portal_ref]
            latest_complaint_row = complaint_rows[-1] if complaint_rows else None
            first_filed_at = next((row.filed_at for row in complaint_rows if row.filed_at is not None), None)
            unresolved_days = 0
            if first_filed_at:
                unresolved_days = max(0, (datetime.now(timezone.utc) - first_filed_at).days)

            latest_scan_result = await db.execute(
                select(
                    Scan.scan_date,
                    Scan.repair_status,
                    Scan.ssim_score,
                    Scan.siamese_score,
                    Scan.scan_source,
                )
                .where(Scan.pothole_id == pothole.id)
                .order_by(Scan.id.desc())
                .limit(1)
            )
            latest_scan = latest_scan_result.first()

            return {
                "road_name": road_name,
                "road_type": infer_road_type(road_name),
                "km_marker": km_marker,
                "accident_count": accident_count,
                "traffic_volume_category": infer_traffic_category(segment, pothole.aadt),
                "aadt": int(pothole.aadt or ((segment or {}).get("aadt") or 0) or 0),
                "forecast_rain_48h_mm": round(forecast_rain_48h_mm, 2),
                "weather_summary": weather_summary,
                "near_junction": bool(pothole.near_junction or ((segment or {}).get("is_junction") if segment else False)),
                "on_curve": bool(pothole.on_curve or ((segment or {}).get("is_curve") if segment else False)),
                "on_blind_spot": bool(pothole.on_blind_spot or ((segment or {}).get("is_blind_spot") if segment else False)),
                "thermal_stress_flag": bool(pothole.thermal_stress_flag or ((segment or {}).get("thermal_stress_zone") if segment else False)),
                "prior_portal_refs": ", ".join(prior_refs[-3:]) if prior_refs else "",
                "last_portal_status": latest_complaint_row.portal_status if latest_complaint_row else None,
                "escalation_target": latest_complaint_row.escalation_target if latest_complaint_row and latest_complaint_row.escalation_target else None,
                "days_since_first_filing": unresolved_days,
                "latest_verification_status": latest_scan.repair_status if latest_scan else None,
                "latest_verification_date": latest_scan.scan_date.isoformat() if latest_scan and latest_scan.scan_date else None,
                "latest_ssim_score": float(latest_scan.ssim_score) if latest_scan and latest_scan.ssim_score is not None else None,
                "latest_siamese_score": float(latest_scan.siamese_score) if latest_scan and latest_scan.siamese_score is not None else None,
                "latest_scan_source": latest_scan.scan_source if latest_scan else None,
            }

        async with async_session_factory() as db:
            result = await db.execute(select(Pothole).where(Pothole.id == pothole_id))
            pothole = result.scalar_one_or_none()
            if not pothole:
                return {"error": "Pothole not found"}

            if not force and float(pothole.risk_score or 0) < float(settings.AUTO_FILE_MIN_RISK_SCORE):
                await logger.ainfo(
                    "skip_low_risk_auto_file",
                    pothole_id=pothole_id,
                    risk_score=float(pothole.risk_score or 0),
                    min_risk=float(settings.AUTO_FILE_MIN_RISK_SCORE),
                )
                return {
                    "pothole_id": pothole_id,
                    "status": "SKIPPED_LOW_RISK",
                    "risk_score": float(pothole.risk_score or 0),
                    "min_risk": float(settings.AUTO_FILE_MIN_RISK_SCORE),
                }

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

            context = await load_context(pothole)

            # Build pothole data dict
            pothole_data = {
                "pothole_id": pothole.id,
                "road_name": context["road_name"],
                "road_type": context["road_type"],
                "km_marker": str(context["km_marker"] or "N/A"),
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
                "accident_count": context["accident_count"],
                "traffic_volume_category": context["traffic_volume_category"],
                "aadt": context["aadt"],
                "rain_imminent": pothole.rain_flag,
                "forecast_rain_48h_mm": context["forecast_rain_48h_mm"],
                "weather_summary": context["weather_summary"],
                "near_junction": context["near_junction"],
                "on_curve": context["on_curve"],
                "on_blind_spot": context["on_blind_spot"],
                "thermal_stress_flag": context["thermal_stress_flag"],
                "prev_complaint_count": prev_complaint_count,
                "days_since_filing": max(days_since_filing, int(context["days_since_first_filing"] or 0)),
                "prior_portal_refs": context["prior_portal_refs"] or "None",
                "latest_verification_status": context["latest_verification_status"] or pothole.last_repair_status or "No verification run yet",
                "latest_verification_date": context["latest_verification_date"] or "N/A",
                "latest_ssim_score": context["latest_ssim_score"] if context["latest_ssim_score"] is not None else "N/A",
                "latest_siamese_score": context["latest_siamese_score"] if context["latest_siamese_score"] is not None else "N/A",
                "latest_scan_source": context["latest_scan_source"] or "N/A",
                "escalation_target": context["escalation_target"] or "",
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
            if escalation_level_override is not None:
                escalation_level = int(escalation_level_override)
            pothole_data["escalation_target"] = context["escalation_target"] or pothole_data["escalation_target"] or ""

            # Generate complaint text via Gemini
            gemini_result = await generate_complaint(db, pothole_data, escalation_level)

            if gemini_result is None:
                # Fallback template
                gemini_result = generate_fallback_complaint(pothole_data, escalation_level)

            # File on PG Portal
            try:
                filing_result = await file_complaint_pg_portal(
                    complaint_text=gemini_result.get("body", ""),
                    subject=gemini_result.get("subject", "Pothole Complaint"),
                    pothole_data=pothole_data,
                    image_path=pothole.image_path,
                )
            except Exception as exc:
                await logger.awarning(
                    "pg_portal_filing_failed_fallback_pending_retry",
                    pothole_id=pothole_id,
                    error=str(exc),
                )
                filing_result = {
                    "status": "PENDING_RETRY",
                    "portal_ref": None,
                    "filing_proof_path": None,
                    "error": str(exc),
                }

            # Store complaint
            portal_status = filing_result.get("status", "PENDING")
            filed_at_value = datetime.now(timezone.utc) if portal_status == "FILED" else None
            complaint = Complaint(
                pothole_id=pothole_id,
                complaint_text=gemini_result.get("body", ""),
                portal_ref=filing_result.get("portal_ref"),
                portal_status=portal_status,
                filed_at=filed_at_value,
                escalation_level=escalation_level,
                escalated_at=datetime.now(timezone.utc) if escalation_level > 0 else None,
                escalation_target=pothole_data.get("escalation_target") or None,
                filing_proof_path=filing_result.get("filing_proof_path"),
                filing_method="PG_PORTAL",
            )
            db.add(complaint)

            # Email fallback if PG Portal failed
            if filing_result.get("status") == "PENDING_RETRY":
                contact = await get_authority_contact(db, escalation_level)
                if contact:
                    email_sent = await send_email_fallback(
                        to_email=contact["email"],
                        subject=gemini_result.get("subject", "Pothole Complaint"),
                        body=gemini_result.get("body", ""),
                        pothole_id=pothole_id,
                    )
                    if email_sent:
                        complaint.filing_method = "EMAIL_FALLBACK"
                        complaint.portal_status = "FILED_EMAIL_FALLBACK"
                        complaint.filed_at = datetime.now(timezone.utc)
                        if not complaint.portal_ref:
                            complaint.portal_ref = f"EMAIL-{pothole_id}-{int(datetime.now(timezone.utc).timestamp())}"

            await db.commit()
            await _record_history(
                "file_complaint",
                getattr(self.request, "id", None),
                "SUCCESS",
                {
                    "pothole_id": pothole_id,
                    "portal_ref": filing_result.get("portal_ref"),
                    "status": filing_result.get("status"),
                    "forced": bool(force),
                    "escalation_level": escalation_level,
                    "source_complaint_id": source_complaint_id,
                },
            )
            return {
                "pothole_id": pothole_id,
                "portal_ref": filing_result.get("portal_ref"),
                "status": filing_result.get("status"),
                "forced": bool(force),
                "escalation_level": escalation_level,
            }

    return asyncio.get_event_loop().run_until_complete(_file())


@app.task(name="app.tasks.filing_tasks.generate_monthly_report", bind=True)
def generate_monthly_report(self):
    """Generate monthly district accountability report from live DB metrics."""

    async def _generate():
        from sqlalchemy import case, and_

        from app.models.complaint import Complaint
        from app.models.pothole import Pothole
        from app.models.task import TaskHistory

        now = datetime.now(timezone.utc)
        month_start = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        if now.month == 12:
            month_end = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            month_end = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)

        def _is_open_status():
            return and_(
                Complaint.portal_status.is_not(None),
                Complaint.portal_status.notin_(["Resolved", "Closed"]),
            )

        async with async_session_factory() as db:
            detected_q = await db.execute(
                select(func.count(Pothole.id)).where(
                    Pothole.detected_at >= month_start,
                    Pothole.detected_at < month_end,
                )
            )
            total_detected = int(detected_q.scalar() or 0)

            filed_q = await db.execute(
                select(func.count(Complaint.id)).where(
                    Complaint.filed_at.is_not(None),
                    Complaint.filed_at >= month_start,
                    Complaint.filed_at < month_end,
                )
            )
            total_filed = int(filed_q.scalar() or 0)

            resolved_q = await db.execute(
                select(func.count(Complaint.id)).where(
                    Complaint.resolved_at.is_not(None),
                    Complaint.resolved_at >= month_start,
                    Complaint.resolved_at < month_end,
                )
            )
            total_resolved = int(resolved_q.scalar() or 0)

            escalated_q = await db.execute(
                select(func.count(Complaint.id)).where(
                    Complaint.escalated_at.is_not(None),
                    Complaint.escalated_at >= month_start,
                    Complaint.escalated_at < month_end,
                )
            )
            total_escalated = int(escalated_q.scalar() or 0)

            open_q = await db.execute(
                select(func.count(Complaint.id)).where(_is_open_status())
            )
            open_complaints = int(open_q.scalar() or 0)

            overdue_anchor = now - timedelta(days=14)
            overdue_q = await db.execute(
                select(func.count(Complaint.id)).where(
                    _is_open_status(),
                    func.coalesce(Complaint.escalated_at, Complaint.filed_at, Complaint.created_at) <= overdue_anchor,
                )
            )
            overdue_open = int(overdue_q.scalar() or 0)

            district_q = await db.execute(
                select(
                    Pothole.district.label("district"),
                    func.count(Complaint.id).label("open_count"),
                    func.sum(
                        case(
                            (
                                func.coalesce(Complaint.escalated_at, Complaint.filed_at, Complaint.created_at)
                                <= overdue_anchor,
                                1,
                            ),
                            else_=0,
                        )
                    ).label("overdue_count"),
                )
                .join(Pothole, Pothole.id == Complaint.pothole_id)
                .where(_is_open_status())
                .group_by(Pothole.district)
                .order_by(func.count(Complaint.id).desc())
                .limit(10)
            )
            district_breakdown = [
                {
                    "district": row.district or "Unknown",
                    "open_complaints": int(row.open_count or 0),
                    "overdue_open": int(row.overdue_count or 0),
                }
                for row in district_q.all()
            ]

            resolution_rate = round((total_resolved / total_filed) * 100, 2) if total_filed > 0 else 0.0
            escalation_rate = round((total_escalated / total_filed) * 100, 2) if total_filed > 0 else 0.0

            report_lines = [
                f"Monthly Accountability Report ({month_start.strftime('%B %Y')})",
                f"Detected this month: {total_detected}",
                f"Filed this month: {total_filed}",
                f"Resolved this month: {total_resolved}",
                f"Escalated this month: {total_escalated}",
                f"Current open complaints: {open_complaints}",
                f"Current open overdue (>14d): {overdue_open}",
                f"Resolution rate: {resolution_rate}%",
                f"Escalation rate: {escalation_rate}%",
            ]

            for item in district_breakdown:
                report_lines.append(
                    f"District {item['district']}: open={item['open_complaints']}, overdue={item['overdue_open']}"
                )

            payload = {
                "generated_at": now.isoformat(),
                "month_start": month_start.isoformat(),
                "month_end": month_end.isoformat(),
                "summary": {
                    "detected": total_detected,
                    "filed": total_filed,
                    "resolved": total_resolved,
                    "escalated": total_escalated,
                    "open_complaints": open_complaints,
                    "overdue_open": overdue_open,
                    "resolution_rate_pct": resolution_rate,
                    "escalation_rate_pct": escalation_rate,
                },
                "district_breakdown": district_breakdown,
                "report_text": "\n".join(report_lines),
            }

            db.add(
                TaskHistory(
                    task_name="generate_monthly_report",
                    task_id=getattr(self.request, "id", None),
                    status="SUCCESS",
                    result=payload,
                    duration_seconds=0.0,
                    completed_at=now,
                )
            )
            await db.commit()
            return payload

    return asyncio.get_event_loop().run_until_complete(_generate())
