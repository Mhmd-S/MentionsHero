"""Auth API routes."""

from fastapi import APIRouter, Depends

from backend.core.auth import require_user_auth
from backend.core.database import get_supabase

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me")
async def get_me(user: dict = Depends(require_user_auth)) -> dict:
    """Return the current user's role for the frontend role-gating UI."""
    supabase = get_supabase()
    result = (
        supabase.table("profiles")
        .select("role")
        .eq("id", user["sub"])
        .single()
        .execute()
    )
    role = (result.data or {}).get("role")
    return {"role": role}
