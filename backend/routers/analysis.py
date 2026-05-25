"""Analysis API routes (speaker-related only)."""

from fastapi import APIRouter, Query

from backend.services import speaker_service, transcript_service
from backend.models.analysis import SpeakersResponse

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


@router.get("/speakers")
async def list_speakers(
    folder_id: str | None = Query(None, alias="folder_id")
) -> SpeakersResponse:
    """List all speakers found across transcripts (from database)."""
    speakers = await speaker_service.get_all_speakers(folder_id)
    return SpeakersResponse(speakers=speakers)


@router.get("/speakers/search")
async def search_speakers_endpoint(
    q: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200)
) -> SpeakersResponse:
    """Search speakers by name."""
    speakers = await speaker_service.search_speakers(q, limit)
    return SpeakersResponse(speakers=speakers)


@router.post("/speakers/migrate")
async def migrate_speakers(
    folder_id: str | None = Query(
        None,
        description="Optional: migrate only transcripts in this folder tree"
    )
) -> dict[str, int]:
    """One-time migration: extract and save speakers from existing transcripts.
    Safe to call multiple times (idempotent)."""
    if folder_id:
        transcripts = await transcript_service.get_transcripts_in_folder_tree(folder_id)
    else:
        transcripts = await transcript_service.get_all_transcripts()

    migrated = 0
    skipped = 0
    for t in transcripts:
        transcript_text = t.get("transcript", "")
        if not transcript_text:
            skipped += 1
            continue
        await speaker_service.extract_and_save_transcript_speakers(
            t["id"], transcript_text
        )
        migrated += 1

    return {
        "migrated": migrated,
        "skipped": skipped,
        "total": len(transcripts)
    }
