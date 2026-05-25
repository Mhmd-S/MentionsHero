"""Database connection utilities for Supabase."""

from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from postgrest.exceptions import APIError
from supabase import create_client, Client

from backend.config import get_settings


@lru_cache
def get_supabase() -> Client:
    """Get cached Supabase client instance."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_key)


def get_analytical_table(table_name: str):
    """Get a PostgREST query builder for a table in the analytical schema."""
    return get_supabase().schema("analytical").table(table_name)


def is_missing_speakers_column(error: APIError) -> bool:
    """Check if error is due to missing speakers column."""
    if not error.args:
        return False
    payload = error.args[0]
    if isinstance(payload, dict):
        code = payload.get("code")
        message = str(payload.get("message", ""))
        return code in {"42703", "PGRST204"} and "speakers" in message
    if isinstance(payload, str):
        return "speakers" in payload and ("42703" in payload or "PGRST204" in payload)
    return False


def get_folder_ids_in_tree(folder_id: str, folders: list[dict[str, Any]]) -> list[str]:
    """Return folder_id plus all descendant folder IDs (in-memory from folders list)."""
    by_parent: dict[str | None, list[str]] = {}
    for f in folders:
        raw_parent = f.get("parent_id")
        pid = str(raw_parent) if raw_parent is not None else None
        if pid not in by_parent:
            by_parent[pid] = []
        by_parent[pid].append(str(f["id"]))
    result = [folder_id]
    stack = [folder_id]
    while stack:
        current = stack.pop()
        for child_id in by_parent.get(current, []):
            if child_id not in result:
                result.append(child_id)
                stack.append(child_id)
    return result


async def get_cached_analysis(cache_key: str) -> dict[str, Any] | None:
    """Get cached analysis result if not expired."""
    supabase = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    response = (
        supabase.table("analysis_cache")
        .select("result, expires_at")
        .eq("cache_key", cache_key)
        .gte("expires_at", now)
        .limit(1)
        .execute()
    )
    rows = response.data if isinstance(response.data, list) else []
    if rows:
        return rows[0].get("result")
    return None


async def set_cached_analysis(
    cache_key: str,
    result: dict[str, Any],
    expires_hours: int = 24
) -> None:
    """Cache analysis result with expiration."""
    supabase = get_supabase()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    supabase.table("analysis_cache").upsert({
        "cache_key": cache_key,
        "result": result,
        "expires_at": expires_at.isoformat()
    }).execute()
