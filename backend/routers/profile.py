"""User profile API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.core.auth import require_user_auth
from backend.core.database import get_supabase

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

    # Verify user exists in Supabase Auth
    try:
        supabase.auth.admin.get_user_by_id(body.user_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid user")

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
