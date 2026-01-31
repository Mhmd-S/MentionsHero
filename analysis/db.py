"""Database connection utilities for Supabase."""

import os
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


@lru_cache()
def get_supabase() -> Client:
    """Get cached Supabase client instance."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

    return create_client(url, key)


async def get_all_transcripts(folder_id: str | None = None) -> list[dict[str, Any]]:
    """Fetch transcripts from the database, optionally filtered by folder."""
    supabase = get_supabase()
    query = supabase.table("transcripts").select("id, transcript, name, created_at, folder_id")

    if folder_id:
        query = query.eq("folder_id", folder_id)

    response = query.execute()
    return response.data or []


async def get_folders() -> list[dict[str, Any]]:
    """Fetch all folders from the database."""
    supabase = get_supabase()
    response = supabase.table("folders").select("id, name, parent_id").execute()
    return response.data or []


def _get_folder_ids_in_tree(folder_id: str, folders: list[dict[str, Any]]) -> list[str]:
    """Return folder_id plus all descendant folder IDs (in-memory from folders list)."""
    by_parent: dict[str | None, list[str]] = {}
    for f in folders:
        pid = f.get("parent_id")
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


async def get_all_transcripts_in_folder_tree(folder_id: str) -> list[dict[str, Any]]:
    """Fetch transcripts from the given folder and all its descendant folders."""
    folders = await get_folders()
    folder_ids = _get_folder_ids_in_tree(folder_id, folders)
    supabase = get_supabase()
    response = supabase.table("transcripts").select("id, transcript, name, created_at, folder_id").in_("folder_id", folder_ids).execute()
    return response.data or []


async def get_transcript_by_id(transcript_id: str) -> dict[str, Any] | None:
    """Fetch a single transcript by ID."""
    supabase = get_supabase()
    response = supabase.table("transcripts").select("*").eq("id", transcript_id).single().execute()
    return response.data


async def get_cached_analysis(cache_key: str) -> dict[str, Any] | None:
    """Get cached analysis result if not expired."""
    supabase = get_supabase()
    response = (
        supabase.table("analysis_cache")
        .select("result, expires_at")
        .eq("cache_key", cache_key)
        .gte("expires_at", "now()")
        .single()
        .execute()
    )
    if response.data:
        return response.data.get("result")
    return None


async def set_cached_analysis(
    cache_key: str,
    result: dict[str, Any],
    expires_hours: int = 24
) -> None:
    """Cache analysis result with expiration."""
    supabase = get_supabase()
    supabase.table("analysis_cache").upsert({
        "cache_key": cache_key,
        "result": result,
        "expires_at": f"now() + interval '{expires_hours} hours'"
    }).execute()
