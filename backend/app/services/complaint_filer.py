"""PG Portal complaint filing via Playwright."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from app.config import settings
from app.services.minio_client import upload_bytes

logger = structlog.get_logger(__name__)


async def file_complaint_pg_portal(
    complaint_text: str,
    subject: str,
    pothole_data: dict[str, Any],
    image_path: str | None = None,
) -> dict[str, Any]:
    """File a complaint on PG Portal using Playwright headless Chromium."""
    from playwright.async_api import async_playwright

    pothole_id = pothole_data.get("pothole_id", "unknown")
    retries = [30, 90, 270]

    for attempt, wait_seconds in enumerate(retries, 1):
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()

                # Navigate to PG Portal login
                await page.goto("https://pgportal.gov.in", timeout=60000)
                await page.fill('input[name="username"]', settings.PG_PORTAL_USER)
                await page.fill('input[name="password"]', settings.PG_PORTAL_PASS)
                await page.click('button[type="submit"]')
                await page.wait_for_load_state("networkidle")

                # Navigate to new grievance form
                await page.click('text=Lodge Grievance')
                await page.wait_for_load_state("networkidle")

                # Fill grievance form
                await page.select_option('select[name="category"]', label="Road Infrastructure")
                await page.select_option('select[name="subcategory"]', label="Pothole or Road Damage")
                await page.select_option('select[name="state"]', label="Chhattisgarh")
                await page.fill('input[name="district"]', pothole_data.get("district", "Raipur"))

                # Location
                location_str = (
                    f"{pothole_data.get('road_name', '')}, KM {pothole_data.get('km_marker', '')}, "
                    f"Near {pothole_data.get('nearest_landmark', 'N/A')}, "
                    f"GPS: {pothole_data.get('latitude', 0)}, {pothole_data.get('longitude', 0)}"
                )
                await page.fill('textarea[name="location"]', location_str)
                await page.fill('textarea[name="description"]', complaint_text)

                # Upload evidence image if available
                if image_path:
                    from app.services.minio_client import download_bytes
                    import tempfile, os

                    img_data = download_bytes(image_path)
                    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
                    tmp.write(img_data)
                    tmp.close()
                    file_input = await page.query_selector('input[type="file"]')
                    if file_input:
                        await file_input.set_input_files(tmp.name)
                    os.unlink(tmp.name)

                # Submit
                await page.click('button[type="submit"]')
                await page.wait_for_selector(".confirmation-number", timeout=30000)

                # Scrape reference number
                ref_element = await page.query_selector(".confirmation-number")
                portal_ref = await ref_element.text_content() if ref_element else None

                # Take proof screenshot
                screenshot = await page.screenshot(full_page=True)
                proof_path = f"complaints/proofs/{pothole_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.png"
                upload_bytes(proof_path, screenshot, content_type="image/png")

                await browser.close()

                await logger.ainfo(
                    "complaint_filed",
                    pothole_id=pothole_id,
                    portal_ref=portal_ref,
                    attempt=attempt,
                )

                return {
                    "portal_ref": portal_ref,
                    "status": "FILED",
                    "filing_proof_path": proof_path,
                    "filed_at": datetime.now(timezone.utc).isoformat(),
                }

        except Exception as exc:
            await logger.aexception(
                "pg_portal_filing_failed",
                pothole_id=pothole_id,
                attempt=attempt,
                error=str(exc),
            )
            if attempt < len(retries):
                import asyncio
                await asyncio.sleep(wait_seconds)

    return {"status": "PENDING_RETRY", "error": "All filing attempts failed"}


async def send_email_fallback(
    to_email: str,
    subject: str,
    body: str,
    pothole_id: int | str,
) -> bool:
    """Send complaint via email as fallback."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    try:
        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_USER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASS)
            server.send_message(msg)

        await logger.ainfo("email_fallback_sent", to=to_email, pothole_id=pothole_id)
        return True
    except Exception as exc:
        await logger.aexception("email_fallback_failed", to=to_email, error=str(exc))
        return False
