"""Polymarket API client service."""

import re
from typing import Literal

import httpx

from backend.models.polymarket import (
    PolymarketMarket,
    PolymarketEvent,
    PolymarketTag,
)


POLYMARKET_CLOB_API = "https://clob.polymarket.com"
GAMMA_API_BASE = "https://gamma-api.polymarket.com"


async def get_tags(limit: int = 100) -> list[PolymarketTag]:
    """Fetch all available tags/categories."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GAMMA_API_BASE}/tags",
                params={"limit": limit}
            )
            response.raise_for_status()
            data = response.json()
            return [PolymarketTag(**tag) for tag in data] if data else []
    except Exception as e:
        print(f"Failed to fetch tags: {e}")
        return []


async def get_events_by_tag(
    tag_id: str,
    active: bool = True,
    closed: bool = False,
    limit: int = 50
) -> list[PolymarketEvent]:
    """Fetch events by tag ID."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GAMMA_API_BASE}/events",
                params={
                    "tag_id": tag_id,
                    "active": str(active).lower(),
                    "closed": str(closed).lower(),
                    "limit": limit
                }
            )
            response.raise_for_status()
            data = response.json()
            return [PolymarketEvent(**event) for event in data] if data else []
    except Exception as e:
        print(f"Failed to fetch events by tag: {e}")
        return []


async def get_all_active_events(limit: int = 100) -> list[PolymarketEvent]:
    """Fetch all active events."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{GAMMA_API_BASE}/events",
                params={
                    "active": "true",
                    "closed": "false",
                    "limit": limit
                }
            )
            response.raise_for_status()
            data = response.json()
            return [PolymarketEvent(**event) for event in data] if data else []
    except Exception as e:
        print(f"Failed to fetch active events: {e}")
        return []


def dedupe_events(events: list[PolymarketEvent]) -> list[PolymarketEvent]:
    """Deduplicate events by ID, preserving first occurrence."""
    seen_ids: set[str] = set()
    result: list[PolymarketEvent] = []
    for event in events:
        if event.id not in seen_ids:
            seen_ids.add(event.id)
            result.append(event)
    return result


async def get_leavitt_events() -> list[PolymarketEvent]:
    """
    Get events related to Leavitt/White House press briefings.

    Strategy:
    1. Try tag-based discovery
    2. Fall back to keyword search
    """
    try:
        # Try tag-based discovery first
        tags = await get_tags(100)
        relevant_tags = [
            tag for tag in tags
            if any(
                k in (tag.slug or "").lower() or k in (tag.label or "").lower()
                for k in ["leavitt", "karoline", "briefing", "press"]
            )
        ]

        if relevant_tags:
            events_lists = []
            for tag in relevant_tags:
                tag_events = await get_events_by_tag(tag.id, active=True, closed=False, limit=50)
                events_lists.append(tag_events)

            events = dedupe_events([e for sublist in events_lists for e in sublist])
            if events:
                return events

        # Fallback to keyword search
        all_events = await get_all_active_events(200)
        search_patterns = ["leavitt", "karoline", "briefing", "press-secretary", "white-house-press"]

        result: list[PolymarketEvent] = []
        seen_ids: set[str] = set()

        for event in all_events:
            title_lower = (event.title or "").lower()
            slug_lower = (event.slug or "").lower()
            desc_lower = (event.description or "").lower()

            matches = any(
                pattern in title_lower or pattern in slug_lower or pattern in desc_lower
                for pattern in search_patterns
            )

            if matches and event.id not in seen_ids:
                seen_ids.add(event.id)
                result.append(event)

        return result

    except Exception as e:
        print(f"Failed to fetch Leavitt events: {e}")
        return []


async def get_mentions_markets() -> list[PolymarketMarket]:
    """
    Get "mentions" style markets from events.

    These are sub-markets asking "Will X be mentioned?" or "Will she say X?"
    """
    markets: list[PolymarketMarket] = []

    try:
        events = await get_leavitt_events()

        for event in events:
            if event.markets:
                mentions_markets = [
                    market for market in event.markets
                    if any(
                        phrase in (market.question or "").lower()
                        for phrase in ["mention", "will", "said", "refer to"]
                    )
                ]
                markets.extend(mentions_markets)

    except Exception as e:
        print(f"Failed to fetch mentions markets: {e}")

    return markets


async def get_leavitt_markets() -> list[PolymarketMarket]:
    """Get all markets from Leavitt events (not just mentions-style)."""
    markets: list[PolymarketMarket] = []

    try:
        events = await get_leavitt_events()

        for event in events:
            if event.markets:
                markets.extend(event.markets)

    except Exception as e:
        print(f"Failed to fetch Leavitt markets: {e}")

    return markets


async def get_token_price(token_id: str, side: str = "buy") -> float | None:
    """Get current price for a token from CLOB."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{POLYMARKET_CLOB_API}/price",
                params={"token_id": token_id, "side": side}
            )
            response.raise_for_status()
            data = response.json()
            if data and "price" in data:
                return float(data["price"])
            return None
    except Exception as e:
        print(f"Failed to fetch price for token {token_id}: {e}")
        return None


