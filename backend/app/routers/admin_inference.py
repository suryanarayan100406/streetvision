"""Admin inference module endpoints for decision-engine diagnostics."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pothole import Pothole
from app.models.settings import ModelRegistry
from app.models.source_report import SourceReport
from app.services.decision_engine import decide_detection_action

router = APIRouter(prefix="/api/admin/inference", tags=["admin-inference"])


@router.get("/overview")
async def inference_overview(db: AsyncSession = Depends(get_db)):
    active_models_q = await db.execute(
        select(ModelRegistry)
        .where(ModelRegistry.is_active.is_(True))
        .order_by(ModelRegistry.model_type.asc(), ModelRegistry.id.desc())
    )
    active_models = active_models_q.scalars().all()

    detections_q = await db.execute(
        select(Pothole)
        .order_by(Pothole.detected_at.desc())
        .limit(40)
    )
    potholes = detections_q.scalars().all()

    rows = []
    for p in potholes:
        report_q = await db.execute(
            select(SourceReport)
            .where(SourceReport.pothole_id == p.id)
            .order_by(SourceReport.id.desc())
            .limit(1)
        )
        latest_report = report_q.scalar_one_or_none()
        payload = latest_report.raw_payload if latest_report and latest_report.raw_payload else {}
        yolo_conf = float(payload.get("yolo_confidence") or p.confidence_score or 0.0)
        area_m2 = float(payload.get("area_m2") or p.estimated_area_m2 or 0.0)
        depth_cm = float(payload.get("depth_cm") or p.estimated_depth_cm or 0.0)
        source_type = latest_report.source_type if latest_report else "UNKNOWN"
        severity = p.severity or "Medium"

        decision = decide_detection_action(
            yolo_confidence=yolo_conf,
            source_type=source_type,
            area_m2=area_m2,
            depth_cm=depth_cm,
            severity=severity,
        )

        rows.append(
            {
                "pothole_id": int(p.id),
                "source_type": source_type,
                "severity": severity,
                "yolo_confidence": round(yolo_conf, 3),
                "fused_confidence": decision["fused_confidence"],
                "depth_cm": round(depth_cm, 2),
                "area_m2": round(area_m2, 4),
                "decision_action": decision["action"],
                "risk_score": decision["risk_score"],
                "detected_at": p.detected_at.isoformat() if p.detected_at else None,
            }
        )

    auto_file = sum(1 for row in rows if row["decision_action"] == "AUTO_FILE_COMPLAINT")
    review = sum(1 for row in rows if row["decision_action"] == "FLAG_FOR_REVIEW")
    monitor = sum(1 for row in rows if row["decision_action"] == "MONITOR")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "models": [
            {
                "model_type": model.model_type,
                "model_name": model.model_name,
                "version": model.version,
                "weights_path": model.weights_path,
                "is_active": bool(model.is_active),
            }
            for model in active_models
        ],
        "summary": {
            "rows": len(rows),
            "auto_file": auto_file,
            "review": review,
            "monitor": monitor,
        },
        "recent_decisions": rows,
    }
