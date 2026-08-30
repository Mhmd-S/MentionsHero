"""Profile lookup with self-healing.

The `on_auth_user_created` trigger (supabase/migrations/20260830_auth_rebuild_profiles.sql)
is the primary guarantee that every auth user has a profile row. This module is the
second, independent guarantee: if a row is ever missing anyway — the migration has not
been applied yet, or a user was created by some path that bypassed the trigger — the
row is created on first read instead of 500ing.

Every caller that needs a profile should go through `ensure_profile`. Reaching for
`.single()` on the profiles table directly is what made a missing row fatal to
checkout, the portal and the admin role check.
"""

import logging
from typing import Any

from backend.core.database import get_supabase

logger = logging.getLogger(__name__)

PROFILE_COLUMNS = "id, role, first_name, last_name, phone, stripe_customer_id"


def _is_duplicate_key(exc: Exception) -> bool:
    """True when a PostgREST error is a unique violation (the row already exists)."""
    if getattr(exc, "code", None) == "23505":
        return True
    text = str(exc).lower()
    return "23505" in text or "duplicate key" in text


def get_profile(user_id: str) -> dict[str, Any] | None:
    """Return the profile row for a user, or None when it does not exist."""
    supabase = get_supabase()
    result = (
        supabase.table("profiles")
        .select(PROFILE_COLUMNS)
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    # maybe_single() returns None (not an object with .data) on zero rows in some
    # postgrest-py versions, so guard on the response itself and not just .data.
    return getattr(result, "data", None) if result else None


def ensure_profile(user_id: str, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return the user's profile row, creating it if it is missing.

    `role` is only ever written on creation. It must never be part of an update:
    rewriting it on every call would silently demote an admin to 'client'.
    """
    existing = get_profile(user_id)
    if existing:
        return existing

    supabase = get_supabase()
    row = {"id": user_id, "role": "client", **(defaults or {})}

    try:
        supabase.table("profiles").insert(row).execute()
        logger.info("Created missing profile row for %s", user_id)
    except Exception as exc:
        if not _is_duplicate_key(exc):
            raise
        # Raced with the trigger or a concurrent request — the row exists now.

    profile = get_profile(user_id)
    if profile is None:
        # Insert reported success but the row is not readable: treat as a real fault
        # rather than handing callers a half-built dict.
        raise RuntimeError(f"Profile for {user_id} could not be created or read")
    return profile


def get_role(user_id: str) -> str | None:
    """Return the user's role, self-healing a missing profile row."""
    try:
        return ensure_profile(user_id).get("role")
    except Exception:
        logger.exception("Role lookup failed for %s", user_id)
        return None


def update_profile(user_id: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Update editable profile fields, creating the row first if needed.

    `role` and `stripe_customer_id` are stripped: neither is user-editable, and
    letting `role` through would be a privilege-escalation hole.
    """
    editable = {
        key: value
        for key, value in fields.items()
        if key in {"first_name", "last_name", "phone"}
    }

    ensure_profile(user_id)

    if not editable:
        return ensure_profile(user_id)

    supabase = get_supabase()
    result = (
        supabase.table("profiles")
        .update(editable)
        .eq("id", user_id)
        .execute()
    )
    rows = result.data or []
    return rows[0] if rows else ensure_profile(user_id)


def get_stripe_customer_id(user_id: str) -> str | None:
    """Return the user's Stripe customer id, or None if they have no customer yet."""
    return ensure_profile(user_id).get("stripe_customer_id")


def set_stripe_customer_id(user_id: str, customer_id: str) -> None:
    """Persist a newly created Stripe customer id onto the profile."""
    ensure_profile(user_id)
    get_supabase().table("profiles").update(
        {"stripe_customer_id": customer_id}
    ).eq("id", user_id).execute()
