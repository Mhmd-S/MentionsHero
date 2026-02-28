"""Transcript management API routes."""

from fastapi import APIRouter, HTTPException, Query
from typing import Any

from backend.models.transcript import Transcript, TranscriptUpdate, TranscriptWithHighlights
from backend.services import transcript_service
from backend.utils.transcript_filter import (
    highlight_transcript,
    extract_speakers,
    calculate_speaker_frequencies,
)

router = APIRouter(prefix="/api/transcripts", tags=["transcripts"])


@router.get("")
async def list_transcripts() -> list[dict[str, Any]]:
    """List all transcripts."""
    transcripts = await transcript_service.get_all_transcripts()
    return transcripts


@router.get("/{transcript_id}")
async def get_transcript(
    transcript_id: str,
    search: str | None = Query(None),
    speakers: str | None = Query(None)
) -> dict[str, Any]:
    """
    Get a single transcript by ID.

    Supports optional search highlighting and speaker filtering.
    """
    transcript = await transcript_service.get_transcript_by_id(transcript_id)

    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    # Parse speakers from comma-separated string
    speaker_list: list[str] | None = None
    if speakers:
        speaker_list = [s.strip() for s in speakers.split(",") if s.strip()]

    # Extract available speakers
    available_speakers = extract_speakers(transcript.get("transcript", ""))

    # Apply highlighting if search or speakers provided
    if search or speaker_list:
        result = highlight_transcript(
            transcript.get("transcript", ""),
            search_string=search,
            speakers=speaker_list
        )

        # Calculate speaker frequencies for search term
        speaker_frequencies = []
        if search:
            speaker_frequencies = calculate_speaker_frequencies(
                transcript.get("transcript", ""),
                search
            )

        return {
            **transcript,
            "transcript": result["highlightedTranscript"],
            "matchCount": result["matchCount"],
            "speakerFrequencies": speaker_frequencies,
            "availableSpeakers": available_speakers,
            "hasHighlights": True
        }

    return {
        **transcript,
        "availableSpeakers": available_speakers
    }


@router.patch("/{transcript_id}")
async def update_transcript(
    transcript_id: str,
    request: TranscriptUpdate
) -> dict[str, Any]:
    """Update a transcript."""
    if request.name is not None and not request.name.strip():
        raise HTTPException(status_code=400, detail="Transcript name cannot be empty")

    # Check if there's anything to update
    has_update = any(
        v is not None for v in [request.name, request.folder_id, request.is_public, request.is_premium]
    )
    if not has_update:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    transcript = await transcript_service.update_transcript(
        transcript_id=transcript_id,
        name=request.name,
        folder_id=request.folder_id,
        is_public=request.is_public,
        is_premium=request.is_premium,
    )

    if not transcript:
        raise HTTPException(status_code=500, detail="Failed to update transcript")

    return transcript


@router.delete("/{transcript_id}")
async def delete_transcript(transcript_id: str) -> dict:
    """Delete a transcript."""
    await transcript_service.delete_transcript(transcript_id)
    return {"success": True}
