"""Public-facing API routes (no admin auth required)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any

from backend.core.auth import optional_auth
from backend.services import public_service
from backend.utils.transcript_filter import (
    highlight_transcript,
    calculate_speaker_frequencies,
)

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/personas")
async def list_personas() -> list[dict[str, Any]]:
    """List all personas for public browsing."""
    return await public_service.get_public_personas()


@router.get("/personas/{slug}")
async def get_persona(slug: str) -> dict[str, Any]:
    """Get a single persona by slug."""
    persona = await public_service.get_persona_by_slug(slug)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return persona


@router.get("/personas/{slug}/transcripts")
async def get_persona_transcripts(
    slug: str,
    folder_id: str | None = Query(None),
    search: str | None = Query(None),
    sort_by: str = Query("date", pattern="^(date|name)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """List public transcripts for a persona (alias-based matching)."""
    persona = await public_service.get_persona_by_slug(slug)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    if not persona.get("aliases"):
        return {
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
        }

    return await public_service.get_public_transcripts_for_persona(
        aliases=persona["aliases"],
        folder_id=folder_id,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
        page=page,
        page_size=page_size,
    )


@router.get("/transcripts/{transcript_id}")
async def get_transcript(
    transcript_id: str,
    search: str | None = Query(None),
    user: dict | None = Depends(optional_auth),
) -> dict[str, Any]:
    """
    Get a public transcript by ID.

    If the transcript is premium and the user is not subscribed,
    returns a truncated preview with is_locked=True.

    Supports search highlighting with per-speaker frequency breakdown.
    """
    user_id = user["sub"] if user else None
    transcript = await public_service.get_public_transcript(transcript_id, user_id)

    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    if search:
        result = highlight_transcript(
            transcript.get("transcript", ""),
            search_string=search,
        )
        speaker_frequencies = calculate_speaker_frequencies(
            transcript.get("transcript", ""),
            search,
        )

        return {
            **transcript,
            "transcript": result["highlightedTranscript"],
            "matchCount": result["matchCount"],
            "speakerFrequencies": speaker_frequencies,
            "hasHighlights": True,
        }

    return transcript
