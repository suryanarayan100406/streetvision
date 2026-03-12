"""Data ingestion tasks: crowdsource, accident, OSM, traffic, leaderboard, cleanup."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy import select, delete

from app.tasks.celery_app import app
from app.database import async_session_factory

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Crowdsource / street-level imagery
# ---------------------------------------------------------------------------


@app.task(name="app.tasks.data_ingestion_tasks.ingest_mapillary")
def ingest_mapillary():
    """Fetch recent Mapillary sequences covering the highway corridors."""

    async def _run():
        import httpx
        from app.config import settings
        from app.models.source_report import SourceReport

        if not settings.MAPILLARY_TOKEN:
            return {"skipped": "no token"}

        bbox_corridors = {
            "NH-30": "80.5,20.5,82.5,23.5",
            "NH-53": "81.0,21.0,84.0,22.5",
            "NH-130C": "81.5,21.8,82.5,22.5",
        }
        total = 0
        async with httpx.AsyncClient(timeout=60) as client:
            for name, bbox in bbox_corridors.items():
                resp = await client.get(
                    "https://graph.mapillary.com/images",
                    params={
                        "access_token": settings.MAPILLARY_TOKEN,
                        "bbox": bbox,
                        "fields": "id,geometry,captured_at,thumb_1024_url",
                        "limit": 50,
                    },
                )
                if resp.status_code != 200:
                    continue
                data = resp.json().get("data", [])
                async with async_session_factory() as db:
                    for item in data:
                        coords = item["geometry"]["coordinates"]
                        sr = SourceReport(
                            source_type="mapillary",
                            raw_payload=item,
                            latitude=coords[1],
                            longitude=coords[0],
                            captured_at=datetime.fromtimestamp(
                                item["captured_at"] / 1000, tz=timezone.utc
                            ) if isinstance(item.get("captured_at"), (int, float)) else None,
                            image_url=item.get("thumb_1024_url"),
                            processed=False,
                        )
                        db.add(sr)
                        total += 1
                    await db.commit()

        return {"ingested": total}

    return asyncio.get_event_loop().run_until_complete(_run())


@app.task(name="app.tasks.data_ingestion_tasks.ingest_kartaview")
def ingest_kartaview():
    """Fetch KartaView sequences near highway corridors."""

    async def _run():
        import httpx

        bbox_corridors = {
            "NH-30": "80.5,20.5,82.5,23.5",
            "NH-53": "81.0,21.0,84.0,22.5",
            "NH-130C": "81.5,21.8,82.5,22.5",
        }
        total = 0
        async with httpx.AsyncClient(timeout=60) as client:
            for name, bbox in bbox_corridors.items():
                parts = bbox.split(",")
                resp = await client.get(
                    "https://api.openstreetcam.org/2.0/photo/",
                    params={
                        "bbTopLeft": f"{parts[3]},{parts[0]}",
                        "bbBottomRight": f"{parts[1]},{parts[2]}",
                        "page": 1,
                        "itemsPerPage": 50,
                    },
                )
                if resp.status_code != 200:
                    continue
                data = resp.json().get("result", {}).get("data", [])
                async with async_session_factory() as db:
                    from app.models.source_report import SourceReport

                    for item in data:
                        sr = SourceReport(
                            source_type="kartaview",
                            raw_payload=item,
                            latitude=float(item.get("lat", 0)),
                            longitude=float(item.get("lng", 0)),
                            image_url=item.get("lth_name"),
                            processed=False,
                        )
                        db.add(sr)
                        total += 1
                    await db.commit()
        return {"ingested": total}

    return asyncio.get_event_loop().run_until_complete(_run())


@app.task(name="app.tasks.data_ingestion_tasks.ingest_osm_notes")
def ingest_osm_notes():
    """Fetch OpenStreetMap notes about potholes / road damage in CG."""

    async def _run():
        import httpx

        bbox = "80.5,20.5,84.5,24.0"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                "https://api.openstreetmap.org/api/0.6/notes.json",
                params={"bbox": bbox, "closed": 0, "limit": 100},
            )
            if resp.status_code != 200:
                return {"error": resp.status_code}

            notes = resp.json().get("features", [])
            pothole_notes = [
                n for n in notes
                if any(
                    kw in str(n.get("properties", {}).get("comments", "")).lower()
                    for kw in ("pothole", "road damage", "crater", "broken road")
                )
            ]

            async with async_session_factory() as db:
                from app.models.source_report import SourceReport

                for n in pothole_notes:
                    coords = n["geometry"]["coordinates"]
                    sr = SourceReport(
                        source_type="osm_notes",
                        raw_payload=n,
                        latitude=coords[1],
                        longitude=coords[0],
                        processed=False,
                    )
                    db.add(sr)
                await db.commit()

            return {"ingested": len(pothole_notes)}

    return asyncio.get_event_loop().run_until_complete(_run())


# ---------------------------------------------------------------------------
# Accident & traffic data
# ---------------------------------------------------------------------------


@app.task(name="app.tasks.data_ingestion_tasks.ingest_accident_data")
def ingest_accident_data():
    """Fetch accident data from data.gov.in (NCRB proxy)."""

    async def _run():
        import httpx
        from app.config import settings

        if not settings.DATA_GOV_IN_API_KEY:
            return {"skipped": "no API key"}

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                "https://api.data.gov.in/resource/road-accident-data",
                params={
                    "api-key": settings.DATA_GOV_IN_API_KEY,
                    "format": "json",
                    "filters[state]": "CHHATTISGARH",
                    "limit": 500,
                },
            )
            if resp.status_code != 200:
                return {"error": resp.status_code}

            records = resp.json().get("records", [])
            async with async_session_factory() as db:
                from app.models.road import RoadAccident

                for rec in records:
                    acc = RoadAccident(
                        state="CHHATTISGARH",
                        district=rec.get("district"),
                        year=int(rec.get("year", 0)),
                        total_accidents=int(rec.get("total_accidents", 0)),
                        persons_killed=int(rec.get("persons_killed", 0)),
                        persons_injured=int(rec.get("persons_injured", 0)),
                        raw_payload=rec,
                    )
                    db.add(acc)
                await db.commit()

            return {"ingested": len(records)}

    return asyncio.get_event_loop().run_until_complete(_run())


@app.task(name="app.tasks.data_ingestion_tasks.ingest_nhai_traffic")
def ingest_nhai_traffic():
    """Pull NHAI traffic count data for NH-30, NH-53, NH-130C."""

    async def _run():
        import httpx

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                "https://tms.nhai.gov.in/api/traffic",
                params={"state": "Chhattisgarh"},
            )
            if resp.status_code != 200:
                return {"error": resp.status_code}

            data = resp.json()
            async with async_session_factory() as db:
                from app.models.road import RoadSegment

                for entry in data.get("stations", []):
                    nh = entry.get("nh_number", "")
                    if nh not in ("30", "53", "130C"):
                        continue
                    result = await db.execute(
                        select(RoadSegment).where(
                            RoadSegment.nh_number == f"NH-{nh}",
                            RoadSegment.chainage_km.between(
                                float(entry.get("start_km", 0)),
                                float(entry.get("end_km", 999)),
                            ),
                        )
                    )
                    segment = result.scalar_one_or_none()
                    if segment:
                        segment.aadt = int(entry.get("aadt", 0))
                await db.commit()

        return {"updated": True}

    return asyncio.get_event_loop().run_until_complete(_run())


# ---------------------------------------------------------------------------
# OSM road geometry
# ---------------------------------------------------------------------------


@app.task(name="app.tasks.data_ingestion_tasks.ingest_osm_road_geometry")
def ingest_osm_road_geometry():
    """Fetch road geometry from Overpass API for CG national highways."""

    async def _run():
        import httpx

        overpass_query = """
        [out:json][timeout:120];
        area["ISO3166-2"="IN-CT"]->.cg;
        way["ref"~"NH 30|NH 53|NH 130C"](area.cg);
        out geom;
        """
        async with httpx.AsyncClient(timeout=180) as client:
            resp = await client.post(
                "https://overpass-api.de/api/interpreter",
                data={"data": overpass_query},
            )
            if resp.status_code != 200:
                return {"error": resp.status_code}

            elements = resp.json().get("elements", [])
            logger.info("osm_road_geometry", count=len(elements))
            return {"fetched_ways": len(elements)}

    return asyncio.get_event_loop().run_until_complete(_run())


# ---------------------------------------------------------------------------
# Leaderboard, model metrics, cleanup
# ---------------------------------------------------------------------------


@app.task(name="app.tasks.data_ingestion_tasks.refresh_leaderboard")
def refresh_leaderboard():
    """Refresh gamification leaderboard points."""

    async def _run():
        from app.models.settings import GamificationPoints
        from sqlalchemy import func

        async with async_session_factory() as db:
            result = await db.execute(
                select(GamificationPoints)
                .order_by(GamificationPoints.total_points.desc())
                .limit(100)
            )
            entries = result.scalars().all()
            for rank, entry in enumerate(entries, 1):
                entry.rank = rank
            await db.commit()
            return {"ranked": len(entries)}

    return asyncio.get_event_loop().run_until_complete(_run())


@app.task(name="app.tasks.data_ingestion_tasks.collect_model_metrics")
def collect_model_metrics():
    """Collect and log ML model performance metrics to MLflow."""

    async def _run():
        from app.models.settings import ModelRegistry

        async with async_session_factory() as db:
            result = await db.execute(
                select(ModelRegistry).where(ModelRegistry.is_active.is_(True))
            )
            models = result.scalars().all()
            metrics = {}
            for m in models:
                metrics[m.model_name] = {
                    "version": m.version,
                    "precision": m.precision,
                    "recall": m.recall,
                    "f1": m.f1_score,
                }
            return metrics

    return asyncio.get_event_loop().run_until_complete(_run())


@app.task(name="app.tasks.data_ingestion_tasks.cleanup_old_minio_objects")
def cleanup_old_minio_objects():
    """Remove MinIO objects older than 90 days for non-critical data."""

    async def _run():
        from app.services.minio_client import minio
        from datetime import timedelta

        cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        buckets_to_clean = ["temp-tiles", "processing-scratch"]
        removed = 0

        for bucket in buckets_to_clean:
            try:
                objects = minio.list_objects(bucket, recursive=True)
                for obj in objects:
                    if obj.last_modified and obj.last_modified < cutoff:
                        minio.remove_object(bucket, obj.object_name)
                        removed += 1
            except Exception as e:
                logger.warning("minio_cleanup_error", bucket=bucket, error=str(e))

        return {"removed": removed}

    return asyncio.get_event_loop().run_until_complete(_run())


@app.task(name="app.tasks.data_ingestion_tasks.database_backup")
def database_backup():
    """Trigger a PostgreSQL backup via pg_dump to MinIO."""

    import subprocess
    import os
    from app.config import settings

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dump_path = f"/tmp/backup_{ts}.sql.gz"

    try:
        env = os.environ.copy()
        env["PGPASSWORD"] = settings.DATABASE_URL.split(":")[-1].split("@")[0]

        subprocess.run(
            f"pg_dump {settings.DATABASE_URL} | gzip > {dump_path}",
            shell=False,  # avoid shell injection
            check=True,
            env=env,
            capture_output=True,
        )

        # Upload to MinIO
        from app.services.minio_client import upload_file

        asyncio.get_event_loop().run_until_complete(
            upload_file("backups", f"db/backup_{ts}.sql.gz", dump_path)
        )

        # Remove local file
        os.unlink(dump_path)
        return {"backup": f"backup_{ts}.sql.gz"}
    except Exception as e:
        logger.error("backup_failed", error=str(e))
        return {"error": str(e)}
