"""Polymarket API client service."""

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Literal

import httpx

from backend.config import get_settings
from backend.core.database import get_supabase
from backend.models.polymarket import (
    PolymarketMarket,
    PolymarketEvent,
    PolymarketTag,
)
from backend.utils.nlp import calculate_term_frequency, search_term_in_context


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


# ----- Persona–event integration (Gamma fetch, DB, Gemini parsing) -----

GAMMA_EVENTS_SLUG = f"{GAMMA_API_BASE}/events/slug"


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


async def fetch_event_by_slug(slug: str) -> dict[str, Any] | None:
    """Fetch a single event by slug from Gamma API. Returns raw dict (camelCase)."""
    slug = (slug or "").strip()
    if not slug:
        return None
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GAMMA_EVENTS_SLUG}/{slug}")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"Failed to fetch event by slug {slug}: {e}")
        return None


def parse_market_criteria(question: str) -> dict[str, Any]:
    """
    Extract search terms from a market question using regex.
    Terms are always in double quotes.

    Examples:
      'Will Keir Starmer say "International"?' -> { "search_terms": ["International"], "min_count": 0, "logic": "any" }
      'Will Keir Starmer say "Ally" or "Allied"?' -> { "search_terms": ["Ally", "Allied"], "min_count": 0, "logic": "any" }
    """
    question = (question or "").strip()
    default_result = {"search_terms": [], "min_count": 0, "logic": "any"}
    if not question:
        return default_result

    # Extract all quoted terms (supports both straight and curly quotes)
    pattern = r'["\u201c]([^"\u201d]+)["\u201d]'
    matches = re.findall(pattern, question)

    search_terms = [m.strip() for m in matches if m.strip()]

    # Check for "X+ times" pattern for min_count
    min_count = 0
    count_match = re.search(r'(\d+)\+?\s*times?', question, re.IGNORECASE)
    if count_match:
        min_count = int(count_match.group(1))

    logic = "any" if len(search_terms) > 1 else "at_least"

    print(f"[parse_market_criteria] question='{question[:80]}...' -> search_terms={search_terms}, min_count={min_count}")
    return {"search_terms": search_terms, "min_count": min_count, "logic": logic}


def _resolve_outcome(m: dict[str, Any]) -> str | None:
    """Determine resolved_outcome from market data. Returns 'YES', 'NO', or None."""
    closed = m.get("closed") if "closed" in m else False
    if not closed:
        return None
    outcome_prices = m.get("outcomePrices") or m.get("outcome_prices")
    if isinstance(outcome_prices, str):
        try:
            outcome_prices = json.loads(outcome_prices) if outcome_prices else []
        except json.JSONDecodeError:
            return None
    if not isinstance(outcome_prices, list) or len(outcome_prices) < 2:
        return None
    try:
        yes_price = float(outcome_prices[0])
        no_price = float(outcome_prices[1])
    except (ValueError, TypeError):
        return None
    if yes_price >= 0.95:
        return "YES"
    if no_price >= 0.95:
        return "NO"
    return None


