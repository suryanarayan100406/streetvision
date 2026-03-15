"""Gemini AI service — complaint generation and risk analysis."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import time
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.admin import GeminiAudit
from app.services.risk_engine import get_urgency_language

logger = structlog.get_logger(__name__)

AUTHORITY_MAP = {
    0: "Executive Engineer, PWD Roads Division",
    1: "District Collector",
    2: "Principal Secretary, Public Works Department, Government of Chhattisgarh",
    3: "Secretary, Ministry of Road Transport and Highways, Government of India",
}

SYSTEM_INSTRUCTION = """You are a senior Public Works Department grievance documentation
officer for the state of Chhattisgarh, India. You produce formal complaint letters in
English directed to the appropriate government authority. Every letter must be factual,
cite specific GPS coordinates, road name, KM marker, and measured pothole dimensions.
The tone must be proportional to the risk score. Letters must not exceed 300 words.
If prior complaint history or verification results are provided, treat the letter as a
follow-up escalation and explicitly reference the unresolved grievance trail.
Output format:
SUBJECT: (under 120 characters)
TO: (full authority title)
BODY: (three paragraphs)
EVIDENCE SUMMARY: (five bullet points)"""


def _build_special_instructions(pothole_data: dict[str, Any], escalation_level: int) -> list[str]:
    instructions: list[str] = []
    if pothole_data.get("rain_imminent"):
        instructions.append("Include monsoon deterioration warning.")
    if escalation_level >= 3:
        instructions.append("Cite Motor Vehicles Act 1988 Section 198A regarding road authority liability.")
    if escalation_level >= 2:
        instructions.append("Reference dereliction of duty in maintaining safe road infrastructure.")
    accident_count = int(pothole_data.get("accident_count") or 0)
    if accident_count > 3:
        instructions.append(f"Cite {accident_count} documented road accidents within 2km.")
    if pothole_data.get("near_junction"):
        instructions.append("State that the defect is close to a junction, increasing conflict risk.")
    if pothole_data.get("on_curve") or pothole_data.get("on_blind_spot"):
        instructions.append("Mention reduced driver reaction time due to alignment or visibility constraints.")
    if int(pothole_data.get("days_since_filing") or 0) >= 14:
        instructions.append("State that the grievance remains unresolved beyond the 14-day verification window.")
    if pothole_data.get("latest_verification_status") and pothole_data.get("latest_verification_status") != "Repaired":
        instructions.append("Mention that the latest automated verification still shows the pothole as unresolved.")
    if pothole_data.get("prior_portal_refs"):
        instructions.append("Reference earlier grievance numbers in the body to establish escalation continuity.")
    return instructions


async def generate_complaint(
    db: AsyncSession,
    pothole_data: dict[str, Any],
    escalation_level: int = 0,
) -> dict[str, str] | None:
    """Generate a formal complaint letter using Gemini."""
    import google.generativeai as genai

    genai.configure(api_key=settings.GEMINI_API_KEY)

    risk = float(pothole_data.get("risk_score", 0))
    urgency = get_urgency_language(risk)
    authority = AUTHORITY_MAP.get(escalation_level, AUTHORITY_MAP[0])

    model_name = "gemini-1.5-pro" if escalation_level >= 2 else "gemini-1.5-flash"
    special_instructions = _build_special_instructions(pothole_data, escalation_level)

    user_prompt = f"""Generate a formal complaint letter for the following pothole:

Road Name: {pothole_data.get('road_name', 'Unknown')}
Road Type: {pothole_data.get('road_type', 'National Highway')}
KM Marker: {pothole_data.get('km_marker', 'N/A')}
District: {pothole_data.get('district', 'Chhattisgarh')}
State: Chhattisgarh
GPS: {pothole_data.get('latitude', 0)}, {pothole_data.get('longitude', 0)}
Nearest Landmark: {pothole_data.get('nearest_landmark', 'N/A')}
Area: {pothole_data.get('area_sqm', 0)} sq.m
Depth: {pothole_data.get('depth_cm', 0)} cm
Severity: {pothole_data.get('severity', 'Unknown')}
Risk Score: {risk}/100
Sources Confirming: {pothole_data.get('source_count', 1)} independent sources ({pothole_data.get('sources_list', 'satellite')})
Detection Date: {pothole_data.get('detection_date', 'N/A')}
Accident Count (2km radius): {pothole_data.get('accident_count', 0)}
Traffic Volume: {pothole_data.get('traffic_volume_category', 'N/A')}
AADT Estimate: {pothole_data.get('aadt', 'N/A')}
Rain Imminent: {pothole_data.get('rain_imminent', False)}
Forecast Rain (48h): {pothole_data.get('forecast_rain_48h_mm', 0)} mm
Weather Summary: {pothole_data.get('weather_summary', 'No forecast summary available')}
Near Junction: {pothole_data.get('near_junction', False)}
On Curve: {pothole_data.get('on_curve', False)}
Blind Spot: {pothole_data.get('on_blind_spot', False)}
Thermal Stress Zone: {pothole_data.get('thermal_stress_flag', False)}
Previous Complaints: {pothole_data.get('prev_complaint_count', 0)}
Escalation Level: {escalation_level}
Escalation Target: {pothole_data.get('escalation_target', authority)}
Days Since First Filing: {pothole_data.get('days_since_filing', 0)}
Prior Portal References: {pothole_data.get('prior_portal_refs', 'None')}
Latest Verification Status: {pothole_data.get('latest_verification_status', 'No verification run yet')}
Latest Verification Date: {pothole_data.get('latest_verification_date', 'N/A')}
Latest SSIM Score: {pothole_data.get('latest_ssim_score', 'N/A')}
Latest Siamese Score: {pothole_data.get('latest_siamese_score', 'N/A')}

