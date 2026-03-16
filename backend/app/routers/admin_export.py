"""Admin data export router (PDF)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fpdf import FPDF
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.complaint import Complaint
from app.models.pothole import Pothole
from app.models.scan import Scan
from app.models.source_report import SourceReport

router = APIRouter(prefix="/api/admin/export", tags=["admin-export"])


def _to_text(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, (datetime, date)):
        if isinstance(value, datetime) and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(float(value))
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _fit_text(value: object, limit: int = 110) -> str:
    text = _to_text(value)
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _new_pdf() -> FPDF:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, "APIS Data Export", ln=1)
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 6, f"Generated at: {datetime.now(timezone.utc).isoformat()}", ln=1)
    pdf.ln(2)
    return pdf


def _add_section(pdf: FPDF, title: str, rows: list[dict[str, object]]) -> None:
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, title, ln=1)
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 6, f"Rows: {len(rows)}", ln=1)

    if not rows:
        pdf.set_font("Helvetica", "I", 9)
        pdf.cell(0, 6, "No data found.", ln=1)
        pdf.ln(2)
        return

    # Print each row as key-value pairs for readability with variable schemas.
    for idx, row in enumerate(rows, start=1):
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, f"#{idx}", ln=1)
        pdf.set_font("Helvetica", size=8)
        for key, val in row.items():
            pdf.multi_cell(0, 4.5, f"{key}: {_fit_text(val)}")
        pdf.ln(1)

    pdf.ln(2)


async def _fetch_potholes(db: AsyncSession, limit: int) -> list[dict[str, object]]:
    rows = (await db.execute(select(Pothole).order_by(Pothole.id.desc()).limit(limit))).scalars().all()
    return [
        {
            "id": r.id,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "severity": r.severity,
            "confidence_score": r.confidence_score,
            "risk_score": r.risk_score,
            "status": r.status,
            "nh_number": r.nh_number,
            "district": r.district,
            "address": r.address,
            "estimated_area_m2": r.estimated_area_m2,
            "estimated_depth_cm": r.estimated_depth_cm,
            "estimated_diameter_m": r.estimated_diameter_m,
            "rain_flag": r.rain_flag,
            "thermal_stress_flag": r.thermal_stress_flag,
            "moisture_flag": r.moisture_flag,
            "near_junction": r.near_junction,
            "on_curve": r.on_curve,
            "on_blind_spot": r.on_blind_spot,
            "aadt": r.aadt,
            "last_repair_status": r.last_repair_status,
            "detected_at": r.detected_at,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]


async def _fetch_complaints(db: AsyncSession, limit: int) -> list[dict[str, object]]:
    rows = (await db.execute(select(Complaint).order_by(Complaint.id.desc()).limit(limit))).scalars().all()
    return [
        {
            "id": r.id,
            "pothole_id": r.pothole_id,
            "portal_ref": r.portal_ref,
            "portal_status": r.portal_status,
            "escalation_level": r.escalation_level,
            "escalation_target": r.escalation_target,
            "filing_method": r.filing_method,
            "filed_at": r.filed_at,
            "resolved_at": r.resolved_at,
            "escalated_at": r.escalated_at,
            "created_at": r.created_at,
            "complaint_text": r.complaint_text,
        }
        for r in rows
    ]


async def _fetch_scans(db: AsyncSession, limit: int) -> list[dict[str, object]]:
    rows = (await db.execute(select(Scan).order_by(Scan.id.desc()).limit(limit))).scalars().all()
    return [
        {
            "id": r.id,
            "pothole_id": r.pothole_id,
            "scan_date": r.scan_date,
            "ssim_score": r.ssim_score,
            "siamese_score": r.siamese_score,
            "repair_status": r.repair_status,
            "scan_source": r.scan_source,
            "scan_satellite": r.scan_satellite,
            "before_image_path": r.before_image_path,
            "after_image_path": r.after_image_path,
        }
        for r in rows
    ]


async def _fetch_source_reports(db: AsyncSession, limit: int) -> list[dict[str, object]]:
    rows = (await db.execute(select(SourceReport).order_by(SourceReport.id.desc()).limit(limit))).scalars().all()
    return [
        {
            "id": r.id,
            "pothole_id": r.pothole_id,
            "source_type": r.source_type,
            "latitude": r.latitude,
            "longitude": r.longitude,
            "image_url": r.image_url,
            "captured_at": r.captured_at,
            "confidence_boost": r.confidence_boost,
            "processed": r.processed,
            "created_at": r.created_at,
            "raw_payload": r.raw_payload,
        }
        for r in rows
    ]


@router.get("/pdf")
async def export_pdf(
    dataset: str = Query(
        default="all",
        description="Dataset to export: all, potholes, complaints, scans, source_reports",
    ),
    limit: int = Query(default=200, ge=1, le=5000),
    db: AsyncSession = Depends(get_db),
):
    dataset = dataset.strip().lower()
    allowed = {"all", "potholes", "complaints", "scans", "source_reports"}
    if dataset not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported dataset '{dataset}'")

    pdf = _new_pdf()

    if dataset in {"all", "potholes"}:
        _add_section(pdf, "Potholes", await _fetch_potholes(db, limit))

    if dataset in {"all", "complaints"}:
        _add_section(pdf, "Complaints", await _fetch_complaints(db, limit))

    if dataset in {"all", "scans"}:
        _add_section(pdf, "Scans", await _fetch_scans(db, limit))

    if dataset in {"all", "source_reports"}:
        _add_section(pdf, "Source Reports", await _fetch_source_reports(db, limit))

    payload = bytes(pdf.output(dest="S"))
    filename = f"apis-{dataset}-export-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.pdf"

    return StreamingResponse(
        BytesIO(payload),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
