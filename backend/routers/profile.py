"""User profile API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from supabase_auth.errors import AuthApiError

from backend.core.auth import require_user_auth
from backend.core.database import get_supabase

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


class ProfileInit(BaseModel):
    user_id: str
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None


@router.post("/init")
async def init_profile(body: ProfileInit) -> dict:
    """Initialize profile during signup (no auth required — uses service key).

    Validates that the user_id exists in auth.users before upserting.
    """
    supabase = get_supabase()

    # Verify user exists in Supabase Auth. Only a 4xx from the Auth API means the
    # user_id is actually bad — connection failures, bad service keys and Supabase
    # outages must not be reported back to the user as invalid input.
    try:
        supabase.auth.admin.get_user_by_id(body.user_id)
    except AuthApiError as exc:
        status = getattr(exc, "status", None) or 400
        if 400 <= status < 500:
            logger.warning("Profile init rejected for %s: %s", body.user_id, exc)
            raise HTTPException(status_code=400, detail="Invalid user") from exc
        logger.exception("Auth lookup failed during profile init for %s", body.user_id)
        raise HTTPException(status_code=503, detail="Auth service unavailable") from exc
    except Exception as exc:
        logger.exception("Auth lookup failed during profile init for %s", body.user_id)
        raise HTTPException(status_code=503, detail="Auth service unavailable") from exc

    try:
        supabase.table("profiles").upsert(
            {
                "id": body.user_id,
                "role": "client",
                "first_name": body.first_name,
                "last_name": body.last_name,
                "phone": body.phone,
            },
            on_conflict="id",
        ).execute()
    except Exception as exc:
        logger.exception("Profile upsert failed for %s", body.user_id)
        raise HTTPException(status_code=503, detail="Could not create profile") from exc

    return {"status": "ok"}


@router.get("")
async def get_profile(user: dict = Depends(require_user_auth)) -> ProfileResponse:
    """Get the current user's profile."""
    supabase = get_supabase()
    result = (
        supabase.table("profiles")
        .select("first_name, last_name, phone, role")
        .eq("id", user["sub"])
        .single()
        .execute()
    )
    data = result.data or {}
    return ProfileResponse(
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        phone=data.get("phone"),
        email=user.get("email"),
        role=data.get("role"),
    )


@router.put("")
async def update_profile(
    body: ProfileUpdate,
    user: dict = Depends(require_user_auth),
) -> ProfileResponse:
    """Update the current user's profile."""
    supabase = get_supabase()

    update_data = {
        "first_name": body.first_name,
        "last_name": body.last_name,
        "phone": body.phone,
    }

    result = (
        supabase.table("profiles")
        .update(update_data)
        .eq("id", user["sub"])
        .execute()
    )

    if not result.data:
        raise HTTPException(status_code=404, detail="Profile not found")

    row = result.data[0]
    return ProfileResponse(
        first_name=row.get("first_name"),
        last_name=row.get("last_name"),
        phone=row.get("phone"),
        email=user.get("email"),
    )
