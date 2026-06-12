"""Analytical data procurement API routes."""

import logging
from datetime import datetime

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
    ScrapeRequest,
    TruthSocialPost,
)
from backend.services import (
    analytical_news_service,
    analytical_truth_social_service,
    analytical_procurement_service,
    analytical_event_tag_service,
    analytical_context_service,
    metadata_extraction_service,
)
from backend.core.database import get_analytical_table

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytical", tags=["analytical"])


# ---------------------------------------------------------------------------
# Scrape procurement (real sources: Truth Social posts / Fox News articles)
# ---------------------------------------------------------------------------

@router.post("/scrape", response_model=ProcurementResult)
async def start_scrape(body: ScrapeRequest, background_tasks: BackgroundTasks):
    """Start a date-ranged scrape in the background; returns the real run_id
    so the caller can track live progress via /procurement-runs."""
    try:
        run_id = await analytical_procurement_service.start_run(
            body.source_type, body.persona_id
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    background_tasks.add_task(
        analytical_procurement_service.execute_run,
        run_id,
        body.source_type,
        body.persona_id,
        body.start_date,
        body.end_date,
    )
    return ProcurementResult(message="Scrape started", run_id=run_id)


@router.post("/scrape-sync", response_model=ProcurementResult)
async def start_scrape_sync(body: ScrapeRequest):
    """Run a scrape synchronously (small ranges / testing)."""
    try:
        result = await analytical_procurement_service.run_scrape(
            body.source_type, body.persona_id, body.start_date, body.end_date
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ProcurementResult(
        message=f"Scrape {result['status']}",
        run_id=result["run_id"],
        items_found=result["items_found"],
        items_new=result["items_new"],
        items_skipped=result["items_skipped"],
    )


# ---------------------------------------------------------------------------
# News + Truth Social reads (date-range + outlet filtering)
# ---------------------------------------------------------------------------

@router.get("/news", response_model=list[NewsItem])
async def list_news(
    persona_id: str = Query(...),
    days: int = Query(7, ge=1, le=3650),
    limit: int = Query(100, ge=1, le=2000),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    source: str | None = Query(None, description="Outlet filter, e.g. 'foxnews.com' or 'Fox News'"),
):
    """List news items for a persona (optional explicit window + outlet filter)."""
    return await analytical_news_service.get_news_items(
        persona_id, days, limit, start, end, source
    )


@router.get("/truth-social", response_model=list[TruthSocialPost])
async def list_truth_social(
    persona_id: str = Query(...),
    days: int = Query(7, ge=1, le=3650),
    limit: int = Query(100, ge=1, le=2000),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
):
    """List Truth Social posts for a persona (optional explicit window)."""
    return await analytical_truth_social_service.get_posts(
        persona_id, days, limit, start, end
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


@router.post("/procurement-runs/reset-stale")
async def reset_stale_procurement_runs():
    """Mark any 'running' procurement_run with no recent heartbeat as cancelled.
    Use this to recover after a backend crash."""
    return await metadata_extraction_service.reset_stale_runs()


@router.post("/procurement-runs/{run_id}/cancel")
async def cancel_procurement_run(run_id: str):
    """Request cancellation of an in-flight procurement_run. The worker
    polls the cancel flag at each iteration and exits cleanly."""
    try:
        return await metadata_extraction_service.cancel_run(run_id)
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.delete("/procurement-runs/{run_id}")
async def delete_procurement_run(run_id: str):
    """Delete a procurement_run record. Refuses to delete an in-flight run."""
    try:
        ok = await metadata_extraction_service.delete_run(run_id)
    except ValueError as e:
        raise HTTPException(409, str(e))
    if not ok:
        raise HTTPException(404, "procurement_run not found")
    return {"deleted": True, "run_id": run_id}
