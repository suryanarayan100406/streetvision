"""Admin system settings management."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.settings import SystemSetting, GovernmentContact, PWDOfficer
from app.models.admin import AdminAuditLog
from app.schemas.admin import SettingOut, SettingUpdate

router = APIRouter(prefix="/api/admin/settings", tags=["admin-settings"])


@router.get("/", response_model=list[SettingOut])
async def list_settings(db: AsyncSession = Depends(get_db)):
    """List all system settings."""
    result = await db.execute(
        select(SystemSetting).order_by(SystemSetting.category, SystemSetting.key)
    )
    return result.scalars().all()


@router.get("/{key}", response_model=SettingOut)
async def get_setting(key: str, db: AsyncSession = Depends(get_db)):
    """Get a specific setting by key."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")
    return setting


@router.put("/{key}", response_model=SettingOut)
async def update_setting(
    key: str,
    body: SettingUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a system setting value."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == key)
    )
    setting = result.scalar_one_or_none()
    if not setting:
        raise HTTPException(status_code=404, detail="Setting not found")

    before = {"value": setting.value}
    setting.value = body.value

    audit = AdminAuditLog(
        admin_id=1,
        action="UPDATE_SETTING",
        entity_type="system_setting",
        entity_id=setting.id,
        before_state=before,
        after_state={"value": body.value},
    )
    db.add(audit)
    await db.commit()
    await db.refresh(setting)
    return setting


# ---------------------------------------------------------------------------
# Government contacts
# ---------------------------------------------------------------------------


@router.get("/contacts/government")
async def list_government_contacts(db: AsyncSession = Depends(get_db)):
    """List government department contacts for complaint filing."""
    result = await db.execute(
        select(GovernmentContact).order_by(GovernmentContact.authority_level)
    )
    return result.scalars().all()


@router.post("/contacts/government", status_code=201)
async def create_government_contact(body: dict, db: AsyncSession = Depends(get_db)):
    """Add a government contact."""
    contact = GovernmentContact(**body)
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.get("/contacts/pwd")
async def list_pwd_officers(db: AsyncSession = Depends(get_db)):
    """List PWD officers."""
    result = await db.execute(
        select(PWDOfficer).order_by(PWDOfficer.designation)
    )
    return result.scalars().all()


@router.post("/contacts/pwd", status_code=201)
async def create_pwd_officer(body: dict, db: AsyncSession = Depends(get_db)):
    """Add a PWD officer."""
    officer = PWDOfficer(**body)
    db.add(officer)
    await db.commit()
    await db.refresh(officer)
    return officer
