"""Supabase session authentication dependencies for FastAPI."""

import logging

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.database import get_supabase

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


def _validate_session(token: str) -> dict:
    """Validate an access token against Supabase Auth."""
    supabase = get_supabase()
    try:
        response = supabase.auth.get_user(token)
        if response and response.user:
            return {"sub": response.user.id, "email": response.user.email}
        logger.warning("Token validation returned no user")
    except Exception as e:
        logger.warning("Token validation failed: %s", e)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session",
    )


def _extract_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    """Extract token from Authorization header or ?token query param."""
    if credentials and credentials.credentials:
        return credentials.credentials
    return request.query_params.get("token")


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Validate session from Authorization header or ?token query param (for SSE)."""
    token = _extract_token(request, credentials)
    if token:
        return _validate_session(token)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


async def optional_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict | None:
    """Return user dict if token is present and valid, None otherwise."""
    token = _extract_token(request, credentials)
    if not token:
        return None
    try:
        return _validate_session(token)
    except HTTPException:
        return None


async def require_user_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Require any authenticated user (admin or client)."""
    return await require_auth(request, credentials)


async def require_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Require authenticated user with admin role."""
    user = await require_auth(request, credentials)

    supabase = get_supabase()
    try:
        profile = (
            supabase.table("profiles")
            .select("role")
            .eq("id", user["sub"])
            .single()
            .execute()
        )
        if profile.data and profile.data.get("role") == "admin":
            return user
    except Exception as e:
        logger.warning("Admin role check failed: %s", e)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )
