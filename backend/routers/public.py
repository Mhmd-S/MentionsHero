"""Public-facing API routes.

Everything here is anonymous. There are no accounts, no subscription and no
paywall on the public site, so no route on this router takes a user.
"""

import logging

from fastapi import APIRouter, HTTPException, Query
from typing import Any

from backend.services import public_service
from backend.utils.transcript_filter import (
    highlight_transcript,
    calculate_speaker_frequencies,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/sitemap-urls")
async def sitemap_urls() -> list[dict[str, Any]]:
    """Return sitemap-formatted URLs for all persona pages."""
    personas = await public_service.get_public_personas()
    urls: list[dict[str, Any]] = []

    # Persona pages. Most personas have no slug yet, and the frontend links them
    # by id (`slug || id`), so fall back to the id rather than dropping the page.
    for p in personas:
        ident = p.get("slug") or p.get("id")
        if ident:
            urls.append({
                "loc": f"/personas/{ident}",
                "lastmod": p.get("updated_at"),
                "changefreq": "weekly",
                "priority": 0.8,
            })

    return urls


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


@router.get("/personas/{slug}/keyword-search")
async def persona_keyword_search(
    slug: str,
    q: str = Query(..., min_length=1, max_length=100),
) -> dict[str, Any]:
    """Search for a keyword across all of a persona's transcripts."""
    persona = await public_service.get_persona_by_slug(slug)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    if not persona.get("aliases"):
        return {
            "query": q,
            "total_matches": 0,
            "transcripts_with_matches": 0,
            "matches": [],
        }

    return await public_service.keyword_search_for_persona(
        aliases=persona["aliases"],
        query=q,
    )


@router.get("/transcripts/{transcript_id}")
async def get_transcript(
    transcript_id: str,
    search: str | None = Query(None),
) -> dict[str, Any]:
    """
    Get a public transcript by ID, in full.

    Supports search highlighting with per-speaker frequency breakdown.
    """
    transcript = await public_service.get_public_transcript(transcript_id)

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


@router.get("/transcripts/{transcript_id}/neighbors")
async def get_transcript_neighbors(
    transcript_id: str,
    persona: str = Query(..., description="Persona slug for ordering context"),
) -> dict[str, Any]:
    """Get previous and next transcripts within a persona's list."""
    return await public_service.get_transcript_neighbors(transcript_id, persona)
