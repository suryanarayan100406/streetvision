"""JWT authentication middleware for admin routes."""

from __future__ import annotations

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

security = HTTPBearer()

ADMIN_PREFIX = "/api/admin"
PUBLIC_ADMIN_PATHS = {"/api/admin/auth/login", "/api/admin/auth/refresh"}


class JWTAuthMiddleware(BaseHTTPMiddleware):
    """Protect all /api/admin/* routes with JWT verification."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip non-admin routes
        if not path.startswith(ADMIN_PREFIX):
            return await call_next(request)

        # Skip public auth endpoints
        if path in PUBLIC_ADMIN_PATHS:
            return await call_next(request)

        # Verify JWT
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return self._unauthorized("Missing authorization header")

        token = auth_header.split(" ", 1)[1]
        payload = self._verify_token(token)
        if payload is None:
            return self._unauthorized("Invalid or expired token")

        # Attach user info to request state
        request.state.admin_id = int(payload["sub"])
        request.state.admin_role = payload.get("role", "viewer")

        return await call_next(request)

    @staticmethod
    def _verify_token(token: str) -> dict | None:
        import jwt

        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=["HS256"],
            )
            # Reject refresh tokens used as access tokens
            if payload.get("type") == "refresh":
                return None
            return payload
        except jwt.InvalidTokenError:
            return None

    @staticmethod
    def _unauthorized(detail: str):
        from starlette.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": detail},
        )


async def get_current_admin(request: Request) -> dict:
    """Dependency to get current admin user from request state."""
    admin_id = getattr(request.state, "admin_id", None)
    if admin_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return {"id": admin_id, "role": request.state.admin_role}


async def require_super_admin(request: Request) -> dict:
    """Dependency that requires super_admin role."""
    admin = await get_current_admin(request)
    if admin["role"] != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return admin
