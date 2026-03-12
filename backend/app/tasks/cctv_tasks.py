"""CCTV and inference tasks."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal

import structlog

from app.tasks.celery_app import app
from app.database import async_session_factory

logger = structlog.get_logger(__name__)


@app.task(name="app.tasks.cctv_tasks.run_inference_on_tile", bind=True)
def run_inference_on_tile(self, tile_id: str, source: str, highway: str):
    """Run YOLOv8 + MiDaS inference on a single tile from any source."""

    async def _run():
        from app.ml.detector import PotholeDetector
        from app.ml.depth_estimator import DepthEstimator
        from app.models.pothole import Pothole
        from app.models.source_report import SourceReport
        from app.services.confidence_engine import recompute_confidence, determine_action
        from app.services.risk_engine import compute_risk_score
        from app.services.geocoder import reverse_geocode

        detector = PotholeDetector()
        depth_estimator = DepthEstimator()

        # In production, tile would be loaded from MinIO
        # Here we process whatever source provides
        detections = detector.detect_from_source(tile_id, source)

        async with async_session_factory() as db:
            created = 0
            for det in detections:
                lat, lon = det["latitude"], det["longitude"]

                # Geocode
                try:
                    geo = await reverse_geocode(lat, lon)
                except Exception:
                    geo = {"road_name": "", "district": "", "nearest_landmark": ""}

                # Depth estimation
                depth_cm = depth_estimator.estimate_depth(det.get("crop"))
                area_sqm = det.get("area_sqm", 0)

                # Classification
                severity = classify_severity(area_sqm, depth_cm)

                pothole = Pothole(
                    geom=f"SRID=4326;POINT({lon} {lat})",
                    severity=severity,
                    area_sqm=Decimal(str(round(area_sqm, 4))),
                    depth_cm=Decimal(str(round(depth_cm, 2))),
                    confidence_score=Decimal(str(round(det["confidence"], 3))),
                    source_primary=source,
                    satellite_source=source if "SAT" in source or source in (
                        "SENTINEL-2", "SENTINEL-1", "CARTOSAT-3", "CARTOSAT-2S",
                        "LANDSAT-9", "RISAT-2B", "EOS-04", "ALOS-2", "MODIS"
                    ) else None,
                    image_path=det.get("image_path"),
                    detected_at=datetime.now(timezone.utc),
                    road_name=geo.get("road_name"),
                    km_marker=det.get("km_marker"),
                    district=geo.get("district"),
                    nearest_landmark=geo.get("nearest_landmark"),
                )
                db.add(pothole)
                await db.flush()

                # Add source report
                report = SourceReport(
                    pothole_id=pothole.id,
                    source=source,
                    report_type="DETECTION",
                    gps=f"SRID=4326;POINT({lon} {lat})",
                    timestamp=datetime.now(timezone.utc),
                    image_path=det.get("image_path"),
                    confidence_boost=Decimal(str(det["confidence"])),
                )
                db.add(report)
                await db.flush()

                # Recompute confidence and risk
                conf = await recompute_confidence(db, pothole.id)
                await compute_risk_score(db, pothole.id)

                action = determine_action(conf)
                if action == "AUTO_FILE_COMPLAINT":
                    from app.tasks.filing_tasks import file_complaint
                    file_complaint.delay(pothole.id)

                created += 1

            await db.commit()
            return {"source": source, "tile_id": tile_id, "detections": created}

    return asyncio.get_event_loop().run_until_complete(_run())


@app.task(name="app.tasks.cctv_tasks.process_cctv_frame", bind=True)
def process_cctv_frame(self, camera_id: str):
    """Capture and process a single frame from a CCTV camera."""

    async def _process():
        from sqlalchemy import select
        from app.models.cctv import CCTVNode
        from app.services.cctv_manager import capture_and_process_frame

        async with async_session_factory() as db:
            result = await db.execute(
                select(CCTVNode).where(CCTVNode.camera_id == camera_id, CCTVNode.status == "ACTIVE")
            )
            node = result.scalar_one_or_none()
            if not node:
                return {"error": f"Camera {camera_id} not found or inactive"}

            frame_data = capture_and_process_frame(
                node.rtsp_url,
                perspective_matrix=node.perspective_matrix,
            )
            if not frame_data:
                return {"error": "Frame capture failed"}

            # Save frame and run inference
            import cv2
            from app.services.minio_client import upload_bytes

            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            frame_path = f"cctv/{camera_id}/{ts}.jpg"
            _, buffer = cv2.imencode(".jpg", frame_data["frame"])
            upload_bytes(frame_path, buffer.tobytes(), content_type="image/jpeg")

            # Queue inference
            run_inference_on_tile.delay(frame_path, "CCTV", node.highway or "")

            # Update last active
            node.last_active = datetime.now(timezone.utc)
            await db.commit()

            return {"camera_id": camera_id, "frame_path": frame_path}

    return asyncio.get_event_loop().run_until_complete(_process())


def classify_severity(area_sqm: float, depth_cm: float) -> str:
    """Classify pothole severity based on area and depth. Higher wins."""
    area_sev = "Low"
    if area_sqm > 1.5:
        area_sev = "Critical"
    elif area_sqm > 0.5:
        area_sev = "High"
    elif area_sqm > 0.1:
        area_sev = "Medium"

    depth_sev = "Low"
    if depth_cm > 10:
        depth_sev = "Critical"
    elif depth_cm > 5:
        depth_sev = "High"
    elif depth_cm > 2:
        depth_sev = "Medium"

    severity_order = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
    return area_sev if severity_order[area_sev] >= severity_order[depth_sev] else depth_sev
