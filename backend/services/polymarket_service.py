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
from backend.utils.nlp import calculate_term_frequency


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


def _upsert_event_and_markets(gamma_event: dict[str, Any]) -> tuple[str | None, list[str]]:
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

    # Upsert event (by slug)
    existing = supabase.table("polymarket_events").select("id").eq("slug", slug).limit(1).execute()
    now = datetime.now(timezone.utc).isoformat()
    if existing.data and len(existing.data) > 0:
        event_id = existing.data[0]["id"]
        supabase.table("polymarket_events").update({
            "title": title,
            "image": image,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "updated_at": now,
        }).eq("id", event_id).execute()
    else:
        supabase.table("polymarket_events").insert({
            "slug": slug,
            "title": title,
            "image": image,
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
        }).execute()
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
    """Build one PersonaEventWithMarkets-like dict for a single event."""
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
        res = supabase.table("market_search_results").select("*").eq("market_id", market_id).eq("persona_id", persona_id).limit(1).execute()
        res_data = res.data[0] if res.data and len(res.data) > 0 else None
        market_with_analysis.append({
            "market": m,
            "search_config": cfg_data,
            "result_count": res_data.get("count") if res_data else None,
            "result_last_updated": res_data.get("last_updated") if res_data else None,
            "result_briefings_with_term": res_data.get("briefings_with_term") if res_data else None,
            "result_total_briefings": res_data.get("total_briefings") if res_data else None,
            "result_percentage": res_data.get("percentage") if res_data else None,
            "result_trend": res_data.get("trend") if res_data else None,
            "result_mentions_by_date": res_data.get("mentions_by_date") if res_data else None,
        })
    return {
        "event": event_data,
        "markets": market_with_analysis,
    }


async def update_market_analysis(persona_id: str, event_id: str) -> None:
    """
    For each market in the event, get persona's transcripts, run term search (first search term),
    and upsert market_search_results.
    """
    from backend.services import persona_service, transcript_service

    supabase = get_supabase()
    markets = supabase.table("polymarket_markets").select("id").eq("event_id", event_id).execute()
    market_ids = [r["id"] for r in (markets.data or [])]

    # Get persona to check aliases
    persona = await persona_service.get_persona_by_id(persona_id)
    aliases = persona.get("aliases", []) if persona else []
    print(f"[update_market_analysis] persona_id={persona_id}, aliases={aliases}")

    persona_transcripts = await persona_service.get_transcripts_for_persona(persona_id)
    print(f"[update_market_analysis] persona_transcripts count={len(persona_transcripts)}")

    transcript_ids = [t["id"] for t in persona_transcripts]
    transcripts = await transcript_service.get_transcripts_by_ids(transcript_ids) if transcript_ids else []
    print(f"[update_market_analysis] full transcripts count={len(transcripts)}")

    for market_id in market_ids:
        cfg = supabase.table("market_search_configs").select("*").eq("market_id", market_id).limit(1).execute()
        cfg_data = cfg.data[0] if cfg.data and len(cfg.data) > 0 else None
        search_terms = (cfg_data.get("search_terms") or []) if cfg_data else []
        min_count = int(cfg_data.get("min_count", 0)) if cfg_data else 0
        primary_term = search_terms[0] if search_terms else ""
        print(f"[update_market_analysis] market_id={market_id}, search_terms={search_terms}, primary_term='{primary_term}'")

        if not primary_term:
            freq = {
                "total_mentions": 0,
                "briefings_with_term": 0,
                "total_briefings": len(transcripts),
                "percentage": 0,
                "trend": "stable",
                "mentions_by_date": []
            }
            print(f"[update_market_analysis] No primary_term, setting count=0")
        else:
            # Filter to only count mentions from the persona's speakers (aliases)
            freq = calculate_term_frequency(transcripts, primary_term, case_sensitive=False, speakers=aliases)
            print(f"[update_market_analysis] term='{primary_term}', speakers={aliases}, count={freq.get('total_mentions', 0)}, briefings_with_term={freq.get('briefings_with_term', 0)}")

        now = datetime.now(timezone.utc).isoformat()
        supabase.table("market_search_results").upsert({
            "market_id": market_id,
            "persona_id": persona_id,
            "count": freq.get("total_mentions", 0),
            "briefings_with_term": freq.get("briefings_with_term", 0),
            "total_briefings": freq.get("total_briefings", 0),
            "percentage": freq.get("percentage", 0),
            "trend": freq.get("trend", "stable"),
            "mentions_by_date": freq.get("mentions_by_date", []),
            "last_updated": now,
        }, on_conflict="market_id,persona_id").execute()


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
