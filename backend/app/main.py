"""FastAPI application entrypoint.

Assembles all routers, middleware, Socket.IO, CORS, and Prometheus instrumentation.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware

from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Startup — ensure MinIO buckets exist
    from app.services.minio_client import ensure_buckets
    await ensure_buckets()
    yield
    # Shutdown — nothing special


app = FastAPI(
    title="Autonomous Pothole Intelligence System",
    description="AI-powered pothole detection, complaint filing & monitoring for Chhattisgarh highways",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        f"https://{settings.DOMAIN}" if hasattr(settings, "DOMAIN") else "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT auth middleware for admin routes
from app.middleware.auth import JWTAuthMiddleware
app.add_middleware(JWTAuthMiddleware)

# Prometheus metrics
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

from app.routers.public import router as public_router
from app.routers.dashboard import router as dashboard_router
from app.routers.admin_auth import router as admin_auth_router
from app.routers.admin_satellite import router as admin_satellite_router
from app.routers.admin_drone import router as admin_drone_router
from app.routers.admin_cctv import router as admin_cctv_router
from app.routers.admin_pipeline import router as admin_pipeline_router
from app.routers.admin_detection import router as admin_detection_router
from app.routers.admin_model import router as admin_model_router
from app.routers.admin_scheduler import router as admin_scheduler_router
from app.routers.admin_settings import router as admin_settings_router
from app.routers.admin_logs import router as admin_logs_router
from app.routers.admin_overview import router as admin_overview_router
from app.routers.admin_module_demo import router as admin_module_demo_router
from app.routers.mobile import router as mobile_router

app.include_router(public_router)
app.include_router(dashboard_router)
app.include_router(admin_auth_router)
app.include_router(admin_satellite_router)
app.include_router(admin_drone_router)
app.include_router(admin_cctv_router)
app.include_router(admin_pipeline_router)
app.include_router(admin_detection_router)
app.include_router(admin_model_router)
app.include_router(admin_scheduler_router)
app.include_router(admin_settings_router)
app.include_router(admin_logs_router)
app.include_router(admin_overview_router)
app.include_router(admin_module_demo_router)
app.include_router(mobile_router)

# ---------------------------------------------------------------------------
# Socket.IO mount
# ---------------------------------------------------------------------------

from app.websocket import socket_app
app.mount("/ws", socket_app)

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/version")
async def version():
    return {
        "version": "1.0.0",
        "system": "Autonomous Pothole Intelligence System",
        "region": "Chhattisgarh, India",
        "highways": ["NH-30", "NH-53", "NH-130C"],
    }
