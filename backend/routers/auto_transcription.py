"""Auto-transcription API routes (manual-trigger only, no scheduler)."""

import logging

from fastapi import APIRouter, HTTPException

from backend.models.auto_transcription import (
    AutoSource,
    AutoSourceCreate,
    AutoSourceUpdate,
    RunResult,
    TimelineEntry,
)
from backend.services import auto_transcription_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auto-transcription", tags=["auto-transcription"])


# ---------------------------------------------------------------------------
# Static routes BEFORE parameterized routes
# ---------------------------------------------------------------------------

@router.get("/timeline", response_model=list[TimelineEntry])
async def get_timeline(limit: int = 200):
    """Global timeline of every video processed across all sources."""
    return await auto_transcription_service.get_timeline(limit)


# ---------------------------------------------------------------------------
# Sources CRUD
# ---------------------------------------------------------------------------

@router.get("/sources", response_model=list[AutoSource])
async def list_sources():
    return await auto_transcription_service.get_all_sources()


@router.get("/sources/{source_id}", response_model=AutoSource)
async def get_source(source_id: str):
    source = await auto_transcription_service.get_source(source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    return source


@router.post("/sources", response_model=AutoSource)
async def create_source(body: AutoSourceCreate):
    try:
        return await auto_transcription_service.create_source(body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.patch("/sources/{source_id}", response_model=AutoSource)
async def update_source(source_id: str, body: AutoSourceUpdate):
    try:
        source = await auto_transcription_service.update_source(
            source_id, body.model_dump(exclude_none=True)
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not source:
        raise HTTPException(404, "Source not found")
    return source


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    deleted = await auto_transcription_service.delete_source(source_id)
    if not deleted:
        raise HTTPException(404, "Source not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Manual run
# ---------------------------------------------------------------------------

@router.post("/sources/{source_id}/run", response_model=RunResult)
async def run_source(source_id: str):
    """Run discovery + transcription queueing for a single source.

    Synchronous: returns counts and per-video details once jobs have been
    queued. Each transcription itself continues in the background.
    """
    try:
        return await auto_transcription_service.run_source(source_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception("Manual run failed for source %s", source_id)
        raise HTTPException(500, f"Run failed: {e}")


@router.post("/sources/{source_id}/backfill", response_model=RunResult)
async def backfill_source(source_id: str):
    """One-shot full-history backfill for a single source.

    Ignores the regular `max_videos_per_check` cap; channels are pulled
    without yt-dlp's `--playlist-end` limit so every listable upload is
    considered. Jobs queued this way are capped by the source's
    `backfill_limit` (0 / null = unlimited) and still throttled by
    `auto_semaphore` (max 3 concurrent).
    """
    try:
        return await auto_transcription_service.backfill_source(source_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        logger.exception("Backfill failed for source %s", source_id)
        raise HTTPException(500, f"Backfill failed: {e}")
