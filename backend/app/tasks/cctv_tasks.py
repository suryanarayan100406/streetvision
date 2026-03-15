"""CCTV and inference tasks."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog

from app.tasks.celery_app import app
from app.database import async_session_factory
from app.ml.classifier import classify_from_detection
from app.services.decision_engine import decide_detection_action, normalize_source_type
from app.services.risk_engine import compute_risk_score

logger = structlog.get_logger(__name__)


@app.task(name="app.tasks.cctv_tasks.run_inference_on_tile", bind=True)
def run_inference_on_tile(
    self,
    tile_id: str,
    source: str,
    highway: str,
    satellite_job_id: int | None = None,
    source_context: dict | None = None,
):
    """Run YOLOv8 + MiDaS inference on a single tile from any source."""

    async def _run():
        import cv2
        import httpx
        import numpy as np
        from sqlalchemy import func, select

        from app.config import settings
        from app.ml.detector import detect
        from app.ml.depth_estimator import estimate_depth
        from app.models.pothole import Pothole
        from app.models.satellite import SatelliteJob
        from app.models.source_report import SourceReport
        from app.services.minio_client import download_bytes
        from app.services.geocoder import reverse_geocode

        async def _update_job_progress(detections_increment: int = 0, error: str | None = None) -> None:
            if satellite_job_id is None:
                return
            async with async_session_factory() as job_db:
                job = await job_db.get(SatelliteJob, satellite_job_id)
                if job is None:
                    return
                job.tiles_processed = int(job.tiles_processed or 0) + 1
                job.detections_count = int(job.detections_count or 0) + int(detections_increment or 0)
                if error:
                    job.error_message = error
                if int(job.tiles_processed or 0) >= int(job.tiles_total or 0):
                    job.status = "COMPLETED" if not job.error_message else "COMPLETED"
                    job.completed_at = datetime.now(timezone.utc)
                await job_db.commit()

        async def _oam_context_from_uuid(uuid_value: str) -> dict:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.openaerialmap.org/meta",
                    params={"uuid": uuid_value, "limit": 1},
                    timeout=30.0,
                )
                response.raise_for_status()
                result = (response.json().get("results") or [None])[0]

            if not result:
                return {}

            bbox = result.get("bbox") or (result.get("geojson") or {}).get("bbox")
            center_lat = 0.0
            center_lon = 0.0
            if isinstance(bbox, list) and len(bbox) == 4:
                center_lon = float((bbox[0] + bbox[2]) / 2.0)
                center_lat = float((bbox[1] + bbox[3]) / 2.0)

            gsd = result.get("gsd") or (result.get("properties") or {}).get("resolution_in_meters")
            return {
                "lat": center_lat,
                "lon": center_lon,
                "bbox": bbox,
                "gsd_m_per_px": float(gsd) if gsd is not None else None,
            }

        async def _load_image_and_context() -> tuple[np.ndarray | None, dict]:
            context: dict = {
                "lat": 0.0,
                "lon": 0.0,
                "bbox": None,
                "gsd_m_per_px": None,
            }
            if source_context:
                context.update(source_context)

            if source.upper().startswith("OAM") and tile_id.startswith("http"):
                context.update(await _oam_context_from_uuid(tile_id))
                async with httpx.AsyncClient() as client:
                    resp = await client.get(tile_id, timeout=90.0, follow_redirects=True)
                    resp.raise_for_status()
                    raw = resp.content
            else:
                raw = download_bytes(tile_id)

            image = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
            return image, context

        try:
            image, context = await _load_image_and_context()
        except Exception as exc:
            await logger.aexception("inference_image_load_failed", tile_id=tile_id, source=source, error=str(exc))
            await _update_job_progress(error="image_load_failed")
            return {"source": source, "tile_id": tile_id, "detections": 0, "error": "image_load_failed"}

        if image is None:
            await logger.aerror("inference_image_decode_failed", tile_id=tile_id, source=source)
            await _update_job_progress(error="image_decode_failed")
            return {"source": source, "tile_id": tile_id, "detections": 0, "error": "image_decode_failed"}

        source_upper = (source or "").upper()
        gsd_value = context.get("gsd_m_per_px")
        try:
            gsd_value = float(gsd_value) if gsd_value is not None else None
        except (TypeError, ValueError):
            gsd_value = None

        if source_upper in {"SENTINEL-2", "LANDSAT-9", "LANDSAT-8"} and gsd_value is not None and gsd_value > float(settings.SATELLITE_POTHOLE_MAX_GSD_M):
            await logger.ainfo(
                "inference_skipped_coarse_resolution",
                tile_id=tile_id,
                source=source,
                gsd_m_per_px=gsd_value,
                threshold_m_per_px=float(settings.SATELLITE_POTHOLE_MAX_GSD_M),
            )
            await _update_job_progress()
            return {
                "source": source,
                "tile_id": tile_id,
                "detections": 0,
                "skipped": "coarse_resolution",
                "gsd_m_per_px": gsd_value,
                "threshold_m_per_px": float(settings.SATELLITE_POTHOLE_MAX_GSD_M),
            }

        detections = await detect(image, confidence=float(settings.YOLO_CONFIDENCE_THRESHOLD))

        async with async_session_factory() as db:
            original_report_result = await db.execute(
                select(SourceReport)
                .where(
                    SourceReport.image_url == tile_id,
                    func.lower(SourceReport.source_type) == str(source or "").lower(),
                    SourceReport.processed.is_(False),
                )
                .order_by(SourceReport.id.desc())
                .limit(1)
            )
            original_report = original_report_result.scalar_one_or_none()

            created = 0
            created_pothole_ids: list[int] = []
            for det in detections:
                lat = float(context.get("lat") or 0.0)
                lon = float(context.get("lon") or 0.0)

                if abs(lat) > 0.000001 or abs(lon) > 0.000001:
                    try:
                        geo = await reverse_geocode(lat, lon)
                    except Exception:
                        geo = {"road_name": "", "district": "", "nearest_landmark": ""}
                else:
                    geo = {"road_name": "", "district": "", "nearest_landmark": ""}

                try:
                    depth_result = await estimate_depth(image, det.get("mask"))
                    depth_cm = float(depth_result.get("estimated_depth_cm") or 0.0)
                except Exception as exc:
                    depth_cm = 0.0
                    await logger.awarning(
                        "depth_estimation_failed_fallback_zero",
                        tile_id=tile_id,
                        source=source,
                        error=str(exc),
                    )

                gsd = float(context.get("gsd_m_per_px") or 0.05)
                area_px = int(det.get("area_px") or 0)
                area_sqm = float(area_px * (gsd**2)) if area_px > 0 else 0.0

                base_conf = float(det.get("confidence", 0.6) or 0.6)

                severity_meta = classify_from_detection(
                    det,
                    gsd_m_per_px=gsd,
                    depth_cm=depth_cm,
                    near_junction=False,
                    on_curve=False,
                    aadt=0,
                )
                severity = severity_meta.get("severity", "Medium")

                decision = decide_detection_action(
                    yolo_confidence=base_conf,
                    source_type=source,
                    area_m2=area_sqm,
                    depth_cm=depth_cm,
                    severity=severity,
                )

                normalized_source = normalize_source_type(source)
                if decision.get("source_multiplier", 1.0) == 1.0 and normalized_source not in {"UNKNOWN", "CCTV"}:
                    await logger.awarning(
                        "decision_source_not_mapped",
                        source=source,
                        normalized_source=normalized_source,
                        tile_id=tile_id,
                    )

                pothole = Pothole(
                    latitude=float(lat),
                    longitude=float(lon),
                    geom=f"SRID=4326;POINT({lon} {lat})",
                    severity=severity,
                    confidence_score=decision["fused_confidence"],
                    risk_score=decision["risk_score"],
                    status="Detected",
                    nh_number=highway or None,
                    district=geo.get("district") or None,
                    address=geo.get("road_name") or geo.get("nearest_landmark") or None,
                    estimated_area_m2=round(float(area_sqm), 4) if area_sqm is not None else None,
                    estimated_depth_cm=round(float(depth_cm), 2) if depth_cm is not None else None,
                    image_path=tile_id,
                    detected_at=datetime.now(timezone.utc),
                )
                db.add(pothole)
                await db.flush()

                try:
                    async with db.begin_nested():
                        canonical_risk = await compute_risk_score(db, pothole.id)
                    pothole.risk_score = float(canonical_risk)
                except Exception as exc:
                    await logger.awarning(
                        "risk_score_recompute_failed_using_decision_risk",
                        pothole_id=pothole.id,
                        error=str(exc),
                    )

                report = SourceReport(
                    pothole_id=pothole.id,
                    source_type=source,
                    latitude=float(lat),
                    longitude=float(lon),
                    raw_payload={
                        "tile_id": tile_id,
                        "highway": highway,
                        "bbox": context.get("bbox"),
                        "class_name": det.get("class_name"),
                        "bbox_px": det.get("bbox"),
                        "yolo_confidence": round(base_conf, 3),
                        "depth_cm": round(float(depth_cm), 2),
                        "area_m2": round(float(area_sqm), 4),
                        "severity_score": severity_meta.get("score"),
                        "decision_action": decision["action"],
                        "fused_confidence": decision["fused_confidence"],
                        "decision_risk_score": decision["risk_score"],
                        "canonical_risk_score": float(pothole.risk_score or 0),
                        "source_multiplier": decision.get("source_multiplier", 1.0),
                        "normalized_source": decision.get("normalized_source", normalized_source),
                        "decision_reason": decision.get("decision_reason"),
                    },
                    image_url=tile_id,
                    captured_at=datetime.now(timezone.utc),
                    confidence_boost=decision["fused_confidence"],
                    processed=True,
                )
                db.add(report)
                await db.flush()

                created_pothole_ids.append(int(pothole.id))

                action = decision["action"]
                if action == "AUTO_FILE_COMPLAINT" and float(pothole.risk_score or 0) >= float(settings.AUTO_FILE_MIN_RISK_SCORE):
                    from app.tasks.filing_tasks import file_complaint
                    file_complaint.delay(pothole.id)

                created += 1

            if original_report is not None:
                original_report.processed = True
                if len(created_pothole_ids) == 1:
                    original_report.pothole_id = created_pothole_ids[0]
                payload = dict(original_report.raw_payload or {})
                payload.update(
                    {
                        "inference_tile_id": tile_id,
                        "detections_created": created,
                        "created_pothole_ids": created_pothole_ids,
                    }
                )
                original_report.raw_payload = payload

            await db.commit()
            await _update_job_progress(detections_increment=created)
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
                select(CCTVNode).where(CCTVNode.name == camera_id, CCTVNode.is_active.is_(True))
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
            run_inference_on_tile.delay(frame_path, "CCTV", node.nh_number or "")

            # Update last active
            node.last_frame_at = datetime.now(timezone.utc)
            await db.commit()

            return {"camera_id": camera_id, "frame_path": frame_path}

    return asyncio.get_event_loop().run_until_complete(_process())


@app.task(name="app.tasks.cctv_tasks.poll_active_cctv_nodes", bind=True)
def poll_active_cctv_nodes(self, limit: int = 200):
    """Queue frame processing for all active CCTV nodes."""

    async def _run():
        from sqlalchemy import select
        from app.models.cctv import CCTVNode

        async with async_session_factory() as db:
            result = await db.execute(
                select(CCTVNode.id, CCTVNode.nh_number)
                .where(CCTVNode.is_active.is_(True))
                .order_by(CCTVNode.id.asc())
                .limit(limit)
            )
            rows = result.all()

        queued = 0
        for row in rows:
            process_cctv_node.delay(int(row.id), row.nh_number)
            queued += 1

        await logger.ainfo(
            "poll_active_cctv_nodes_queued",
            queued=queued,
            limit=limit,
        )
        return {"queued": queued, "limit": limit}

    return asyncio.get_event_loop().run_until_complete(_run())


@app.task(name="app.tasks.cctv_tasks.process_cctv_node", bind=True)
def process_cctv_node(self, node_id: int, highway: str | None = None):
    """Capture and process a single frame from a CCTV node by node id."""

    async def _process():
        from sqlalchemy import select
        from app.models.cctv import CCTVNode
        from app.services.cctv_manager import capture_and_process_frame
        from app.services.minio_client import upload_bytes

        import cv2

        async with async_session_factory() as db:
            result = await db.execute(select(CCTVNode).where(CCTVNode.id == node_id, CCTVNode.is_active.is_(True)))
            node = result.scalar_one_or_none()
            if not node:
                return {"error": f"CCTV node {node_id} not found or inactive"}

            frame_data = capture_and_process_frame(
                node.rtsp_url,
                perspective_matrix=node.perspective_matrix,
            )
            if not frame_data:
                return {"error": "Frame capture failed"}

            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            frame_path = f"cctv/node_{node_id}/{ts}.jpg"
            _, buffer = cv2.imencode(".jpg", frame_data["frame"])
            upload_bytes(frame_path, buffer.tobytes(), content_type="image/jpeg")

            run_inference_on_tile.delay(frame_path, "CCTV", highway or node.nh_number or "")

            node.last_frame_at = datetime.now(timezone.utc)
            await db.commit()

            return {"node_id": node_id, "frame_path": frame_path, "queued": True}

    return asyncio.get_event_loop().run_until_complete(_process())
