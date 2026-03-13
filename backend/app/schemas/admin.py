"""Admin panel schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AdminLogin(BaseModel):
    username: str
    password: str


class AdminTokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AdminUserCreate(BaseModel):
    username: str
    role: str = "viewer"
    password: str


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    role: str
    last_login: datetime | None = None
    is_active: bool
    created_at: datetime


class AdminAuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    admin_id: int | None = None
    action: str
    entity_type: str | None = None
    entity_id: int | None = None
    before_state: dict | None = None
    after_state: dict | None = None
    created_at: datetime


class SystemOverview(BaseModel):
    total_potholes: int
    active_potholes: int
    critical_potholes: int
    new_last_24h: int
    total_complaints: int
    open_complaints: int
    critically_overdue: int
    active_satellite_jobs: int
    active_drone_missions: int
    active_cctv_cameras: int


class SchedulerTaskOut(BaseModel):
    task_name: str
    description: str | None = None
    schedule: str | None = None
    next_run: datetime | None = None
    last_run: datetime | None = None
    last_status: str | None = None
    last_duration_s: float | None = None
    enabled: bool = True


class SchedulerTaskUpdate(BaseModel):
    schedule: str | None = None
    enabled: bool | None = None


class SettingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    key: str
    value: str | None = None
    category: str | None = None
    description: str | None = None


class SettingUpdate(BaseModel):
    value: str