def _upsert_event_and_markets(
    gamma_event: dict[str, Any],
    series_id: str | None = None,
) -> tuple[str | None, list[str]]:
    """
    Insert or update polymarket_events and polymarket_markets from Gamma event payload.
    Returns (event_id, list of market_ids).
    """
    supabase = get_supabase()
    slug = (gamma_event.get("slug") or "").strip()
    if not slug:
        return None, []

    title = gamma_event.get("title") or gamma_event.get("groupItemTitle")
    image = gamma_event.get("image")
    start_date = _parse_iso(gamma_event.get("startDate") or gamma_event.get("startDateIso"))
    end_date = _parse_iso(gamma_event.get("endDate") or gamma_event.get("endDateIso"))
    polymarket_id = gamma_event.get("id")

    # Upsert event (by slug)
    existing = supabase.table("polymarket_events").select("id").eq("slug", slug).limit(1).execute()
    now = datetime.now(timezone.utc).isoformat()
    event_row: dict[str, Any] = {
        "title": title,
        "image": image,
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "updated_at": now,
    }
    if series_id:
        event_row["series_id"] = series_id
    if polymarket_id:
        event_row["polymarket_id"] = polymarket_id

    if existing.data and len(existing.data) > 0:
        event_id = existing.data[0]["id"]
        supabase.table("polymarket_events").update(event_row).eq("id", event_id).execute()
    else:
        event_row["slug"] = slug
        supabase.table("polymarket_events").insert(event_row).execute()
        refetch = supabase.table("polymarket_events").select("id").eq("slug", slug).limit(1).execute()
        if not refetch.data or len(refetch.data) == 0:
            return None, []
        event_id = refetch.data[0]["id"]

    # Markets: Gamma event may have "markets" array
    markets_payload = gamma_event.get("markets") or []
    if not isinstance(markets_payload, list):
        markets_payload = []
    market_ids: list[str] = []

    for m in markets_payload:
        condition_id = m.get("conditionId") or m.get("condition_id")
        question = m.get("question")
        slug_m = m.get("slug") or ""
        active = m.get("active") if "active" in m else True
        closed = m.get("closed") if "closed" in m else False
        outcome_prices = m.get("outcomePrices") or m.get("outcome_prices")
        if isinstance(outcome_prices, str):
            try:
                outcome_prices = json.loads(outcome_prices) if outcome_prices else []
            except json.JSONDecodeError:
                outcome_prices = []
        if not isinstance(outcome_prices, list):
            outcome_prices = []

        resolved_outcome = _resolve_outcome(m)
        closed_time_str = m.get("closedTime") or m.get("closed_time")
        closed_time = _parse_iso(closed_time_str)
        resolution_source = m.get("resolutionSource") or m.get("resolution_source")

        # Upsert market by condition_id if present, else by (event_id, question)
        if condition_id:
            existing_m = supabase.table("polymarket_markets").select("id").eq("condition_id", condition_id).limit(1).execute()
        else:
            existing_m = supabase.table("polymarket_markets").select("id").eq("event_id", event_id).eq("question", question or "").limit(1).execute()

        row = {
            "event_id": event_id,
            "condition_id": condition_id,
            "question": question,
            "slug": slug_m or None,
            "active": active,
            "closed": closed,
            "outcome_prices": outcome_prices,
            "resolved_outcome": resolved_outcome,
            "closed_time": closed_time.isoformat() if closed_time else None,
            "resolution_source": resolution_source,
            "updated_at": now,
        }
        if existing_m.data and len(existing_m.data) > 0:
            market_id = existing_m.data[0]["id"]
            supabase.table("polymarket_markets").update(row).eq("id", market_id).execute()
        else:
            row["created_at"] = now
            supabase.table("polymarket_markets").insert(row).execute()
            if condition_id:
                refetch_m = supabase.table("polymarket_markets").select("id").eq("condition_id", condition_id).limit(1).execute()
            else:
                refetch_m = supabase.table("polymarket_markets").select("id").eq("event_id", event_id).eq("question", question or "").limit(1).execute()
            if not refetch_m.data or len(refetch_m.data) == 0:
                continue
            market_id = refetch_m.data[0]["id"]
        market_ids.append(market_id)

    return event_id, market_ids


