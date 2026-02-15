"""Polymarket API client service."""

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
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


def extract_base_slug(slug: str) -> str:
    """Strip trailing -NNN numeric suffix from slug for pattern matching."""
    return re.sub(r'-\d+$', '', (slug or "").strip())


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


async def update_market_analysis(persona_id: str, event_id: str, folder_id: str | None = None) -> None:
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
    print(f"[update_market_analysis] persona_id={persona_id}, aliases={aliases}, folder_id={folder_id}")

    persona_transcripts = await persona_service.get_transcripts_for_persona(persona_id, folder_id=folder_id)
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
    event_row = supabase.table("polymarket_events").select("slug, series_id").eq("id", event_id).single().execute()
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
    # Look up folder_id from persona-series link
    folder_id = None
    series_id = event_row.data.get("series_id")
    if series_id:
        link_row = (
            supabase.table("persona_polymarket_series")
            .select("folder_id")
            .eq("persona_id", persona_id)
            .eq("polymarket_series_id", series_id)
            .limit(1)
            .execute()
        )
        folder_id = (link_row.data[0].get("folder_id") if link_row.data else None)
    await update_market_analysis(persona_id, event_id, folder_id=folder_id)
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


async def _fetch_gamma_events(
    active: bool | None = None,
    closed: bool | None = None,
    tag_slug: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Fetch raw events from Gamma events API."""
    try:
        params: dict[str, Any] = {"limit": limit}
        if active is not None:
            params["active"] = str(active).lower()
        if closed is not None:
            params["closed"] = str(closed).lower()
        if tag_slug:
            params["tag_slug"] = tag_slug
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{GAMMA_API_BASE}/events", params=params)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"Failed to fetch gamma events: {e}")
        return []


async def _fetch_gamma_events_paginated(
    closed: bool | None = None,
    tag_slug: str | None = None,
    limit: int = 100,
    max_pages: int = 10,
) -> list[dict[str, Any]]:
    """Paginated wrapper around GET /events with offset for large result sets."""
    all_events: list[dict[str, Any]] = []
    for page in range(max_pages):
        offset = page * limit
        try:
            params: dict[str, Any] = {"limit": limit, "offset": offset}
            if closed is not None:
                params["closed"] = str(closed).lower()
            if tag_slug:
                params["tag_slug"] = tag_slug
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{GAMMA_API_BASE}/events", params=params)
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, list) or len(data) == 0:
                    break
                all_events.extend(data)
                if len(data) < limit:
                    break  # last page
        except Exception as e:
            print(f"Failed to fetch gamma events page {page}: {e}")
            break
    return all_events


async def discover_series() -> list[dict[str, Any]]:
    """
    Discover mention-market events from Gamma using the mention-markets tag.
    Each event is returned as a potential series to add.
    """
    events = await _fetch_gamma_events(
        closed=False, tag_slug="mention-markets", limit=50,
    )
    result = []
    for ev in events:
        markets = ev.get("markets") or []
        result.append({
            "slug": ev.get("slug") or "",
            "title": ev.get("title") or ev.get("slug") or "",
            "image": ev.get("image"),
            "event_count": 1,
            "market_count": len(markets),
            "active": not ev.get("closed", False),
            "closed": ev.get("closed", False),
        })
    return result


def _upsert_series_from_events(
    slug: str,
    gamma_events: list[dict[str, Any]],
) -> str | None:
    """
    Build and upsert a polymarket_series record from event data (not from /series API).
    Uses the slug as the polymarket_id since we don't have a real series ID.
    Returns internal UUID.
    """
    supabase = get_supabase()
    slug = (slug or "").strip()
    if not slug or not gamma_events:
        return None

    # Derive series metadata from the first event
    first = gamma_events[0]
    title = first.get("groupItemTitle") or first.get("title") or slug
    image = first.get("image")

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "polymarket_id": slug,  # use slug as stable ID
        "slug": slug,
        "title": title,
        "image": image,
        "active": any(ev.get("active", False) for ev in gamma_events),
        "closed": all(ev.get("closed", False) for ev in gamma_events),
        "base_slug": extract_base_slug(slug),
        "updated_at": now,
    }

    existing = supabase.table("polymarket_series").select("id").eq("slug", slug).limit(1).execute()
    if existing.data and len(existing.data) > 0:
        series_id = existing.data[0]["id"]
        supabase.table("polymarket_series").update(row).eq("id", series_id).execute()
        return series_id
    else:
        supabase.table("polymarket_series").insert(row).execute()
        refetch = supabase.table("polymarket_series").select("id").eq("slug", slug).limit(1).execute()
        if not refetch.data or len(refetch.data) == 0:
            return None
        return refetch.data[0]["id"]


async def add_series(slug: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Add a mention-market event as a series.
    Fetches the event by slug from Gamma, creates a series wrapper, upserts event+markets.
    """
    slug = (slug or "").strip()
    if not slug:
        return None, "not_found"

    # Fetch the event by slug (Gamma events/slug endpoint includes markets)
    gamma_event = await fetch_event_by_slug(slug)
    if not gamma_event:
        return None, "not_found"

    # Create a series wrapper from this single event
    series_id = _upsert_series_from_events(slug, [gamma_event])
    if not series_id:
        return None, "db_error"

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

    # Get linked persona IDs with folder_id and auto_trade
    links = supabase.table("persona_polymarket_series").select("persona_id, folder_id, auto_trade").eq("polymarket_series_id", series_id).execute()
    persona_ids = [r["persona_id"] for r in (links.data or [])]
    # Map persona_id → folder_id for transcript scoping
    persona_folder_map = {r["persona_id"]: r.get("folder_id") for r in (links.data or [])}
    # Map persona_id → auto_trade flag
    persona_auto_trade_map = {r["persona_id"]: r.get("auto_trade", False) for r in (links.data or [])}

    return {
        "series": series_row.data,
        "events": events_data,
        "persona_ids": persona_ids,
        "persona_folder_map": persona_folder_map,
        "persona_auto_trade_map": persona_auto_trade_map,
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
        links = supabase.table("persona_polymarket_series").select("persona_id, auto_trade").eq("polymarket_series_id", sid).execute()
        persona_ids = [r["persona_id"] for r in (links.data or [])]
        persona_auto_trade_map = {r["persona_id"]: r.get("auto_trade", False) for r in (links.data or [])}
        result.append({
            **s,
            "event_count": event_count,
            "persona_ids": persona_ids,
            "persona_auto_trade_map": persona_auto_trade_map,
        })
    return result


async def delete_series(series_id: str) -> bool:
    """Delete a stored series (cascades to junction, events set null)."""
    supabase = get_supabase()
    result = supabase.table("polymarket_series").delete().eq("id", series_id).execute()
    return bool(result.data)


async def refresh_series(series_id: str) -> dict[str, Any] | None:
    """Re-fetch the event from Gamma and update markets."""
    supabase = get_supabase()
    series_row = supabase.table("polymarket_series").select("slug").eq("id", series_id).single().execute()
    if not series_row.data:
        return None
    slug = series_row.data["slug"]

    gamma_event = await fetch_event_by_slug(slug)
    if gamma_event:
        _upsert_series_from_events(slug, [gamma_event])
        _upsert_event_and_markets(gamma_event, series_id=series_id)

    return await get_series_detail(series_id)


async def link_persona_to_series(
    persona_id: str, series_id: str, folder_id: str | None = None, auto_trade: bool = False,
) -> bool:
    """Link a persona to a series, optionally scoped to a folder."""
    supabase = get_supabase()
    try:
        row = {
            "persona_id": persona_id,
            "polymarket_series_id": series_id,
            "auto_trade": auto_trade,
        }
        if folder_id:
            row["folder_id"] = folder_id
        supabase.table("persona_polymarket_series").insert(row).execute()
        return True
    except Exception:
        return False  # already linked


async def set_auto_trade(persona_id: str, series_id: str, enabled: bool) -> bool:
    """Toggle auto_trade on a persona-series link."""
    supabase = get_supabase()
    result = (
        supabase.table("persona_polymarket_series")
        .update({"auto_trade": enabled})
        .eq("persona_id", persona_id)
        .eq("polymarket_series_id", series_id)
        .execute()
    )
    return bool(result.data)


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
    """Get series records linked to a persona, including auto_trade flag."""
    supabase = get_supabase()
    links = supabase.table("persona_polymarket_series").select("polymarket_series_id, auto_trade").eq("persona_id", persona_id).execute()
    link_map = {r["polymarket_series_id"]: r.get("auto_trade", False) for r in (links.data or [])}
    result = []
    for sid, auto_trade in link_map.items():
        row = supabase.table("polymarket_series").select("*").eq("id", sid).single().execute()
        if row.data:
            result.append({**row.data, "auto_trade": auto_trade})
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
    """Re-fetch a single event from Gamma, update markets, and re-run analysis for linked personas."""
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

    # Re-run analysis for all personas linked to this event's series
    if series_id:
        links = supabase.table("persona_polymarket_series").select("persona_id, folder_id").eq("polymarket_series_id", series_id).execute()
        for link in (links.data or []):
            persona_id = link["persona_id"]
            folder_id = link.get("folder_id")
            await update_market_analysis(persona_id, event_id, folder_id=folder_id)

    return await get_event_markets(event_id)


async def backfill_series_from_existing_events() -> dict[str, int]:
    """Migration helper: wrap each orphan event in a series record."""
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
        series_id = _upsert_series_from_events(slug, [gamma])
        if series_id:
            supabase.table("polymarket_events").update({"series_id": series_id}).eq("id", ev["id"]).execute()
            linked += 1
    return {"events_linked": linked}


# ----- Date extraction utilities -----


# Patterns for extracting dates from transcript titles
_DATE_PATTERNS = [
    # "4 February 2026", "12 Jan 2025"
    (re.compile(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{4})', re.IGNORECASE),
     lambda m: _parse_dmy(m.group(1), m.group(2), m.group(3))),
    # "January 4, 2026", "Jan. 31, 2025", "Feb 3, 2025", "March 12 2025"
    (re.compile(r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.?\s+(\d{1,2}),?\s+(\d{4})', re.IGNORECASE),
     lambda m: _parse_dmy(m.group(2), m.group(1), m.group(3))),
    # "2025-01-31", "2025/01/31"
    (re.compile(r'(\d{4})[-/](\d{2})[-/](\d{2})'),
     lambda m: _parse_ymd(m.group(1), m.group(2), m.group(3))),
    # "01/31/2025", "1/31/2025"
    (re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})'),
     lambda m: _parse_mdy(m.group(1), m.group(2), m.group(3))),
]

_MONTH_MAP = {
    'january': 1, 'jan': 1, 'february': 2, 'feb': 2, 'march': 3, 'mar': 3,
    'april': 4, 'apr': 4, 'may': 5, 'june': 6, 'jun': 6,
    'july': 7, 'jul': 7, 'august': 8, 'aug': 8, 'september': 9, 'sep': 9,
    'october': 10, 'oct': 10, 'november': 11, 'nov': 11, 'december': 12, 'dec': 12,
}


def _parse_dmy(day: str, month_str: str, year: str) -> str | None:
    month = _MONTH_MAP.get(month_str.rstrip('.').lower())
    if not month:
        return None
    try:
        dt = datetime(int(year), month, int(day))
        return dt.strftime("%Y%m%d")
    except ValueError:
        return None


def _parse_ymd(year: str, month: str, day: str) -> str | None:
    try:
        dt = datetime(int(year), int(month), int(day))
        return dt.strftime("%Y%m%d")
    except ValueError:
        return None


def _parse_mdy(month: str, day: str, year: str) -> str | None:
    try:
        dt = datetime(int(year), int(month), int(day))
        return dt.strftime("%Y%m%d")
    except ValueError:
        return None


def extract_date_from_title(title: str) -> str | None:
    """Extract a date (YYYYMMDD) from a transcript title using common patterns."""
    if not title:
        return None
    for pattern, parser in _DATE_PATTERNS:
        m = pattern.search(title)
        if m:
            result = parser(m)
            if result:
                return result
    return None


def _get_transcript_date(t: dict[str, Any]) -> str | None:
    """Get a transcript's date as YYYYMMDD: prefer upload_date, fall back to title extraction."""
    upload_date = t.get("upload_date") or ""
    if len(upload_date) == 8:
        return upload_date
    return extract_date_from_title(t.get("name") or "")


def filter_transcripts_by_event_week(
    transcripts: list[dict[str, Any]],
    end_date_str: str | None,
) -> list[dict[str, Any]]:
    """
    Keep only transcripts whose date falls within [end_date - 7 days, end_date].
    Date is resolved from upload_date first, then extracted from the transcript title.
    """
    if not end_date_str:
        return transcripts

    try:
        end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return transcripts

    start_dt = end_dt - timedelta(days=7)
    start_yyyymmdd = start_dt.strftime("%Y%m%d")
    end_yyyymmdd = end_dt.strftime("%Y%m%d")

    filtered = []
    for t in transcripts:
        t_date = _get_transcript_date(t)
        if t_date and start_yyyymmdd <= t_date <= end_yyyymmdd:
            filtered.append(t)

    print(f"[filter_transcripts_by_event_week] {len(filtered)}/{len(transcripts)} transcripts in week {start_yyyymmdd}-{end_yyyymmdd}")
    return filtered


async def fetch_past_events_for_series(series_id: str) -> dict[str, Any]:
    """
    Fetch closed mention-market events matching the series base_slug from Gamma.
    Uses bulk event data directly (no per-event API calls).
    Returns { added, total_matching, base_slug }.
    """
    supabase = get_supabase()
    series_row = supabase.table("polymarket_series").select("slug, base_slug").eq("id", series_id).single().execute()
    if not series_row.data:
        return {"added": 0, "total_matching": 0, "base_slug": None}

    slug = series_row.data["slug"]
    base_slug = series_row.data.get("base_slug") or extract_base_slug(slug)

    # Update base_slug if not set
    if not series_row.data.get("base_slug"):
        supabase.table("polymarket_series").update({"base_slug": base_slug}).eq("id", series_id).execute()

    # Fetch all closed mention-market events
    closed_events = await _fetch_gamma_events_paginated(
        closed=True, tag_slug="mention-markets", limit=100, max_pages=10,
    )

    # Filter to events whose base slug matches
    matching = [
        ev for ev in closed_events
        if extract_base_slug(ev.get("slug") or "") == base_slug
    ]

    added = 0
    for gamma_event in matching:
        event_id, market_ids = _upsert_event_and_markets(gamma_event, series_id=series_id)
        if not event_id:
            continue

        # Parse market_search_configs for new markets
        now = datetime.now(timezone.utc).isoformat()
        for market_id in market_ids:
            existing_cfg = supabase.table("market_search_configs").select("id").eq("market_id", market_id).limit(1).execute()
            if existing_cfg.data and len(existing_cfg.data) > 0:
                continue  # already has config
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
        added += 1

    return {"added": added, "total_matching": len(matching), "base_slug": base_slug}


