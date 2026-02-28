"""Transcript service for database operations."""

from typing import Any

from postgrest.exceptions import APIError

from backend.core.database import get_supabase, is_missing_speakers_column, get_folder_ids_in_tree
from backend.services import folder_service


def _select_transcripts(
    folder_id: str | None = None,
    folder_ids: list[str] | None = None
) -> list[dict[str, Any]]:
    """Select transcripts with optional folder filtering."""
    supabase = get_supabase()
    try:
        query = supabase.table("transcripts").select(
            "id, transcript, name, created_at, folder_id, speakers, youtube_url, upload_date"
        )
        if folder_id:
            query = query.eq("folder_id", folder_id)
        if folder_ids:
            query = query.in_("folder_id", folder_ids)
        response = query.execute()
        return response.data or []
    except APIError as exc:
        if not is_missing_speakers_column(exc):
            raise
        # Fallback without speakers column
        query = supabase.table("transcripts").select(
            "id, transcript, name, created_at, folder_id, youtube_url, upload_date"
        )
        if folder_id:
            query = query.eq("folder_id", folder_id)
        if folder_ids:
            query = query.in_("folder_id", folder_ids)
        response = query.execute()
        return response.data or []


async def get_all_transcripts(folder_id: str | None = None) -> list[dict[str, Any]]:
    """Fetch all transcripts, optionally filtered by folder."""
    supabase = get_supabase()
    query = supabase.table("transcripts").select("*").order("created_at", desc=True)

    if folder_id:
        query = query.eq("folder_id", folder_id)

    response = query.execute()
    return response.data or []


async def get_transcripts_in_folder_tree(folder_id: str) -> list[dict[str, Any]]:
    """Fetch transcripts from the given folder and all its descendant folders."""
    folders = await folder_service.get_all_folders()
    folder_ids = get_folder_ids_in_tree(folder_id, folders)
    return _select_transcripts(folder_ids=folder_ids)


async def get_transcript_by_id(transcript_id: str) -> dict[str, Any] | None:
    """Fetch a single transcript by ID."""
    supabase = get_supabase()
    response = (
        supabase.table("transcripts")
        .select("*")
        .eq("id", transcript_id)
        .single()
        .execute()
    )
    return response.data


async def get_transcripts_by_ids(transcript_ids: list[str]) -> list[dict[str, Any]]:
    """Fetch full transcript rows (including transcript text) for the given IDs."""
    if not transcript_ids:
        return []
    supabase = get_supabase()
    try:
        response = (
            supabase.table("transcripts")
            .select("id, transcript, name, created_at, upload_date, folder_id, youtube_url")
            .in_("id", transcript_ids)
            .execute()
        )
        return response.data or []
    except APIError as exc:
        if not is_missing_speakers_column(exc):
            raise
        response = (
            supabase.table("transcripts")
            .select("id, transcript, name, created_at, upload_date, folder_id, youtube_url")
            .in_("id", transcript_ids)
            .execute()
        )
        return response.data or []


async def create_transcript(
    youtube_url: str,
    transcript: str,
    folder_id: str | None = None
) -> dict[str, Any]:
    """Create a new transcript."""
    supabase = get_supabase()
    response = (
        supabase.table("transcripts")
        .insert({
            "youtube_url": youtube_url,
            "transcript": transcript,
            "folder_id": folder_id
        })
        .execute()
    )
    return response.data[0] if response.data else None


async def update_transcript(
    transcript_id: str,
    name: str | None = None,
    folder_id: str | None = None,
    is_public: bool | None = None,
    is_premium: bool | None = None,
) -> dict[str, Any] | None:
    """Update a transcript."""
    supabase = get_supabase()

    updates: dict[str, Any] = {}

    if name is not None:
        updates["name"] = name.strip()

    if folder_id is not None:
        updates["folder_id"] = folder_id

    if is_public is not None:
        updates["is_public"] = is_public

    if is_premium is not None:
        updates["is_premium"] = is_premium

    if not updates:
        return None

    response = (
        supabase.table("transcripts")
        .update(updates)
        .eq("id", transcript_id)
        .execute()
    )
    return response.data[0] if response.data else None


async def delete_transcript(transcript_id: str) -> bool:
    """Delete a transcript."""
    supabase = get_supabase()
    supabase.table("transcripts").delete().eq("id", transcript_id).execute()
    return True


async def update_transcript_speakers(transcript_id: str, speakers: list[str]) -> None:
    """Save extracted speaker names for a transcript."""
    supabase = get_supabase()
    try:
        supabase.table("transcripts").update({
            "speakers": speakers
        }).eq("id", transcript_id).execute()
    except APIError as exc:
        if is_missing_speakers_column(exc):
            return
        raise