async def add_persona_event(persona_id: str, slug: str) -> dict[str, Any] | None:
    """
    Add a Polymarket event to a persona by slug. Fetches event from Gamma, upserts event+markets,
    links persona, parses each market question with Gemini, and runs term-search analysis.
    """
    from backend.services import persona_service, transcript_service

    gamma = await fetch_event_by_slug(slug)
    if not gamma:
        return None
    event_id, market_ids = _upsert_event_and_markets(gamma)
    if not event_id:
        return None

    supabase = get_supabase()
    # Link persona to event (ignore if already linked)
    try:
        supabase.table("persona_polymarket_events").insert({
            "persona_id": persona_id,
            "polymarket_event_id": event_id,
        }).execute()
    except Exception:
        pass  # unique violation = already linked

    # For each market, parse criteria and upsert market_search_configs
    for market_id in market_ids:
        row = supabase.table("polymarket_markets").select("question").eq("id", market_id).single().execute()
        question = (row.data or {}).get("question") or ""
        criteria = parse_market_criteria(question)
        search_terms = criteria.get("search_terms") or []
        min_count = int(criteria.get("min_count", 0))
        logic = str(criteria.get("logic") or "at_least")

        existing_cfg = supabase.table("market_search_configs").select("id").eq("market_id", market_id).limit(1).execute()
        cfg_row = {
            "market_id": market_id,
            "search_terms": search_terms,
            "min_count": min_count,
            "logic": logic,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if existing_cfg.data and len(existing_cfg.data) > 0:
            supabase.table("market_search_configs").update(cfg_row).eq("market_id", market_id).execute()
        else:
            supabase.table("market_search_configs").insert(cfg_row).execute()

    await update_market_analysis(persona_id, event_id)
    return await get_persona_event_internal(persona_id, event_id)


async def remove_persona_event(persona_id: str, event_id: str) -> bool:
    """Remove the link between a persona and a Polymarket event."""
    supabase = get_supabase()
    result = (
        supabase.table("persona_polymarket_events")
        .delete()
        .eq("persona_id", persona_id)
        .eq("polymarket_event_id", event_id)
        .execute()
    )
    return bool(result.data)


async def get_persona_events(persona_id: str) -> list[dict[str, Any]]:
    """List events linked to a persona with markets and analysis results."""
    supabase = get_supabase()
    links = supabase.table("persona_polymarket_events").select("polymarket_event_id").eq("persona_id", persona_id).execute()
    event_ids = [r["polymarket_event_id"] for r in (links.data or [])]
    result = []
    for eid in event_ids:
        ev = await get_persona_event_internal(persona_id, eid)
        if ev:
            result.append(ev)
    return result


async def get_persona_event_internal(persona_id: str, event_id: str) -> dict[str, Any] | None:
    """Build one PersonaEventWithMarkets-like dict for a single event. Reads term_results from market_term_results."""
    supabase = get_supabase()
    event_row = supabase.table("polymarket_events").select("*").eq("id", event_id).single().execute()
    if not event_row.data:
        return None
    event_data = event_row.data
    markets_rows = supabase.table("polymarket_markets").select("*").eq("event_id", event_id).order("created_at").execute()
    markets_data = markets_rows.data or []
    market_with_analysis = []
    for m in markets_data:
        market_id = m["id"]
        cfg = supabase.table("market_search_configs").select("*").eq("market_id", market_id).limit(1).execute()
        cfg_data = cfg.data[0] if cfg.data and len(cfg.data) > 0 else None
        term_rows = supabase.table("market_term_results").select("*").eq("market_id", market_id).eq("persona_id", persona_id).execute()
        term_results = (term_rows.data or [])
        market_with_analysis.append({
            "market": m,
            "search_config": cfg_data,
            "term_results": [
                {
                    "search_term": r["search_term"],
                    "total_mentions": r["total_mentions"],
                    "briefings_with_term": r["briefings_with_term"],
                    "total_briefings": r["total_briefings"],
                    "percentage": float(r["percentage"]) if r.get("percentage") is not None else 0,
                    "trend": r.get("trend") or "stable",
                    "mentions_by_date": r.get("mentions_by_date") or [],
                    "context_matches": r.get("context_matches") or [],
                    "context_total_matches": r.get("context_total_matches") or 0,
                    "context_transcripts_with_matches": r.get("context_transcripts_with_matches") or 0,
                    "last_updated": r.get("last_updated"),
                }
                for r in term_results
            ],
        })
    return {
        "event": event_data,
        "markets": market_with_analysis,
    }


async def update_market_analysis(persona_id: str, event_id: str) -> None:
    """
    For each market in the event, for each search term: compute frequency + context,
    and upsert into market_term_results.
    """
    from backend.services import persona_service, transcript_service

    supabase = get_supabase()
    markets = supabase.table("polymarket_markets").select("id").eq("event_id", event_id).execute()
    market_ids = [r["id"] for r in (markets.data or [])]

    persona = await persona_service.get_persona_by_id(persona_id)
    aliases = persona.get("aliases", []) if persona else []
    print(f"[update_market_analysis] persona_id={persona_id}, aliases={aliases}")

    persona_transcripts = await persona_service.get_transcripts_for_persona(persona_id)
    transcript_ids = [t["id"] for t in persona_transcripts]
    transcripts = await transcript_service.get_transcripts_by_ids(transcript_ids) if transcript_ids else []
    print(f"[update_market_analysis] full transcripts count={len(transcripts)}")

    for market_id in market_ids:
        cfg = supabase.table("market_search_configs").select("*").eq("market_id", market_id).limit(1).execute()
        cfg_data = cfg.data[0] if cfg.data and len(cfg.data) > 0 else None
        search_terms = (cfg_data.get("search_terms") or []) if cfg_data else []
        if not search_terms:
            continue
        for term in search_terms:
            freq = calculate_term_frequency(transcripts, term, case_sensitive=False, speakers=aliases)
            ctx = search_term_in_context(transcripts, term, context_chars=300, speakers=aliases)
            now = datetime.now(timezone.utc).isoformat()
            supabase.table("market_term_results").upsert({
                "market_id": market_id,
                "persona_id": persona_id,
                "search_term": term,
                "total_mentions": freq.get("total_mentions", 0),
                "briefings_with_term": freq.get("briefings_with_term", 0),
                "total_briefings": freq.get("total_briefings", 0),
                "percentage": freq.get("percentage", 0),
                "trend": freq.get("trend", "stable"),
                "mentions_by_date": freq.get("mentions_by_date", []),
                "context_matches": ctx.get("matches", []),
                "context_total_matches": ctx.get("total_matches", 0),
                "context_transcripts_with_matches": ctx.get("transcripts_with_matches", 0),
                "last_updated": now,
            }, on_conflict="market_id,persona_id,search_term").execute()


async def refresh_persona_event(persona_id: str, event_id: str) -> dict[str, Any] | None:
    """Re-fetch event from Gamma by slug, update markets, re-parse configs, and run analysis."""
    supabase = get_supabase()
    event_row = supabase.table("polymarket_events").select("slug").eq("id", event_id).single().execute()
    if not event_row.data:
        return None
    slug = event_row.data.get("slug")
    if not slug:
        return None
    gamma = await fetch_event_by_slug(slug)
    if not gamma:
        return await get_persona_event_internal(persona_id, event_id)
    _, market_ids = _upsert_event_and_markets(gamma)
    now = datetime.now(timezone.utc).isoformat()
    for market_id in market_ids:
        row = supabase.table("polymarket_markets").select("question").eq("id", market_id).single().execute()
        question = (row.data or {}).get("question") or ""
        criteria = parse_market_criteria(question)
        supabase.table("market_search_configs").upsert({
            "market_id": market_id,
            "search_terms": criteria.get("search_terms") or [],
            "min_count": int(criteria.get("min_count", 0)),
            "logic": criteria.get("logic") or "at_least",
            "updated_at": now,
        }, on_conflict="market_id").execute()
    await update_market_analysis(persona_id, event_id)
    return await get_persona_event_internal(persona_id, event_id)


async def reprocess_persona_markets(persona_id: str) -> None:
    """Reprocess all market analysis for a persona across all linked events."""
    supabase = get_supabase()
    links = supabase.table("persona_polymarket_events").select("polymarket_event_id").eq("persona_id", persona_id).execute()
    event_ids = [r["polymarket_event_id"] for r in (links.data or [])]
    for event_id in event_ids:
        await update_market_analysis(persona_id, event_id)


async def find_affected_persona_ids(speaker_names: list[str]) -> list[str]:
    """Find persona IDs whose aliases match any of the given speaker names (case-insensitive)."""
    if not speaker_names:
        return []
    supabase = get_supabase()
    rows = supabase.table("persona_aliases").select("persona_id, alias").execute()
    aliases_data = rows.data or []
    speaker_lower = [s.strip().lower() for s in speaker_names if s and s.strip()]
    if not speaker_lower:
        return []
    affected: set[str] = set()
    for row in aliases_data:
        alias = (row.get("alias") or "").strip()
        if not alias:
            continue
        alias_lower = alias.lower()
        for sl in speaker_lower:
            if sl == alias_lower or alias_lower in sl or sl in alias_lower:
                affected.add(row["persona_id"])
                break
    return list(affected)


# ----- Series functions -----


async def fetch_series_by_slug(slug: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Fetch a series by slug from Gamma API.
    Returns (series_dict, None) on success, (None, 'not_found') when no match,
    (None, 'api_error') when Gamma API fails (with message in logs).
    """
    slug = (slug or "").strip()
    if not slug:
        return None, "not_found"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{GAMMA_API_BASE}/series",
                params={"slug": slug, "limit": 1},
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0], None
            return None, "not_found"
    except httpx.HTTPStatusError as e:
        print(f"Gamma API HTTP error for series slug {slug}: {e.response.status_code} {e.response.text[:200]}")
        return None, "api_error"
    except Exception as e:
        print(f"Failed to fetch series by slug {slug}: {e}")
        return None, "api_error"


async def fetch_series_by_id(polymarket_id: str) -> dict[str, Any] | None:
    """Fetch a series by Gamma API ID."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GAMMA_API_BASE}/series/{polymarket_id}")
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"Failed to fetch series by id {polymarket_id}: {e}")
        return None


