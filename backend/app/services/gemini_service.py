"""Gemini AI service — complaint generation and risk analysis."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
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
Output format:
SUBJECT: (under 120 characters)
TO: (full authority title)
BODY: (three paragraphs)
EVIDENCE SUMMARY: (five bullet points)"""


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
Risk Score: {risk}/10.0
Sources Confirming: {pothole_data.get('source_count', 1)} independent sources ({pothole_data.get('sources_list', 'satellite')})
Detection Date: {pothole_data.get('detection_date', 'N/A')}
Accident Count (2km radius): {pothole_data.get('accident_count', 0)}
Traffic Volume: {pothole_data.get('traffic_volume_category', 'N/A')}
Rain Imminent: {pothole_data.get('rain_imminent', False)}
Forecast Rain (48h): {pothole_data.get('forecast_rain_48h_mm', 0)} mm
Previous Complaints: {pothole_data.get('prev_complaint_count', 0)}
Escalation Level: {escalation_level}
Days Since First Filing: {pothole_data.get('days_since_filing', 0)}

Authority: {authority}
Urgency: This {urgency}.
{"Include monsoon deterioration warning." if pothole_data.get('rain_imminent') else ""}
{"Cite Motor Vehicles Act 1988 Section 198A regarding road authority liability." if escalation_level >= 3 else ""}
{"Reference dereliction of duty in maintaining safe road infrastructure." if escalation_level >= 2 else ""}
{"Cite {pothole_data.get('accident_count', 0)} documented road accidents within 2km." if pothole_data.get('accident_count', 0) > 3 else ""}"""

    audit = GeminiAudit(
        pothole_id=pothole_data.get("pothole_id"),
        use_case="complaint_generation",
        prompt_text=user_prompt,
        model_name=model_name,
        called_at=datetime.now(timezone.utc),
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

        audit.response_text = text
        audit.prompt_tokens = response.usage_metadata.prompt_token_count if hasattr(response, "usage_metadata") else None
        audit.completion_tokens = response.usage_metadata.candidates_token_count if hasattr(response, "usage_metadata") else None
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

    subject = f"Urgent: {severity} Severity Pothole on {road} at KM {km} — Immediate Repair Required"
    body = (
        f"Respected {authority},\n\n"
        f"This is to bring to your urgent attention a {severity.lower()} severity pothole detected "
        f"on {road} at KM marker {km} (GPS: {lat}, {lon}). The pothole measures approximately "
        f"{area} square metres in area and {depth} cm in depth, posing a serious threat to road users.\n\n"
        f"The detection has been confirmed by {pothole_data.get('source_count', 1)} independent sources. "
        f"Immediate remediation is requested to prevent potential accidents and ensure road safety.\n\n"
        f"Sincerely,\nAutonomous Pothole Intelligence System\nChhattisgarh"
    )

    return {"subject": subject, "to": authority, "body": body, "model": "fallback_template"}
