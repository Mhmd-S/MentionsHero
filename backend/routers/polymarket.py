"""Polymarket API routes."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from backend.models.polymarket import (
    PolymarketMarket,
    MarketsResponse,
    AnalyzeRequest,
    AnalyzeResponse,
    AddEventRequest,
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


# ----- Persona–event integration -----


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