async def search_series(
    query: str,
    active: bool | None = None,
    closed: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Search Gamma series API."""
    try:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if query:
            params["slug"] = query
        if active is not None:
            params["active"] = str(active).lower()
        if closed is not None:
            params["closed"] = str(closed).lower()
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{GAMMA_API_BASE}/series", params=params)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Failed to search series: {e}")
        return []


def _upsert_series(gamma_series: dict[str, Any]) -> str | None:
    """Insert or update polymarket_series from Gamma payload. Returns internal UUID."""
    supabase = get_supabase()
    polymarket_id = gamma_series.get("id") or ""
    slug = (gamma_series.get("slug") or "").strip()
    if not polymarket_id or not slug:
        return None

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "polymarket_id": polymarket_id,
        "slug": slug,
        "title": gamma_series.get("title"),
        "description": gamma_series.get("description"),
        "image": gamma_series.get("image"),
        "icon": gamma_series.get("icon"),
        "series_type": gamma_series.get("seriesType"),
        "recurrence": gamma_series.get("recurrence"),
        "active": gamma_series.get("active", True),
        "closed": gamma_series.get("closed", False),
        "updated_at": now,
    }

    existing = supabase.table("polymarket_series").select("id").eq("polymarket_id", polymarket_id).limit(1).execute()
    if existing.data and len(existing.data) > 0:
        series_id = existing.data[0]["id"]
        supabase.table("polymarket_series").update(row).eq("id", series_id).execute()
        return series_id
    else:
        supabase.table("polymarket_series").insert(row).execute()
        refetch = supabase.table("polymarket_series").select("id").eq("polymarket_id", polymarket_id).limit(1).execute()
        if not refetch.data or len(refetch.data) == 0:
            return None
        return refetch.data[0]["id"]


async def add_series(slug: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Add a series by slug: fetch from Gamma, upsert series, then fetch each event
    individually (to get markets) and upsert.
    Returns (detail_dict, None) on success, (None, error_code) on failure.
    error_code: 'not_found' | 'api_error' | 'db_error'
    """
    gamma_series, fetch_error = await fetch_series_by_slug(slug)
    if fetch_error:
        return None, fetch_error
    if not gamma_series:
        return None, "not_found"

    series_id = _upsert_series(gamma_series)
    if not series_id:
        print(f"add_series: _upsert_series failed for slug={slug}")
        return None, "db_error"

    # Series API returns events WITHOUT nested markets – fetch each individually
    events_list = gamma_series.get("events") or []
    for ev in events_list:
        ev_slug = ev.get("slug")
        if not ev_slug:
            continue
        gamma_event = await fetch_event_by_slug(ev_slug)
        if gamma_event:
            _upsert_event_and_markets(gamma_event, series_id=series_id)

    detail = await get_series_detail(series_id)
    if not detail:
        return None, "db_error"
    return detail, None


async def get_series_detail(series_id: str) -> dict[str, Any] | None:
    """Get series with events and linked persona IDs."""
    supabase = get_supabase()
    series_row = supabase.table("polymarket_series").select("*").eq("id", series_id).single().execute()
    if not series_row.data:
        return None

    events = supabase.table("polymarket_events").select("*").eq("series_id", series_id).order("end_date", desc=True).execute()
    events_data = events.data or []

    # Get linked persona IDs
    links = supabase.table("persona_polymarket_series").select("persona_id").eq("polymarket_series_id", series_id).execute()
    persona_ids = [r["persona_id"] for r in (links.data or [])]

    return {
        "series": series_row.data,
        "events": events_data,
        "persona_ids": persona_ids,
    }


async def get_all_series() -> list[dict[str, Any]]:
    """List all stored series with event counts and persona IDs."""
    supabase = get_supabase()
    series_rows = supabase.table("polymarket_series").select("*").order("updated_at", desc=True).execute()
    result = []
    for s in (series_rows.data or []):
        sid = s["id"]
        events = supabase.table("polymarket_events").select("id").eq("series_id", sid).execute()
        event_count = len(events.data or [])
        links = supabase.table("persona_polymarket_series").select("persona_id").eq("polymarket_series_id", sid).execute()
        persona_ids = [r["persona_id"] for r in (links.data or [])]
        result.append({
            **s,
            "event_count": event_count,
            "persona_ids": persona_ids,
        })
    return result


async def delete_series(series_id: str) -> bool:
    """Delete a stored series (cascades to junction, events set null)."""
    supabase = get_supabase()
    result = supabase.table("polymarket_series").delete().eq("id", series_id).execute()
    return bool(result.data)


async def refresh_series(series_id: str) -> dict[str, Any] | None:
    """Re-fetch series from Gamma, update all events/markets."""
    supabase = get_supabase()
    series_row = supabase.table("polymarket_series").select("polymarket_id").eq("id", series_id).single().execute()
    if not series_row.data:
        return None
    polymarket_id = series_row.data["polymarket_id"]
    gamma_series = await fetch_series_by_id(polymarket_id)
    if not gamma_series:
        return await get_series_detail(series_id)

    _upsert_series(gamma_series)

    events_list = gamma_series.get("events") or []
    for ev in events_list:
        ev_slug = ev.get("slug")
        if not ev_slug:
            continue
        gamma_event = await fetch_event_by_slug(ev_slug)
        if gamma_event:
            _upsert_event_and_markets(gamma_event, series_id=series_id)

    return await get_series_detail(series_id)


async def link_persona_to_series(persona_id: str, series_id: str) -> bool:
    """Link a persona to a series."""
    supabase = get_supabase()
    try:
        supabase.table("persona_polymarket_series").insert({
            "persona_id": persona_id,
            "polymarket_series_id": series_id,
        }).execute()
        return True
    except Exception:
        return False  # already linked


async def unlink_persona_from_series(persona_id: str, series_id: str) -> bool:
    """Unlink a persona from a series."""
    supabase = get_supabase()
    result = (
        supabase.table("persona_polymarket_series")
        .delete()
        .eq("persona_id", persona_id)
        .eq("polymarket_series_id", series_id)
        .execute()
    )
    return bool(result.data)


async def get_personas_for_series(series_id: str) -> list[str]:
    """Get persona IDs linked to a series."""
    supabase = get_supabase()
    links = supabase.table("persona_polymarket_series").select("persona_id").eq("polymarket_series_id", series_id).execute()
    return [r["persona_id"] for r in (links.data or [])]


async def get_series_for_persona(persona_id: str) -> list[dict[str, Any]]:
    """Get series records linked to a persona."""
    supabase = get_supabase()
    links = supabase.table("persona_polymarket_series").select("polymarket_series_id").eq("persona_id", persona_id).execute()
    series_ids = [r["polymarket_series_id"] for r in (links.data or [])]
    result = []
    for sid in series_ids:
        row = supabase.table("polymarket_series").select("*").eq("id", sid).single().execute()
        if row.data:
            result.append(row.data)
    return result


async def get_active_event_for_series(series_id: str) -> dict[str, Any] | None:
    """Get the most recent active event for a series, fallback to most recent closed."""
    supabase = get_supabase()
    # Try active events first (most recent by end_date)
    active = (
        supabase.table("polymarket_events")
        .select("*")
        .eq("series_id", series_id)
        .order("end_date", desc=True)
        .limit(10)
        .execute()
    )
    events = active.data or []
    # Prefer events where markets are still active (check by looking at markets)
    for ev in events:
        markets = supabase.table("polymarket_markets").select("closed").eq("event_id", ev["id"]).execute()
        has_active = any(not m.get("closed", True) for m in (markets.data or []))
        if has_active:
            return ev
    # Fallback to most recent
    return events[0] if events else None


async def get_event_markets(event_id: str) -> dict[str, Any] | None:
    """Get event + markets without persona-specific analysis."""
    supabase = get_supabase()
    event_row = supabase.table("polymarket_events").select("*").eq("id", event_id).single().execute()
    if not event_row.data:
        return None
    markets = supabase.table("polymarket_markets").select("*").eq("event_id", event_id).order("created_at").execute()
    return {
        "event": event_row.data,
        "markets": markets.data or [],
    }


async def get_event_with_analysis(
    event_id: str, persona_id: str | None = None
) -> dict[str, Any] | None:
    """Get event + markets + optional persona analysis."""
    if persona_id:
        return await get_persona_event_internal(persona_id, event_id)
    return await get_event_markets(event_id)


async def refresh_single_event(event_id: str) -> dict[str, Any] | None:
    """Re-fetch a single event from Gamma and update markets."""
    supabase = get_supabase()
    event_row = supabase.table("polymarket_events").select("slug, series_id").eq("id", event_id).single().execute()
    if not event_row.data:
        return None
    slug = event_row.data.get("slug")
    series_id = event_row.data.get("series_id")
    if not slug:
        return None
    gamma = await fetch_event_by_slug(slug)
    if not gamma:
        return await get_event_markets(event_id)
    _upsert_event_and_markets(gamma, series_id=series_id)
    return await get_event_markets(event_id)


async def backfill_series_from_existing_events() -> dict[str, int]:
    """Migration helper: try to associate existing events with series."""
    supabase = get_supabase()
    events = supabase.table("polymarket_events").select("id, slug, series_id").is_("series_id", "null").execute()
    linked = 0
    for ev in (events.data or []):
        slug = ev.get("slug")
        if not slug:
            continue
        gamma = await fetch_event_by_slug(slug)
        if not gamma:
            continue
        # Check if gamma response has series info
        series_slug = gamma.get("seriesSlug") or gamma.get("series_slug")
        if not series_slug:
            continue
        gamma_series, _ = await fetch_series_by_slug(series_slug)
        if not gamma_series:
            continue
        series_id = _upsert_series(gamma_series)
        if series_id:
            supabase.table("polymarket_events").update({"series_id": series_id}).eq("id", ev["id"]).execute()
            linked += 1
    return {"events_linked": linked}
