"""Analytical data procurement API routes."""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from backend.models.analytical import (
    BulkAutoTagResult,
    BulkBackfillMetadataResult,
    BulkComputeResult,
    ContextWindow,
    EventTag,
    EventTagCreate,
    EventTagUpdate,
    NewsItem,
    ProcurementResult,
    ProcurementRun,
    ProcureNewsRequest,
    ProcureTruthSocialRequest,
    TruthSocialPost,
)
from backend.services import (
    analytical_news_service,
    analytical_truth_social_service,
    analytical_event_tag_service,
    analytical_context_service,
    metadata_extraction_service,
)
from backend.core.database import get_analytical_table

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytical", tags=["analytical"])


# ---------------------------------------------------------------------------
# News procurement
# ---------------------------------------------------------------------------

@router.get("/news", response_model=list[NewsItem])
async def list_news(
    persona_id: str = Query(...),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=500),
):
    """List news items for a persona."""
    return await analytical_news_service.get_news_items(persona_id, days, limit)


@router.post("/news/procure", response_model=ProcurementResult)
async def procure_news(
    body: ProcureNewsRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger news procurement via DuckDuckGo."""
    background_tasks.add_task(
        analytical_news_service.procure_news,
        body.persona_id,
        body.query,
        body.days_back,
    )
    return ProcurementResult(
        message="News procurement started",
        run_id="pending",
    )


@router.post("/news/procure-sync", response_model=ProcurementResult)
async def procure_news_sync(body: ProcureNewsRequest):
    """Trigger news procurement synchronously (for testing)."""
    result = await analytical_news_service.procure_news(
        body.persona_id, body.query, body.days_back,
    )
    return ProcurementResult(
        message="News procurement completed",
        run_id=result["run_id"],
        items_found=result["items_found"],
        items_new=result["items_new"],
        items_skipped=result["items_skipped"],
    )


# ---------------------------------------------------------------------------
# Truth Social procurement
# ---------------------------------------------------------------------------

@router.get("/truth-social", response_model=list[TruthSocialPost])
async def list_truth_social(
    persona_id: str = Query(...),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(100, ge=1, le=500),
):
    """List Truth Social posts for a persona."""
    return await analytical_truth_social_service.get_posts(persona_id, days, limit)


@router.post("/truth-social/procure", response_model=ProcurementResult)
async def procure_truth_social(
    body: ProcureTruthSocialRequest,
    background_tasks: BackgroundTasks,
):
    """Trigger Truth Social procurement via DuckDuckGo."""
    background_tasks.add_task(
        analytical_truth_social_service.procure_truth_social_posts,
        body.persona_id,
        body.days_back,
    )
    return ProcurementResult(
        message="Truth Social procurement started",
        run_id="pending",
    )


@router.post("/truth-social/procure-sync", response_model=ProcurementResult)
async def procure_truth_social_sync(body: ProcureTruthSocialRequest):
    """Trigger Truth Social procurement synchronously (for testing)."""
    result = await analytical_truth_social_service.procure_truth_social_posts(
        body.persona_id, body.days_back,
    )
    return ProcurementResult(
        message="Truth Social procurement completed",
        run_id=result["run_id"],
        items_found=result["items_found"],
        items_new=result["items_new"],
        items_skipped=result["items_skipped"],
    )


# ---------------------------------------------------------------------------
# Event tags (static routes before parameterized)
# ---------------------------------------------------------------------------

@router.get("/event-tags", response_model=list[EventTag])
async def list_event_tags(
    event_type: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
):
    """List event tags, optionally filtered by type."""
    return await analytical_event_tag_service.get_tags_by_event_type(event_type, limit)


@router.post("/event-tags", response_model=EventTag)
async def create_event_tag(body: EventTagCreate):
    """Manually tag a transcript with event context."""
    try:
        return await analytical_event_tag_service.tag_transcript(body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/event-tags/auto-tag/{persona_id}", response_model=BulkAutoTagResult)
async def bulk_auto_tag(persona_id: str):
    """Auto-classify all untagged transcripts for a persona using DDG search."""
    result = await analytical_event_tag_service.bulk_auto_tag(persona_id)
    return BulkAutoTagResult(
        message="Bulk auto-tag completed",
        tagged=result["tagged"],
        skipped=result["skipped"],
        failed=result["failed"],
    )


@router.post(
    "/metadata/backfill/{persona_id}",
    response_model=BulkBackfillMetadataResult,
)
async def bulk_backfill_metadata(
    persona_id: str,
    force: bool = Query(False, description="Re-run even on rows with classification_source='manual'"),
    limit: int | None = Query(None, ge=1, description="Only process the first N candidates (smoke test)"),
):
    """Backfill the full metadata bundle (location, event_type, audience,
    event_time + frozen context_window) for every transcript belonging to a
    persona.

    Synchronous; long-running for large personas (~6s/transcript). The HTTP
    request stays open until done — the existing bulk endpoints follow the
    same pattern (see bulk_auto_tag, bulk_compute_context_windows). Progress
    is recorded in `analytical.procurement_runs` with `source_type='metadata_backfill'`.
    """
    try:
        result = await metadata_extraction_service.bulk_backfill_metadata(
            persona_id=persona_id, force=force, limit=limit,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))
    return BulkBackfillMetadataResult(
        message="Metadata backfill completed",
        run_id=result["run_id"],
        candidates=result["candidates"],
        succeeded=result["succeeded"],
        failed=result["failed"],
    )


@router.get("/event-tags/{transcript_id}", response_model=EventTag | None)
async def get_event_tag(transcript_id: str):
    """Get event tag for a transcript."""
    tag = await analytical_event_tag_service.get_tag(transcript_id)
    if not tag:
        raise HTTPException(404, "No event tag for this transcript")
    return tag


@router.patch("/event-tags/{transcript_id}", response_model=EventTag)
async def update_event_tag(transcript_id: str, body: EventTagUpdate):
    """Update an event tag."""
    result = await analytical_event_tag_service.update_tag(
        transcript_id, body.model_dump(exclude_none=True)
    )
    if not result:
        raise HTTPException(404, "No event tag for this transcript")
    return result


@router.delete("/event-tags/{transcript_id}")
async def delete_event_tag(transcript_id: str):
    """Delete an event tag."""
    deleted = await analytical_event_tag_service.delete_tag(transcript_id)
    if not deleted:
        raise HTTPException(404, "No event tag for this transcript")
    return {"ok": True}


# ---------------------------------------------------------------------------
# Context windows (static routes before parameterized)
# ---------------------------------------------------------------------------

@router.post("/context-windows/bulk-compute/{persona_id}", response_model=BulkComputeResult)
async def bulk_compute_context_windows(persona_id: str):
    """Compute context windows for all transcripts of a persona."""
    result = await analytical_context_service.bulk_compute_windows(persona_id)
    return BulkComputeResult(
        message="Bulk context window computation completed",
        computed=result["computed"],
        skipped=result["skipped"],
        failed=result["failed"],
    )


@router.post("/context-windows/compute/{transcript_id}", response_model=ContextWindow | None)
async def compute_context_window(
    transcript_id: str,
    persona_id: str = Query(...),
    hours_before: int = Query(72, ge=1, le=168),
):
    """Compute context window for a transcript."""
    result = await analytical_context_service.compute_context_window(
        transcript_id, persona_id, hours_before,
    )
    if not result:
        raise HTTPException(400, "Could not compute context window (missing upload_date?)")
    return result


@router.get("/context-windows/{transcript_id}", response_model=ContextWindow)
async def get_context_window(
    transcript_id: str,
    persona_id: str = Query(...),
):
    """Get context window for a transcript."""
    window = await analytical_context_service.get_context_window(transcript_id, persona_id)
    if not window:
        raise HTTPException(404, "No context window computed for this transcript")
    return window


# ---------------------------------------------------------------------------
# Procurement audit log
# ---------------------------------------------------------------------------

@router.get("/procurement-runs", response_model=list[ProcurementRun])
async def list_procurement_runs(
    source_type: str | None = Query(None),
    persona_id: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
):
    """Get recent procurement runs."""
    query = get_analytical_table("procurement_runs").select("*")
    if source_type:
        query = query.eq("source_type", source_type)
    if persona_id:
        query = query.eq("persona_id", persona_id)
    response = query.order("started_at", desc=True).limit(limit).execute()
    return response.data or []
