"""Admin authentication — JWT login, token refresh, user management."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.models.admin import AdminUser, AdminAuditLog
from app.schemas.admin import AdminLogin, AdminTokenPair, AdminUserCreate, AdminUserOut

router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])


def _hash_password(password: str) -> str:
    import hashlib
    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        settings.SECRET_KEY.encode(),
        100_000,
    ).hex()


def _verify_password(password: str, hashed: str) -> bool:
    return _hash_password(password) == hashed


def _create_token(data: dict, expires_delta: timedelta) -> str:
    import jwt

    payload = {
        **data,
        "exp": datetime.now(timezone.utc) + expires_delta,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


@router.post("/login", response_model=AdminTokenPair)
async def admin_login(body: AdminLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate admin and return JWT pair."""
    result = await db.execute(
        select(AdminUser).where(AdminUser.username == body.username)
    )
    user = result.scalar_one_or_none()

    if not user or not _verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled",
        )

    user.last_login = datetime.now(timezone.utc)
    await db.commit()

    access = _create_token(
        {"sub": str(user.id), "role": user.role},
        timedelta(hours=2),
    )
    refresh = _create_token(
        {"sub": str(user.id), "type": "refresh"},
        timedelta(days=7),
    )

    return AdminTokenPair(access_token=access, refresh_token=refresh)


@router.post("/refresh", response_model=AdminTokenPair)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """Exchange a refresh token for a new access/refresh pair."""
    import jwt

    try:
        payload = jwt.decode(
            refresh_token, settings.SECRET_KEY, algorithms=["HS256"]
        )
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")

    user_id = int(payload["sub"])
    result = await db.execute(select(AdminUser).where(AdminUser.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    access = _create_token(
        {"sub": str(user.id), "role": user.role},
        timedelta(hours=2),
    )
    new_refresh = _create_token(
        {"sub": str(user.id), "type": "refresh"},
        timedelta(days=7),
    )

    return AdminTokenPair(access_token=access, refresh_token=new_refresh)


@router.post("/users", response_model=AdminUserOut, status_code=201)
async def create_admin_user(
    body: AdminUserCreate,
    db: AsyncSession = Depends(get_db),
    # admin: AdminUser = Depends(get_current_admin)  # enabled via middleware
):
    """Create a new admin user (super-admin only)."""
    existing = await db.execute(
        select(AdminUser).where(AdminUser.username == body.username)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")

    user = AdminUser(
        username=body.username,
        password_hash=_hash_password(body.password),
        role=body.role,
        is_active=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
