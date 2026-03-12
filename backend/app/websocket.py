"""Socket.IO real-time event manager.

Provides two namespaces:
  /admin-stream  — admin panel live updates (detections, tasks, alerts)
  /dashboard-stream — public dashboard live map updates
"""

from __future__ import annotations

import socketio
import structlog

logger = structlog.get_logger(__name__)

# Create async Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

# Wrap as ASGI app for mounting
socket_app = socketio.ASGIApp(sio, socketio_path="/socket.io")


# ---------------------------------------------------------------------------
# Admin namespace
# ---------------------------------------------------------------------------


@sio.on("connect", namespace="/admin-stream")
async def admin_connect(sid, environ):
    logger.info("admin_ws_connected", sid=sid)
    await sio.emit(
        "connected",
        {"message": "Admin stream connected"},
        namespace="/admin-stream",
        to=sid,
    )


@sio.on("disconnect", namespace="/admin-stream")
async def admin_disconnect(sid):
    logger.info("admin_ws_disconnected", sid=sid)


@sio.on("subscribe", namespace="/admin-stream")
async def admin_subscribe(sid, data):
    """Subscribe to specific event channels."""
    channels = data.get("channels", [])
    for channel in channels:
        sio.enter_room(sid, channel, namespace="/admin-stream")
    logger.info("admin_subscribed", sid=sid, channels=channels)


# ---------------------------------------------------------------------------
# Dashboard namespace
# ---------------------------------------------------------------------------


@sio.on("connect", namespace="/dashboard-stream")
async def dashboard_connect(sid, environ):
    logger.info("dashboard_ws_connected", sid=sid)


@sio.on("disconnect", namespace="/dashboard-stream")
async def dashboard_disconnect(sid):
    logger.info("dashboard_ws_disconnected", sid=sid)


@sio.on("subscribe_region", namespace="/dashboard-stream")
async def subscribe_region(sid, data):
    """Subscribe to updates for a specific highway or region."""
    region = data.get("region", "all")
    sio.enter_room(sid, f"region:{region}", namespace="/dashboard-stream")


# ---------------------------------------------------------------------------
# Emit helpers (called from tasks / services)
# ---------------------------------------------------------------------------


async def emit_new_detection(pothole_data: dict):
    """Broadcast a new pothole detection to all connected clients."""
    await sio.emit(
        "new_detection",
        pothole_data,
        namespace="/admin-stream",
        room="detections",
    )
    await sio.emit(
        "new_detection",
        pothole_data,
        namespace="/dashboard-stream",
    )


async def emit_complaint_update(complaint_data: dict):
    """Broadcast a complaint status update."""
    await sio.emit(
        "complaint_update",
        complaint_data,
        namespace="/admin-stream",
        room="complaints",
    )
    await sio.emit(
        "complaint_update",
        complaint_data,
        namespace="/dashboard-stream",
    )


async def emit_task_update(task_data: dict):
    """Broadcast task execution updates to admin."""
    await sio.emit(
        "task_update",
        task_data,
        namespace="/admin-stream",
        room="tasks",
    )


async def emit_alert(alert_data: dict):
    """Broadcast critical system alerts."""
    await sio.emit(
        "alert",
        alert_data,
        namespace="/admin-stream",
        room="alerts",
    )


async def emit_escalation(escalation_data: dict):
    """Broadcast escalation events."""
    await sio.emit(
        "escalation",
        escalation_data,
        namespace="/admin-stream",
        room="escalations",
    )
