"""Polymarket API routes."""

from fastapi import APIRouter, HTTPException, Query

from backend.models.polymarket import (
    AddPolyEventRequest,
)
from backend.services import polymarket_service

router = APIRouter(prefix="/api/polymarket", tags=["polymarket"])


# ----- Event endpoints (static routes MUST come before parameterized) -----


@router.get("/events/search")
async def search_events(
    q: str = Query(..., description="Search query"),
    limit: int = Query(20, ge=1, le=100),
    mentions_only: bool = Query(True, description="Only return mentions-style markets"),
):
    """Search Polymarket for events by keyword, filtered to mentions markets by default."""
    results = await polymarket_service.search_events(q, limit=limit, mentions_only=mentions_only)
    # Return lightweight search results
    return [
        {
            "poly_id": str(ev.get("id", "")),
            "slug": ev.get("slug", ""),
            "title": ev.get("title"),
            "image": ev.get("image"),
            "market_count": len(ev.get("markets") or []),
            "volume": ev.get("volume"),
            "end_date": ev.get("endDate"),
        }
        for ev in results
    ]


@router.get("/events")
async def list_stored_events():
    """List all stored Polymarket events with market counts and persona links."""
    return await polymarket_service.get_stored_events()


@router.post("/events")
async def add_event(request: AddPolyEventRequest):
    """Add a Polymarket event by slug or URL."""
    if not request.slug:
        raise HTTPException(status_code=400, detail="slug is required")
    slug = polymarket_service.extract_slug_from_url(request.slug)
    result = await polymarket_service.add_event(slug)
    if not result:
        raise HTTPException(status_code=404, detail=f"Event not found for slug: {slug}")
    return result


@router.get("/events/{event_id}")
async def get_event_detail(
    event_id: str,
    persona_id: str | None = Query(None),
):
    """Get Polymarket event detail with markets and optional persona analysis."""
    result = await polymarket_service.get_event_detail(event_id, persona_id=persona_id)
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.post("/events/{event_id}/refresh")
async def refresh_event(event_id: str):
    """Refresh a Polymarket event from the API."""
    result = await polymarket_service.refresh_event(event_id)
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.delete("/events/{event_id}")
async def delete_event(event_id: str):
    """Delete a stored Polymarket event."""
    success = await polymarket_service.delete_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"ok": True}
