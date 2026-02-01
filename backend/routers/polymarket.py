"""Polymarket API routes."""

from typing import Literal

from fastapi import APIRouter, HTTPException

from backend.models.polymarket import (
    PolymarketMarket,
    MarketsResponse,
    AnalyzeRequest,
    AnalyzeResponse,
)
from backend.services import polymarket_service
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
