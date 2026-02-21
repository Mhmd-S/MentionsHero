"""Kalshi API routes."""

from fastapi import APIRouter, HTTPException, Query

from backend.models.kalshi import (
    AddSeriesRequest,
    LinkPersonaToSeriesRequest,
    AnalyzeRequest,
    AnalyzeResponse,
)
from backend.services import kalshi_service, persona_service
from backend.utils.nlp import calculate_term_frequency
from backend.services import transcript_service

router = APIRouter(prefix="/api/kalshi", tags=["kalshi"])


# ----- Series endpoints (static routes MUST come before parameterized) -----


@router.get("/series")
async def list_series():
    """List all stored series with event counts and persona IDs."""
    return await kalshi_service.get_all_series()


@router.post("/series")
async def add_series(request: AddSeriesRequest):
    """Add a series by ticker."""
    if not request.ticker:
        raise HTTPException(status_code=400, detail="ticker is required")
    result, error = await kalshi_service.add_series(request.ticker)
    if error == "not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Series not found for ticker: {request.ticker}.",
        )
    if error == "db_error":
        raise HTTPException(
            status_code=502,
            detail="Failed to save series to database.",
        )
    if result is None:
        raise HTTPException(status_code=502, detail="Failed to add series")
    return result


@router.get("/series/discover")
async def discover_series_endpoint(
    tags: str | None = Query(None, description="Comma-separated tags (e.g. Politicians,Earnings)"),
):
    """Discover available Mentions series from Kalshi, optionally filtered by tags."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    return await kalshi_service.discover_series(tags=tag_list)


@router.post("/series/{series_id}/load-past-events")
async def load_past_events(series_id: str):
    """Fetch + store closed events for a series from Kalshi."""
    result = await kalshi_service.fetch_past_events_for_series(series_id)
    detail = await kalshi_service.get_series_detail(series_id)
    return {**result, "detail": detail}


@router.get("/series/{series_id}")
async def get_series_detail(series_id: str):
    """Get series detail with events and linked personas."""
    result = await kalshi_service.get_series_detail(series_id)
    if not result:
        raise HTTPException(status_code=404, detail="Series not found")
    return result


@router.post("/series/{series_id}/refresh")
async def refresh_series(series_id: str):
    """Refresh series from Kalshi API."""
    result = await kalshi_service.refresh_series(series_id)
    if not result:
        raise HTTPException(status_code=404, detail="Series not found")
    return result


@router.delete("/series/{series_id}")
async def delete_series(series_id: str):
    """Delete a stored series."""
    removed = await kalshi_service.delete_series(series_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Series not found")
    return {"ok": True}


@router.post("/series/{series_id}/personas")
async def link_persona_to_series(series_id: str, request: LinkPersonaToSeriesRequest):
    """Link a persona to a series."""
    persona = await persona_service.get_persona_by_id(request.persona_id)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")
    linked = await kalshi_service.link_persona_to_series(request.persona_id, series_id, folder_id=request.folder_id)
    if not linked:
        raise HTTPException(status_code=409, detail="Already linked")
    return {"ok": True}


@router.delete("/series/{series_id}/personas/{persona_id}")
async def unlink_persona_from_series(series_id: str, persona_id: str):
    """Unlink a persona from a series."""
    removed = await kalshi_service.unlink_persona_from_series(persona_id, series_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Link not found")
    return {"ok": True}


@router.get("/series/{series_id}/personas")
async def get_series_personas(series_id: str):
    """Get persona IDs linked to a series."""
    return await kalshi_service.get_personas_for_series(series_id)


@router.get("/series/{series_id}/events/{event_id}")
async def get_series_event(
    series_id: str,
    event_id: str,
    persona_id: str | None = Query(None, description="Optional persona ID for analysis data"),
):
    """Get event with markets and optional persona analysis."""
    result = await kalshi_service.get_event_with_analysis(event_id, persona_id=persona_id)
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


@router.post("/series/{series_id}/events/{event_id}/refresh")
async def refresh_series_event(series_id: str, event_id: str):
    """Refresh a single event from Kalshi."""
    result = await kalshi_service.refresh_single_event(event_id)
    if not result:
        raise HTTPException(status_code=404, detail="Event not found")
    return result


# ----- Analysis -----


@router.post("/analyze")
async def analyze_market(request: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a market opportunity based on historical term frequency."""
    if not request.market_ticker or not request.term:
        raise HTTPException(status_code=400, detail="market_ticker and term are required")

    supabase = kalshi_service.get_supabase()
    market_row = supabase.table("kalshi_markets").select("*").eq("ticker", request.market_ticker).single().execute()
    if not market_row.data:
        raise HTTPException(status_code=404, detail="Market not found")

    market = market_row.data
    transcripts = await transcript_service.get_all_transcripts()

    if not transcripts:
        return AnalyzeResponse(
            market_id=market["id"],
            market_question=market.get("question") or "",
            term=request.term,
            historical_percentage=0.0,
            market_yes_price=market.get("last_price") or 0.5,
            recommendation="skip",
            confidence="low",
            reason="No historical data available for analysis",
            expected_value=0.0,
        )

    term_freq = calculate_term_frequency(transcripts, request.term, case_sensitive=False)
    yes_price = market.get("last_price") or 0.5

    analysis = kalshi_service.analyze_market_opportunity(yes_price, term_freq["percentage"])

    return AnalyzeResponse(
        market_id=market["id"],
        market_question=market.get("question") or "",
        term=request.term,
        historical_percentage=term_freq["percentage"],
        market_yes_price=yes_price,
        recommendation=analysis["recommendation"],
        confidence=analysis["confidence"],
        reason=analysis["reason"],
        expected_value=analysis["expectedValue"],
    )
