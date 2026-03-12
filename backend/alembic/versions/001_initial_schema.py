"""Initial schema with PostGIS.

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable PostGIS
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ---- potholes ----
    op.create_table(
        "potholes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("geom", geoalchemy2.Geometry("POINT", srid=4326)),
        sa.Column("severity", sa.String(20)),
        sa.Column("confidence_score", sa.Float(), default=0.0),
        sa.Column("risk_score", sa.Float(), default=0.0),
        sa.Column("status", sa.String(30), default="Detected"),
        sa.Column("nh_number", sa.String(20)),
        sa.Column("chainage_km", sa.Float()),
        sa.Column("district", sa.String(100)),
        sa.Column("address", sa.Text()),
        sa.Column("estimated_area_m2", sa.Float()),
        sa.Column("estimated_depth_cm", sa.Float()),
        sa.Column("estimated_diameter_m", sa.Float()),
        sa.Column("image_path", sa.Text()),
        sa.Column("mask_path", sa.Text()),
        sa.Column("rain_flag", sa.Boolean(), default=False),
        sa.Column("thermal_stress_flag", sa.Boolean(), default=False),
        sa.Column("moisture_flag", sa.Boolean(), default=False),
        sa.Column("near_junction", sa.Boolean(), default=False),
        sa.Column("on_curve", sa.Boolean(), default=False),
        sa.Column("on_blind_spot", sa.Boolean(), default=False),
        sa.Column("aadt", sa.Integer(), default=0),
        sa.Column("last_repair_status", sa.String(30)),
        sa.Column("last_scan_date", sa.DateTime(timezone=True)),
        sa.Column("critically_overdue", sa.Boolean(), default=False),
        sa.Column("merged_into_id", sa.Integer()),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index("ix_potholes_geom", "potholes", ["geom"], postgresql_using="gist")
    op.create_index("ix_potholes_nh", "potholes", ["nh_number"])
    op.create_index("ix_potholes_severity", "potholes", ["severity"])
    op.create_index("ix_potholes_risk", "potholes", ["risk_score"])

    # ---- complaints ----
    op.create_table(
        "complaints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pothole_id", sa.Integer(), sa.ForeignKey("potholes.id"), nullable=False),
        sa.Column("portal_ref", sa.String(100)),
        sa.Column("portal_status", sa.String(50)),
        sa.Column("complaint_text", sa.Text()),
        sa.Column("filed_at", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("escalation_level", sa.Integer(), default=0),
        sa.Column("escalated_at", sa.DateTime(timezone=True)),
        sa.Column("escalation_target", sa.String(200)),
        sa.Column("filing_proof_path", sa.Text()),
        sa.Column("filing_method", sa.String(20)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_complaints_pothole", "complaints", ["pothole_id"])

    # ---- scans ----
    op.create_table(
        "scans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pothole_id", sa.Integer(), sa.ForeignKey("potholes.id"), nullable=False),
        sa.Column("scan_date", sa.Date()),
        sa.Column("before_image_path", sa.Text()),
        sa.Column("after_image_path", sa.Text()),
        sa.Column("ssim_score", sa.Float()),
        sa.Column("siamese_score", sa.Float()),
        sa.Column("repair_status", sa.String(30)),
        sa.Column("scan_source", sa.String(50)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- source_reports ----
    op.create_table(
        "source_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pothole_id", sa.Integer(), sa.ForeignKey("potholes.id")),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("raw_payload", sa.JSON()),
        sa.Column("image_url", sa.Text()),
        sa.Column("captured_at", sa.DateTime(timezone=True)),
        sa.Column("confidence_boost", sa.Float(), default=0.0),
        sa.Column("processed", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- cctv_nodes ----
    op.create_table(
        "cctv_nodes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("rtsp_url", sa.Text(), nullable=False),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("nh_number", sa.String(20)),
        sa.Column("chainage_km", sa.Float()),
        sa.Column("perspective_matrix", sa.JSON()),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("last_frame_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- drone_missions ----
    op.create_table(
        "drone_missions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mission_name", sa.String(200)),
        sa.Column("operator", sa.String(200)),
        sa.Column("flight_date", sa.Date()),
        sa.Column("area_bbox", sa.JSON()),
        sa.Column("image_count", sa.Integer()),
        sa.Column("gsd_cm", sa.Float()),
        sa.Column("processing_status", sa.String(30), default="PENDING"),
        sa.Column("odm_task_id", sa.String(100)),
        sa.Column("orthophoto_path", sa.Text()),
        sa.Column("dsm_path", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    # ---- road_segments ----
    op.create_table(
        "road_segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nh_number", sa.String(20), nullable=False),
        sa.Column("chainage_km", sa.Float()),
        sa.Column("geom", geoalchemy2.Geometry("LINESTRING", srid=4326)),
        sa.Column("aadt", sa.Integer(), default=0),
        sa.Column("is_curve", sa.Boolean(), default=False),
        sa.Column("is_blind_spot", sa.Boolean(), default=False),
        sa.Column("is_junction", sa.Boolean(), default=False),
        sa.Column("thermal_stress_zone", sa.Boolean(), default=False),
        sa.Column("surface_type", sa.String(50)),
    )

    # ---- road_accidents ----
    op.create_table(
        "road_accidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("state", sa.String(100)),
        sa.Column("district", sa.String(100)),
        sa.Column("year", sa.Integer()),
        sa.Column("total_accidents", sa.Integer()),
        sa.Column("persons_killed", sa.Integer()),
        sa.Column("persons_injured", sa.Integer()),
        sa.Column("raw_payload", sa.JSON()),
    )

    # ---- weather_cache ----
    op.create_table(
        "weather_cache",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("source", sa.String(50)),
        sa.Column("temperature_c", sa.Float()),
        sa.Column("humidity_pct", sa.Float()),
        sa.Column("precipitation_mm", sa.Float()),
        sa.Column("wind_speed_kmh", sa.Float()),
        sa.Column("rain_last_24h", sa.Boolean(), default=False),
        sa.Column("raw_response", sa.JSON()),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- satellite tables ----
    op.create_table(
        "satellite_sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), unique=True),
        sa.Column("source_type", sa.String(20)),
        sa.Column("priority", sa.Integer(), default=50),
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column("credentials", sa.JSON()),
        sa.Column("last_successful_at", sa.DateTime(timezone=True)),
        sa.Column("error_count", sa.Integer(), default=0),
    )

    op.create_table(
        "satellite_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("satellite_sources.id")),
        sa.Column("status", sa.String(30), default="PENDING"),
        sa.Column("bbox", sa.JSON()),
        sa.Column("tiles_total", sa.Integer(), default=0),
        sa.Column("tiles_processed", sa.Integer(), default=0),
        sa.Column("detections_count", sa.Integer(), default=0),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "satellite_selection_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("satellite_jobs.id")),
        sa.Column("candidates", sa.JSON()),
        sa.Column("selected_source", sa.String(100)),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "satellite_download_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("satellite_jobs.id")),
        sa.Column("source_name", sa.String(100)),
        sa.Column("product_id", sa.String(200)),
        sa.Column("file_path", sa.Text()),
        sa.Column("file_size_mb", sa.Float()),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- admin tables ----
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(100), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.String(30), default="viewer"),
        sa.Column("is_active", sa.Boolean(), default=True),
        sa.Column("last_login", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "admin_audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("admin_id", sa.Integer(), sa.ForeignKey("admin_users.id")),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", sa.Integer()),
        sa.Column("before_state", sa.JSON()),
        sa.Column("after_state", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "gemini_audit",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pothole_id", sa.Integer()),
        sa.Column("model_used", sa.String(50)),
        sa.Column("input_tokens", sa.Integer()),
        sa.Column("output_tokens", sa.Integer()),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("success", sa.Boolean(), default=True),
        sa.Column("error_message", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- task_history ----
    op.create_table(
        "task_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_name", sa.String(200)),
        sa.Column("task_id", sa.String(100)),
        sa.Column("status", sa.String(30)),
        sa.Column("result", sa.JSON()),
        sa.Column("duration_seconds", sa.Float()),
        sa.Column("completed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ---- system settings ----
    op.create_table(
        "system_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(100), unique=True, nullable=False),
        sa.Column("value", sa.Text()),
        sa.Column("category", sa.String(50)),
        sa.Column("description", sa.Text()),
    )

    op.create_table(
        "government_contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("authority_level", sa.Integer()),
        sa.Column("department", sa.String(200)),
        sa.Column("designation", sa.String(200)),
        sa.Column("name", sa.String(200)),
        sa.Column("email", sa.String(200)),
        sa.Column("phone", sa.String(20)),
        sa.Column("district", sa.String(100)),
    )

    op.create_table(
        "pwd_officers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200)),
        sa.Column("designation", sa.String(200)),
        sa.Column("division", sa.String(200)),
        sa.Column("email", sa.String(200)),
        sa.Column("phone", sa.String(20)),
        sa.Column("nh_number", sa.String(20)),
    )

    op.create_table(
        "gamification_points",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(100), unique=True),
        sa.Column("display_name", sa.String(200)),
        sa.Column("total_points", sa.Integer(), default=0),
        sa.Column("reports_count", sa.Integer(), default=0),
        sa.Column("rank", sa.Integer()),
    )

    op.create_table(
        "model_registry",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("model_name", sa.String(100)),
        sa.Column("version", sa.String(50)),
        sa.Column("model_type", sa.String(50)),
        sa.Column("is_active", sa.Boolean(), default=False),
        sa.Column("weights_path", sa.Text()),
        sa.Column("precision", sa.Float()),
        sa.Column("recall", sa.Float()),
        sa.Column("f1_score", sa.Float()),
        sa.Column("map50", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Seed default admin
    op.execute(
        """
        INSERT INTO admin_users (username, password_hash, role, is_active)
        VALUES ('admin', 'change_me_on_first_login', 'super_admin', true)
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    tables = [
        "model_registry", "gamification_points", "pwd_officers",
        "government_contacts", "system_settings", "task_history",
        "gemini_audit", "admin_audit_log", "admin_users",
        "satellite_download_log", "satellite_selection_log",
        "satellite_jobs", "satellite_sources",
        "weather_cache", "road_accidents", "road_segments",
        "drone_missions", "cctv_nodes", "source_reports",
        "scans", "complaints", "potholes",
    ]
    for t in tables:
        op.drop_table(t)
