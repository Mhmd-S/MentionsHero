"""Polymarket API routes."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from backend.models.polymarket import (
    PolymarketMarket,
    MarketsResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    AddEventRequest,
    AddSeriesRequest,
    LinkPersonaToSeriesRequest,
)
from backend.services import polymarket_service, persona_service
from backend.utils.nlp import calculate_term_frequency
from backend.services import transcript_service

router = APIRouter(prefix="/api/polymarket", tags=["polymarket"])


@router.get("/markets")
async def get_markets(
    type: str = "all"
) -> MarketsResponse:
    """
    Fetch Polymarket markets.

    Args:
        type: "all", "mentions", or "leavitt"
    """
    markets: list[PolymarketMarket] = []

    try:
        if type == "mentions":
            markets = await polymarket_service.get_mentions_markets()
        elif type == "leavitt":
            markets = await polymarket_service.get_leavitt_markets()
        else:
            # Fetch both and deduplicate
            leavitt = await polymarket_service.get_leavitt_markets()
            mentions = await polymarket_service.get_mentions_markets()

            seen: set[str] = set()
            for market in [*leavitt, *mentions]:
                if market.id not in seen:
                    seen.add(market.id)
                    markets.append(market)

        return MarketsResponse(
            markets=markets,
            count=len(markets),
            source="live"
        )

    except Exception as e:
        print(f"Failed to fetch Polymarket markets: {e}")

        # Return mock data for development/testing
        mock_markets = polymarket_service.get_mock_markets()
        return MarketsResponse(
            markets=mock_markets,
            count=len(mock_markets),
            source="mock"
        )


@router.post("/analyze")
async def analyze_market(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Analyze a market opportunity based on historical term frequency.
    """
    if not request.market or not request.term:
        raise HTTPException(status_code=400, detail="market and term are required")

    # Get historical frequency for the term
    transcripts = await transcript_service.get_all_transcripts()

    if not transcripts:
        # Return default analysis if no transcripts available
        return AnalyzeResponse(
            market_id=request.market.id,
            market_question=request.market.question,
            term=request.term,
            historical_percentage=0.0,
            market_yes_price=float(request.market.outcome_prices[0]) if request.market.outcome_prices else 0.5,
            recommendation="skip",
            confidence="low",
            reason="No historical data available for analysis",
            expected_value=0.0
        )

    term_freq = calculate_term_frequency(
        transcripts,
        request.term,
        case_sensitive=False
    )

    analysis = polymarket_service.analyze_market_opportunity(
        request.market,
        term_freq["percentage"]
    )

    yes_price = float(request.market.outcome_prices[0]) if request.market.outcome_prices else 0.5

    return AnalyzeResponse(
        market_id=request.market.id,
        market_question=request.market.question,
        term=request.term,
        historical_percentage=term_freq["percentage"],
        market_yes_price=yes_price,
        recommendation=analysis["recommendation"],
        confidence=analysis["confidence"],
        reason=analysis["reason"],
        expected_value=analysis["expectedValue"]
    )


# ----- Series endpoints -----


@router.get("/series")
async def list_series():
    """List all stored series with event counts and persona IDs."""
    return await polymarket_service.get_all_series()


@router.post("/series")
async def add_series(request: AddSeriesRequest):
    """Add a series by slug."""
    if not request.slug:
        raise HTTPException(status_code=400, detail="slug is required")
    result, error = await polymarket_service.add_series(request.slug)
    if error == "not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Series not found for slug: {request.slug}. Check the slug or search /api/polymarket/series/search first.",
        )
    if error == "api_error":
        raise HTTPException(
            status_code=502,
            detail="Polymarket Gamma API error. Try again later or check the slug.",
        )
    if error == "db_error":
        raise HTTPException(
            status_code=502,
            detail="Failed to save series to database. Check logs and database state.",
        )
    if result is None:
        raise HTTPException(status_code=502, detail="Failed to add series")
    return result