Authority: {authority}
Urgency: This {urgency}.
Special Instructions:
{chr(10).join(f'- {item}' for item in special_instructions) if special_instructions else '- Keep the letter factual and concise.'}"""

    started = time.perf_counter()
    audit = GeminiAudit(
        pothole_id=pothole_data.get("pothole_id"),
        model_used=model_name,
        success=False,
        created_at=datetime.now(timezone.utc),
    )

    try:
        model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=SYSTEM_INSTRUCTION,
            generation_config=genai.GenerationConfig(
                temperature=0.3,
                max_output_tokens=600,
            ),
        )
        response = model.generate_content(user_prompt)
        text = response.text

        usage = getattr(response, "usage_metadata", None)
        audit.input_tokens = getattr(usage, "prompt_token_count", None) if usage else None
        audit.output_tokens = getattr(usage, "candidates_token_count", None) if usage else None
        audit.latency_ms = int((time.perf_counter() - started) * 1000)
        audit.success = True

        db.add(audit)
        await db.flush()

        await logger.ainfo("gemini_complaint_generated", pothole_id=pothole_data.get("pothole_id"), model=model_name)

        # Parse response into structured format
        lines = text.strip().split("\n")
        result: dict[str, str] = {"raw": text, "model": model_name}
        for line in lines:
            if line.startswith("SUBJECT:"):
                result["subject"] = line[8:].strip()
            elif line.startswith("TO:"):
                result["to"] = line[3:].strip()
        # Body is everything between TO: and EVIDENCE SUMMARY:
        body_start = text.find("BODY:") + 5 if "BODY:" in text else text.find("TO:") + len(result.get("to", "")) + 4
        body_end = text.find("EVIDENCE SUMMARY:") if "EVIDENCE SUMMARY:" in text else len(text)
        result["body"] = text[body_start:body_end].strip()

        return result

    except Exception as exc:
        audit.latency_ms = int((time.perf_counter() - started) * 1000)
        audit.success = False
        audit.error_message = str(exc)
        db.add(audit)
        await db.flush()
        await logger.aexception("gemini_call_failed", pothole_id=pothole_data.get("pothole_id"), error=str(exc))
        return None


def generate_fallback_complaint(pothole_data: dict[str, Any], escalation_level: int = 0) -> dict[str, str]:
    """Template-based fallback when Gemini is unavailable."""
    authority = AUTHORITY_MAP.get(escalation_level, AUTHORITY_MAP[0])
    severity = pothole_data.get("severity", "Unknown")
    road = pothole_data.get("road_name", "Unknown Road")
    km = pothole_data.get("km_marker", "N/A")
    lat = pothole_data.get("latitude", 0)
    lon = pothole_data.get("longitude", 0)
    area = pothole_data.get("area_sqm", 0)
    depth = pothole_data.get("depth_cm", 0)
    accident_count = pothole_data.get("accident_count", 0)
    traffic_volume = pothole_data.get("traffic_volume_category", "Unknown")
    rain_48h = pothole_data.get("forecast_rain_48h_mm", 0)
    unresolved_days = pothole_data.get("days_since_filing", 0)
    prior_refs = pothole_data.get("prior_portal_refs", "")
    latest_verification = pothole_data.get("latest_verification_status", "No verification run yet")

    subject = f"Urgent: {severity} Severity Pothole on {road} at KM {km} — Immediate Repair Required"
    body = (
        f"Respected {authority},\n\n"
        f"This is to bring to your urgent attention a {severity.lower()} severity pothole detected "
        f"on {road} at KM marker {km} (GPS: {lat}, {lon}). The pothole measures approximately "
        f"{area} square metres in area and {depth} cm in depth, posing a serious threat to road users.\n\n"
        f"The detection has been confirmed by {pothole_data.get('source_count', 1)} independent sources. "
        f"Nearby accident history stands at {accident_count} incidents within 2 km and the corridor is marked "
        f"as {traffic_volume} traffic volume. Forecast precipitation over the next 48 hours is {rain_48h} mm.\n\n"
        f"The matter has remained unresolved for {unresolved_days} day(s) since first filing. "
        f"Latest verification status is {latest_verification}. "
        f"{f'Prior portal references: {prior_refs}. ' if prior_refs else ''}"
        f"Immediate remediation is requested to prevent further accidents, pavement deterioration, and avoidable public risk.\n\n"
        f"Sincerely,\nAutonomous Pothole Intelligence System\nChhattisgarh"
    )

    return {"subject": subject, "to": authority, "body": body, "model": "fallback_template"}
