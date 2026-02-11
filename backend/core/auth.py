"""Supabase session authentication dependency for FastAPI."""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.core.database import get_supabase

_bearer = HTTPBearer(auto_error=False)


def _validate_session(token: str) -> dict:
    """Validate an access token against Supabase Auth."""
    supabase = get_supabase()
    try:
        response = supabase.auth.get_user(token)
        if response and response.user:
            return {"sub": response.user.id, "email": response.user.email}
    except Exception:
        pass

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired session",
    )


async def require_auth(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Validate session from Authorization header or ?token query param (for SSE)."""
    # Try Authorization header first
    if credentials and credentials.credentials:
        return _validate_session(credentials.credentials)

    # Fall back to query param (EventSource can't set headers)
    token = request.query_params.get("token")
    if token:
        return _validate_session(token)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )
