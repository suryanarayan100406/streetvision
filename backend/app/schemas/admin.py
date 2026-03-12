"""Admin panel schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class AdminLogin(BaseModel):
    email: EmailStr
    password: str


class AdminTokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AdminUserCreate(BaseModel):
    email: EmailStr
    name: str
    role: str = "ADMIN"
    password: str


class AdminUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    name: str | None = None
    role: str
    last_login: datetime | None = None
    status: str
    created_at: datetime


class AdminAuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    administrator_id: int | None = None
    action_type: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    change_summary: str | None = None
    before_state: dict | None = None
    after_state: dict | None = None
    performed_at: datetime
    ip_address: str | None = None


class SystemHealthItem(BaseModel):
    component: str
    status: str  # HEALTHY | DEGRADED | ERROR | INACTIVE
    last_event: datetime | None = None
    last_error: str | None = None


class SystemOverview(BaseModel):
    total_potholes: int
    open_complaints: dict[str, int]  # escalation_level -> count
    complaints_today: int
    repairs_this_month: int
    health: list[SystemHealthItem]


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
    value_type: str | None = None
    description: str | None = None


class SettingUpdate(BaseModel):
    value: str
