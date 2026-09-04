"""User profile API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.core.auth import require_user_auth
from backend.services import profile_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/profile", tags=["profile"])


class ProfileResponse(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    email: str | None = None
    role: str | None = None


def _to_response(row: dict, email: str | None) -> ProfileResponse:
    return ProfileResponse(
        first_name=row.get("first_name"),
        last_name=row.get("last_name"),
        phone=row.get("phone"),
        email=email,
        role=row.get("role"),
    )


@router.get("")
async def get_profile(user: dict = Depends(require_user_auth)) -> ProfileResponse:
    """Get the current user's profile, creating the row if it is missing.

    This is what the admin UI reads `role` from — it is not a JWT claim. Profile
    rows are created by the `on_auth_user_created` database trigger, with
    `ensure_profile` as a fallback for rows that predate it.
    """
    try:
        row = profile_service.ensure_profile(user["sub"])
    except Exception as exc:
        logger.exception("Profile lookup failed for %s", user["sub"])
        raise HTTPException(status_code=503, detail="Could not load profile") from exc

    return _to_response(row, user.get("email"))