@router.get("/series/search")
async def search_series(
    q: str = Query("", description="Search query (slug fragment)"),
    active: bool | None = Query(None),
    closed: bool | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Search Gamma series API for discovery."""
    return await polymarket_service.search_series(q, active=active, closed=closed, limit=limit, offset=offset)


@router.post("/series/backfill-from-events")
async def backfill_series(background_tasks: BackgroundTasks):
    """One-time migration: associate existing events with series."""
    background_tasks.add_task(polymarket_service.backfill_series_from_existing_events)
    return {"message": "Backfill scheduled"}


@router.get("/series/{series_id}")
async def get_series_detail(series_id: str):
    """Get series detail with events and linked personas."""
    result = await polymarket_service.get_series_detail(series_id)
    if not result:
        raise HTTPException(status_code=404, detail="Series not found")
    return result


@router.post("/series/{series_id}/refresh")
async def refresh_series(series_id: str):
    """Refresh series from Gamma API."""
    result = await polymarket_service.refresh_series(series_id)
    if not result:
        raise HTTPException(status_code=404, detail="Series not found")
    return result


@router.delete("/series/{series_id}")
async def delete_series(series_id: str):
    """Delete a stored series."""
    removed = await polymarket_service.delete_series(series_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Series not found")
    return {"ok": True}


@router.post("/series/{series_id}/personas")
async def link_persona_to_series(series_id: str, request: LinkPersonaToSeriesRequest):
    """Link a persona to a series."""
    persona = await persona_service.get_persona_by_id(request.persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    linked = await polymarket_service.link_persona_to_series(request.persona_id, series_id)
    if not linked:
        raise HTTPException(status_code=409, detail="Already linked")
    return {"ok": True}


@router.delete("/series/{series_id}/personas/{persona_id}")
async def unlink_persona_from_series(series_id: str, persona_id: str):
    """Unlink a persona from a series."""
    removed = await polymarket_service.unlink_persona_from_series(persona_id, series_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"ok": True}


@router.get("/series/{series_id}/personas")
async def get_series_personas(series_id: str):
    """Get persona IDs linked to a series."""
    return await polymarket_service.get_personas_for_series(series_id)


@router.get("/series/{series_id}/events/{event_id}")
async def get_series_event(
    series_id: str,
    event_id: str,
    persona_id: str | None = Query(None, description="Optional persona ID for analysis data"),
):
    """Get event with markets and optional persona analysis."""
    result = await polymarket_service.get_event_with_analysis(event_id, persona_id=persona_id)
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.post("/series/{series_id}/events/{event_id}/refresh")
async def refresh_series_event(series_id: str, event_id: str):
    """Refresh a single event from Gamma."""
    result = await polymarket_service.refresh_single_event(event_id)
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


# ----- Persona–event integration (legacy) -----


@router.post("/events")
async def add_event(request: AddEventRequest):
    """Add a Polymarket event by slug and associate with a persona."""
    if not request.persona_id or not request.slug:
        raise HTTPException(status_code=400, detail="persona_id and slug are required")
    persona = await persona_service.get_persona_by_id(request.persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    result = await polymarket_service.add_persona_event(request.persona_id, request.slug)
    if not result:
        raise HTTPException(status_code=502, detail="Failed to fetch event from Polymarket or save")
    return result


@router.get("/events/{persona_id}")
async def list_persona_events(persona_id: str):
    """List events linked to a persona with markets and analysis results."""
    persona = await persona_service.get_persona_by_id(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    return await polymarket_service.get_persona_events(persona_id)


@router.delete("/events/{event_id}")
async def remove_event(
    event_id: str,
    persona_id: str = Query(..., description="Persona ID to unlink from"),
):
    """Remove the link between a persona and a Polymarket event."""
    persona = await persona_service.get_persona_by_id(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    removed = await polymarket_service.remove_persona_event(persona_id, event_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"ok": True}


@router.post("/events/{event_id}/refresh")
async def refresh_event(
    event_id: str,
    persona_id: str = Query(..., description="Persona ID to refresh analysis for"),
):
    """Re-fetch event from Polymarket and refresh market data and analysis."""
    persona = await persona_service.get_persona_by_id(persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    result = await polymarket_service.refresh_persona_event(persona_id, event_id)
    if not result:
        raise HTTPException(status_code=404, detail="Event not found or refresh failed")
    return result


@router.post("/events/backfill-term-results")
async def backfill_term_results(background_tasks: BackgroundTasks) -> dict:
    """One-time backfill: schedule update_market_analysis for every persona-event link."""
    from backend.core.database import get_supabase
    supabase = get_supabase()
    links = supabase.table("persona_polymarket_events").select("persona_id, polymarket_event_id").execute()
    rows = links.data or []
    for r in rows:
        persona_id = r["persona_id"]
        event_id = r["polymarket_event_id"]
        background_tasks.add_task(polymarket_service.update_market_analysis, persona_id, event_id)
    return {"scheduled": len(rows), "message": "Backfill scheduled for all persona-event links."}