def extract_term_from_question(question: str) -> str | None:
    """
    Extract the betting term from a market question.

    e.g., "Will she say 'tariffs'?" -> "tariffs"
    """
    # Pattern 1: "mention 'X'" or "say 'X'"
    quote_match = re.search(r"(?:mention|say)\s+['\"\u201c]([^'\"\u201d]+)['\"\u201d]|['\"\u201c]([^'\"\u201d]+)['\"\u201d]", question)
    if quote_match:
        return quote_match.group(1) or quote_match.group(2)

    # Pattern 2: "mention X" without quotes (look for capitalized term)
    mention_match = re.search(
        r"(?:mention|say|refer to)\s+([A-Z][a-zA-Z\s]+?)(?:\s+(?:in|during|at)|\?|$)",
        question,
        re.IGNORECASE
    )
    if mention_match:
        return mention_match.group(1).strip()

    return None


def analyze_market_opportunity(
    market: PolymarketMarket,
    historical_percentage: float
) -> dict:
    """
    Analyze market and provide betting insight.

    Returns recommendation, confidence, reason, and expected value.
    """
    # Parse current market price (probability)
    yes_price_str = market.outcome_prices[0] if market.outcome_prices else "0.5"
    yes_price = float(yes_price_str)

    # Historical percentage is our estimated true probability
    estimated_probability = historical_percentage / 100

    # Calculate expected value
    # If we bet on YES: EV = prob * (1/p) - 1
    yes_ev = estimated_probability * (1 / yes_price) - 1 if yes_price > 0 else 0
    no_ev = (1 - estimated_probability) * (1 / (1 - yes_price)) - 1 if yes_price < 1 else 0

    # Determine recommendation
    recommendation: Literal["yes", "no", "skip"] = "skip"
    confidence: Literal["high", "medium", "low"] = "low"
    reason = ""
    expected_value = 0.0

    if yes_ev > 0.15:
        recommendation = "yes"
        expected_value = yes_ev
        if yes_ev > 0.3 and estimated_probability > 0.8:
            confidence = "high"
            reason = f"Term appears in {historical_percentage:.0f}% of briefings but market only prices YES at {yes_price * 100:.0f}%"
        elif yes_ev > 0.2:
            confidence = "medium"
            reason = f"Positive expected value: historical {historical_percentage:.0f}% vs market {yes_price * 100:.0f}%"
        else:
            confidence = "low"
            reason = f"Slight edge detected: {historical_percentage:.0f}% historical vs {yes_price * 100:.0f}% market"
    elif no_ev > 0.15:
        recommendation = "no"
        expected_value = no_ev
        if no_ev > 0.3 and estimated_probability < 0.2:
            confidence = "high"
            reason = f"Term only appears in {historical_percentage:.0f}% of briefings but market prices YES at {yes_price * 100:.0f}%"
        elif no_ev > 0.2:
            confidence = "medium"
            reason = f"Negative edge: historical {historical_percentage:.0f}% vs market {yes_price * 100:.0f}%"
        else:
            confidence = "low"
            reason = f"Slight NO edge: {historical_percentage:.0f}% historical vs {yes_price * 100:.0f}% market"
    else:
        reason = f"Market fairly priced: historical {historical_percentage:.0f}% ≈ market {yes_price * 100:.0f}%"

    return {
        "recommendation": recommendation,
        "confidence": confidence,
        "reason": reason,
        "expectedValue": round(expected_value, 2)
    }


def get_mock_markets() -> list[PolymarketMarket]:
    """Return mock markets for development/testing."""
    from datetime import datetime, timedelta

    end_date = (datetime.now() + timedelta(days=1)).isoformat()

    return [
        PolymarketMarket(
            id="mock-1",
            question="Will Karoline Leavitt mention \"tariffs\" in her next briefing?",
            slug="leavitt-tariffs-mention",
            description="Resolves YES if \"tariffs\" is said during the next White House press briefing.",
            outcomes=["Yes", "No"],
            outcome_prices=["0.72", "0.28"],
            volume="15420",
            liquidity="8500",
            end_date=end_date,
            active=True,
            closed=False,
            category="Politics"
        ),
        PolymarketMarket(
            id="mock-2",
            question="Will \"fake news\" be mentioned in the next press briefing?",
            slug="fake-news-mention",
            description="Resolves YES if the phrase \"fake news\" is spoken during the briefing.",
            outcomes=["Yes", "No"],
            outcome_prices=["0.45", "0.55"],
            volume="8230",
            liquidity="4200",
            end_date=end_date,
            active=True,
            closed=False,
            category="Politics"
        ),
        PolymarketMarket(
            id="mock-3",
            question="Will Elon Musk be mentioned in White House briefing?",
            slug="elon-musk-mention",
            description="Resolves YES if Elon Musk is mentioned by name.",
            outcomes=["Yes", "No"],
            outcome_prices=["0.35", "0.65"],
            volume="22100",
            liquidity="12000",
            end_date=end_date,
            active=True,
            closed=False,
            category="Politics"
        ),
        PolymarketMarket(
            id="mock-4",
            question="Will \"the American people\" be said in next briefing?",
            slug="american-people-mention",
            description="Resolves YES if the phrase \"the American people\" is spoken.",
            outcomes=["Yes", "No"],
            outcome_prices=["0.88", "0.12"],
            volume="5600",
            liquidity="2800",
            end_date=end_date,
            active=True,
            closed=False,
            category="Politics"
        )
    ]
