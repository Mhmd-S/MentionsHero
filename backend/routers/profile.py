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


class ProfileUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


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

    There is no longer a public POST /api/profile/init: profile rows are created by
    the `on_auth_user_created` database trigger, with `ensure_profile` as a fallback.
    The old endpoint was unauthenticated by necessity (it ran before the user had a
    session) and depended on the browser staying alive through the signup redirect,
    which is exactly why accounts ended up with no profile row.
    """
    try:
        row = profile_service.ensure_profile(user["sub"])
    except Exception as exc:
        logger.exception("Profile lookup failed for %s", user["sub"])
        raise HTTPException(status_code=503, detail="Could not load profile") from exc

    return _to_response(row, user.get("email"))


@router.put("")
async def update_profile(
    body: ProfileUpdate,
    user: dict = Depends(require_user_auth),
) -> ProfileResponse:
    """Update the current user's editable profile fields."""
    try:
        row = profile_service.update_profile(user["sub"], body.model_dump())
    except Exception as exc:
        logger.exception("Profile update failed for %s", user["sub"])
        raise HTTPException(status_code=503, detail="Could not save profile") from exc

    return _to_response(row, user.get("email"))
