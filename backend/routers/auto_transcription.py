"""Auto-transcription API routes."""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.models.auto_transcription import (
    AutoSource,
    AutoSourceCreate,
    AutoSourceUpdate,
    AutoRun,
    ManualCheckResponse,
)
from backend.services import auto_transcription_service
from backend.scheduler import reschedule_source, remove_source

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auto-transcription", tags=["auto-transcription"])


# ---------------------------------------------------------------------------
# Sources CRUD
# ---------------------------------------------------------------------------

@router.get("/sources", response_model=list[AutoSource])
async def list_sources():
    """List all auto-transcription sources."""
    return await auto_transcription_service.get_all_sources()


@router.get("/sources/{source_id}", response_model=AutoSource)
async def get_source(source_id: str):
    """Get a single auto-transcription source."""
    source = await auto_transcription_service.get_source(source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    return source


@router.post("/sources", response_model=AutoSource)
async def create_source(body: AutoSourceCreate):
    """Create a new auto-transcription source."""
    try:
        source = await auto_transcription_service.create_source(body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Schedule it
    reschedule_source(source)
    return source


@router.patch("/sources/{source_id}", response_model=AutoSource)
async def update_source(source_id: str, body: AutoSourceUpdate):
    """Update an auto-transcription source."""
    try:
        source = await auto_transcription_service.update_source(
            source_id, body.model_dump(exclude_none=True)
        )
    except ValueError as e:
        raise HTTPException(400, str(e))

    if not source:
        raise HTTPException(404, "Source not found")

    # Reschedule with new settings
    reschedule_source(source)
    return source


@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    """Delete an auto-transcription source."""
    remove_source(source_id)
    deleted = await auto_transcription_service.delete_source(source_id)
    if not deleted:
        raise HTTPException(404, "Source not found")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Manual trigger
# ---------------------------------------------------------------------------

@router.post("/sources/{source_id}/check", response_model=ManualCheckResponse)
async def trigger_check(source_id: str, background_tasks: BackgroundTasks):
    """Manually trigger a check for a specific source."""
    source = await auto_transcription_service.get_source(source_id)
    if not source:
        raise HTTPException(404, "Source not found")

    background_tasks.add_task(
        auto_transcription_service.check_source_for_new_videos, source_id
    )
    return ManualCheckResponse(
        message="Check triggered",
        source_id=source_id,
    )


# ---------------------------------------------------------------------------
# Run history
# ---------------------------------------------------------------------------

@router.get("/sources/{source_id}/runs", response_model=list[AutoRun])
async def get_source_runs(source_id: str, limit: int = 20):
    """Get run history for a specific source."""
    return await auto_transcription_service.get_runs_for_source(source_id, limit)


@router.get("/runs", response_model=list[AutoRun])
async def get_recent_runs(limit: int = 50):
    """Get recent runs across all sources."""
    return await auto_transcription_service.get_recent_runs(limit)
