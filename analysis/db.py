"""Database connection utilities for Supabase."""

import os
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from postgrest.exceptions import APIError
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


def _is_missing_speakers_column(error: APIError) -> bool:
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


def _select_transcripts(
    supabase: Client,
    *,
    folder_id: str | None = None,
    folder_ids: list[str] | None = None
) -> list[dict[str, Any]]:
    try:
        query = supabase.table("transcripts").select("id, transcript, name, created_at, folder_id, speakers")
        if folder_id:
            query = query.eq("folder_id", folder_id)
        if folder_ids:
            query = query.in_("folder_id", folder_ids)
        response = query.execute()
        return response.data or []
    except APIError as exc:
        if not _is_missing_speakers_column(exc):
            raise
        query = supabase.table("transcripts").select("id, transcript, name, created_at, folder_id")
        if folder_id:
            query = query.eq("folder_id", folder_id)
        if folder_ids:
            query = query.in_("folder_id", folder_ids)
        response = query.execute()
        return response.data or []


async def get_all_transcripts(folder_id: str | None = None) -> list[dict[str, Any]]:
    """Fetch transcripts from the database, optionally filtered by folder."""
    supabase = get_supabase()
    return _select_transcripts(supabase, folder_id=folder_id)


async def get_folders() -> list[dict[str, Any]]:
    """Fetch all folders from the database."""
    supabase = get_supabase()
    response = supabase.table("folders").select("id, name, parent_id").execute()
    return response.data or []


def _get_folder_ids_in_tree(folder_id: str, folders: list[dict[str, Any]]) -> list[str]:
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


async def get_all_transcripts_in_folder_tree(folder_id: str) -> list[dict[str, Any]]:
    """Fetch transcripts from the given folder and all its descendant folders."""
    folders = await get_folders()
    folder_ids = _get_folder_ids_in_tree(folder_id, folders)
    supabase = get_supabase()
    return _select_transcripts(supabase, folder_ids=folder_ids)


async def update_transcript_speakers(transcript_id: str, speakers: list[str]) -> None:
    """Save extracted speaker names for a transcript."""
    supabase = get_supabase()
    try:
        supabase.table("transcripts").update({"speakers": speakers}).eq("id", transcript_id).execute()
    except APIError as exc:
        if _is_missing_speakers_column(exc):
            return
        raise


async def get_transcript_by_id(transcript_id: str) -> dict[str, Any] | None:
    """Fetch a single transcript by ID."""
    supabase = get_supabase()
    response = supabase.table("transcripts").select("*").eq("id", transcript_id).single().execute()
    return response.data


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
