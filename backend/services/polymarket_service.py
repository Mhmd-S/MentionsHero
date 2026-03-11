"""Polymarket API client and service layer."""

import json
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.core.database import get_supabase
from backend.services.kalshi_service import parse_market_criteria
from backend.utils.nlp import calculate_term_frequency, search_term_in_context, group_nearby_mentions


POLY_API_BASE = "https://gamma-api.polymarket.com"

# Brief cache of search results so add_event can skip re-fetching
_search_cache: dict[str, dict[str, Any]] = {}
_SEARCH_CACHE_MAX = 200


# ----- Helpers -----


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _parse_numeric(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _parse_json_string(s: str | None) -> list | None:
    """Parse a JSON-encoded string like '[\"Yes\", \"No\"]' into a list."""
    if not s:
        return None
    try:
        parsed = json.loads(s)
        return parsed if isinstance(parsed, list) else None
    except (json.JSONDecodeError, TypeError):
        return None


def _derive_result(market_data: dict[str, Any]) -> str | None:
    """
    Derive market resolution from closed status + outcomePrices.
    outcomePrices is a JSON string like '["1", "0"]' for resolved markets.
    """
    if not market_data.get("closed"):
        return None
    raw = market_data.get("outcomePrices")
    prices = _parse_json_string(raw) if isinstance(raw, str) else raw
    if not prices or len(prices) < 2:
        return None
    try:
        p0 = float(prices[0])
        p1 = float(prices[1])
    except (ValueError, TypeError):
        return None
    if p0 >= 0.99:
        return "yes"
    if p1 >= 0.99:
        return "no"
    return None


def _clean_search_term(term: str) -> str:
    """Strip trailing numeric threshold patterns like '7+', '10+ times' from a term."""
    return re.sub(r'\s+\d+\+?\s*(times?)?\s*$', '', term, flags=re.IGNORECASE).strip()


def _extract_poly_search_terms(market_data: dict[str, Any]) -> list[str]:
    """
    Extract search terms from a Polymarket market.
    Prefers groupItemTitle, falls back to regex parsing of question.
    """
    group_title = (market_data.get("groupItemTitle") or market_data.get("group_item_title") or "").strip()
    if group_title:
        # Split on " / " for compound terms, same as Kalshi
        terms = [_clean_search_term(t) for t in group_title.split(" / ")]
        return [t for t in terms if t]
    question = market_data.get("question") or ""
    criteria = parse_market_criteria(question)
    return criteria.get("search_terms") or []


def extract_slug_from_url(input_str: str) -> str:
    """Extract slug from a Polymarket URL or return input as-is."""
    input_str = input_str.strip()
    match = re.search(r'polymarket\.com/event/([^/?#]+)', input_str)
    if match:
        return match.group(1)
    return input_str


# ----- Polymarket API client -----


def _is_mentions_event(ev: dict[str, Any]) -> bool:
    """Check if an event is a mentions-style market (someone says/mentions a word)."""
    title = (ev.get("title") or "").lower()
    desc = (ev.get("description") or "").lower()[:500]
    questions = " ".join(
        (m.get("question") or "").lower() for m in (ev.get("markets") or [])
    )
    text = f"{title} {desc} {questions}"
    # Mentions patterns commonly used in prediction market questions
    mentions_patterns = [
        ' say "', ' say "', ' say "',  # straight & curly quotes
        " mention ", " mentions ", " mentioned ",
        " says ", " said ",
        " use the word", " use the term",
        " utter ", " tweet ", " tweets ",
        " speak about ", " talk about ",
        "will say", "what will",
    ]
    return any(p in text for p in mentions_patterns)


async def search_events(
    query: str, limit: int = 20, mentions_only: bool = True
) -> list[dict[str, Any]]:
    """
    Search Polymarket for events using the public-search endpoint.
    Optionally filtered to mentions-style markets client-side.
    """
    query = (query or "").strip()
    if not query:
        return []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{POLY_API_BASE}/public-search",
                params={
                    "q": query,
                    "limit_per_type": limit * 3 if mentions_only else limit,
                    "events_status": "active",
                },
            )
            response.raise_for_status()
            data = response.json()

        events = data.get("events") or []

        # Cache all returned events by slug for fast add_event later
        if len(_search_cache) > _SEARCH_CACHE_MAX:
            _search_cache.clear()
        for ev in events:
            slug = ev.get("slug")
            if slug:
                _search_cache[slug] = ev

        results: list[dict[str, Any]] = []
        for ev in events:
            # Skip closed/inactive events (safety net beyond API filter)
            if ev.get("closed") or not ev.get("active", True):
                continue
            if mentions_only and not _is_mentions_event(ev):
                continue
            results.append(ev)
            if len(results) >= limit:
                break
        return results
    except Exception as e:
        print(f"[polymarket] search_events error: {e}")
        return []


async def search_all_events(query: str, limit: int = 20) -> list[dict[str, Any]]:
    """Search without mentions filter (for admin flexibility)."""
    return await search_events(query, limit=limit, mentions_only=False)


async def fetch_event_by_slug(slug: str) -> dict[str, Any] | None:
    """Fetch a single event by slug from Polymarket Gamma API."""
    slug = (slug or "").strip()
    if not slug:
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{POLY_API_BASE}/events/slug/{slug}")
            response.raise_for_status()
            data = response.json()
            # The slug endpoint returns the event directly (not a list)
            if isinstance(data, dict) and data.get("id"):
                return data
            # Some endpoints return a list
            if isinstance(data, list) and data:
                return data[0]
            return None
    except Exception as e:
        print(f"[polymarket] fetch_event_by_slug error: {e}")
        return None


async def fetch_event_by_poly_id(poly_id: str) -> dict[str, Any] | None:
    """Fetch a single event by its Polymarket numeric ID."""
    poly_id = (poly_id or "").strip()
    if not poly_id:
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{POLY_API_BASE}/events",
                params={"id": poly_id},
            )
            response.raise_for_status()
            data = response.json()
            if isinstance(data, list) and data:
                return data[0]
            if isinstance(data, dict) and data.get("id"):
                return data
            return None
    except Exception as e:
        print(f"[polymarket] fetch_event_by_poly_id error: {e}")
        return None


# ----- Database upsert operations -----


def _upsert_event(api_event: dict[str, Any]) -> str | None:
    """Upsert a poly_events record from API data. Returns internal UUID."""
    supabase = get_supabase()
    poly_id = str(api_event.get("id") or "").strip()
    slug = (api_event.get("slug") or "").strip()
    if not poly_id or not slug:
        return None

    now = datetime.now(timezone.utc).isoformat()
    start_date = _parse_iso(api_event.get("startDate"))
    end_date = _parse_iso(api_event.get("endDate"))

    row = {
        "poly_id": poly_id,
        "slug": slug,
        "title": api_event.get("title"),
        "description": api_event.get("description"),
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "active": api_event.get("active", True),
        "closed": api_event.get("closed", False),
        "volume": _parse_numeric(api_event.get("volume")),
        "liquidity": _parse_numeric(api_event.get("liquidity")),
        "image": api_event.get("image"),
        "neg_risk": api_event.get("negRisk", False),
        "updated_at": now,
    }

    supabase.table("poly_events").upsert(row, on_conflict="poly_id").execute()
    refetch = supabase.table("poly_events").select("id").eq("poly_id", poly_id).limit(1).execute()
    if refetch.data and len(refetch.data) > 0:
        return refetch.data[0]["id"]
    return None


def _upsert_markets(api_event: dict[str, Any], event_id: str) -> list[str]:
    """Upsert poly_markets from nested markets in API event. Returns list of market UUIDs."""
    supabase = get_supabase()
    markets_payload = api_event.get("markets") or []
    if not isinstance(markets_payload, list):
        markets_payload = []

    now = datetime.now(timezone.utc).isoformat()

    # Build all market rows for batch upsert
    market_rows: list[dict[str, Any]] = []
    search_term_map: dict[str, list[str]] = {}  # poly_id -> search_terms

    for m in markets_payload:
        poly_id = str(m.get("id") or "").strip()
        if not poly_id:
            continue

        outcome_prices = _parse_json_string(m.get("outcomePrices")) if isinstance(m.get("outcomePrices"), str) else m.get("outcomePrices")
        outcomes = _parse_json_string(m.get("outcomes")) if isinstance(m.get("outcomes"), str) else m.get("outcomes")
        closed_time = _parse_iso(m.get("closedTime"))
        result = _derive_result(m)

        market_rows.append({
            "poly_id": poly_id,
            "event_id": event_id,
            "slug": m.get("slug"),
            "question": m.get("question"),
            "group_item_title": m.get("groupItemTitle"),
            "outcome_prices": outcome_prices,
            "outcomes": outcomes,
            "last_trade_price": _parse_numeric(m.get("lastTradePrice")),
            "one_day_price_change": _parse_numeric(m.get("oneDayPriceChange")),
            "volume": _parse_numeric(m.get("volume")),
            "active": m.get("active", True),
            "closed": m.get("closed", False),
            "closed_time": closed_time.isoformat() if closed_time else None,
            "neg_risk": m.get("negRisk", False),
            "result": result,
            "updated_at": now,
        })

        search_terms = _extract_poly_search_terms(m)
        if search_terms:
            search_term_map[poly_id] = search_terms

    if not market_rows:
        return []

    # Batch upsert all markets in one call
    supabase.table("poly_markets").upsert(
        market_rows, on_conflict="poly_id"
    ).execute()

    # Fetch back IDs for all upserted markets
    poly_ids = [r["poly_id"] for r in market_rows]
    refetch = supabase.table("poly_markets").select("id, poly_id").in_("poly_id", poly_ids).execute()

    market_ids: list[str] = []
    config_rows: list[dict[str, Any]] = []

    for row in (refetch.data or []):
        market_ids.append(row["id"])
        terms = search_term_map.get(row["poly_id"])
        if terms:
            config_rows.append({
                "market_id": row["id"],
                "search_terms": terms,
                "min_count": 0,
                "logic": "any",
                "updated_at": now,
            })

    # Batch upsert all search configs in one call
    if config_rows:
        supabase.table("poly_market_search_configs").upsert(
            config_rows, on_conflict="market_id"
        ).execute()

    return market_ids


# ----- Event management -----


async def add_event(slug: str, api_data: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Add a Polymarket event by slug. Uses cache/provided data or fetches from API."""
    slug = extract_slug_from_url(slug)
    if not slug:
        return None

    api_event = api_data or _search_cache.pop(slug, None) or await fetch_event_by_slug(slug)
    if not api_event:
        return None

    event_id = _upsert_event(api_event)
    if not event_id:
        return None

    _upsert_markets(api_event, event_id)
    return await get_event_detail(event_id)


async def get_stored_events() -> list[dict[str, Any]]:
    """List all stored Polymarket events with market counts and linked persona IDs."""
    supabase = get_supabase()
    events = supabase.table("poly_events").select("*").order("updated_at", desc=True).execute()
    event_ids = [ev["id"] for ev in (events.data or [])]
    if not event_ids:
        return []

    # Batch fetch all markets and persona links in 2 calls instead of 2*N
    all_markets = supabase.table("poly_markets").select("id, event_id").in_("event_id", event_ids).execute()
    all_links = supabase.table("persona_poly_events").select("persona_id, poly_event_id").in_("poly_event_id", event_ids).execute()

    # Build lookup maps
    market_counts: dict[str, int] = {}
    for m in (all_markets.data or []):
        market_counts[m["event_id"]] = market_counts.get(m["event_id"], 0) + 1

    persona_map: dict[str, list[str]] = {}
    for link in (all_links.data or []):
        persona_map.setdefault(link["poly_event_id"], []).append(link["persona_id"])

    return [
        {
            **ev,
            "market_count": market_counts.get(ev["id"], 0),
            "persona_ids": persona_map.get(ev["id"], []),
        }
        for ev in (events.data or [])
    ]


async def get_event_detail(event_id: str, persona_id: str | None = None) -> dict[str, Any] | None:
    """Get event + markets + optional persona analysis."""
    supabase = get_supabase()
    event_row = supabase.table("poly_events").select("*").eq("id", event_id).single().execute()
    if not event_row.data:
        return None

    # Get linked personas
    links = supabase.table("persona_poly_events").select("persona_id").eq("poly_event_id", event_id).execute()
    persona_ids = [r["persona_id"] for r in (links.data or [])]

    # Get markets
    markets_rows = supabase.table("poly_markets").select("*").eq("event_id", event_id).order("created_at").execute()
    markets_data = markets_rows.data or []

    if persona_id and markets_data:
        market_ids = [m["id"] for m in markets_data]

        # Batch fetch all configs and term results in 2 calls instead of 2*N
        all_configs = supabase.table("poly_market_search_configs").select("*").in_("market_id", market_ids).execute()
        all_terms = supabase.table("poly_market_term_results").select("*").in_("market_id", market_ids).eq("persona_id", persona_id).execute()

        # Build lookup maps
        config_map: dict[str, dict] = {c["market_id"]: c for c in (all_configs.data or [])}
        terms_map: dict[str, list[dict]] = {}
        for r in (all_terms.data or []):
            terms_map.setdefault(r["market_id"], []).append(r)

        market_with_analysis = []
        for m in markets_data:
            mid = m["id"]
            market_with_analysis.append({
                "market": m,
                "search_config": config_map.get(mid),
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
                    for r in terms_map.get(mid, [])
                ],
            })
        return {
            "event": event_row.data,
            "markets": market_with_analysis,
            "persona_ids": persona_ids,
        }
    else:
        return {
            "event": event_row.data,
            "markets": markets_data,
            "persona_ids": persona_ids,
        }


async def refresh_event(event_id: str) -> dict[str, Any] | None:
    """Re-fetch event from Polymarket, upsert, re-run analysis for linked personas."""
    supabase = get_supabase()
    event_row = supabase.table("poly_events").select("slug").eq("id", event_id).single().execute()
    if not event_row.data:
        return None
    slug = event_row.data.get("slug")
    if not slug:
        return None

    api_event = await fetch_event_by_slug(slug)
    if not api_event:
        return await get_event_detail(event_id)

    _upsert_event(api_event)
    market_ids = _upsert_markets(api_event, event_id)

    # Rebuild search configs
    now = datetime.now(timezone.utc).isoformat()
    if market_ids:
        all_market_rows = supabase.table("poly_markets").select("id, question, group_item_title").in_("id", market_ids).execute()
        market_data_map = {r["id"]: r for r in (all_market_rows.data or [])}
        for market_id in market_ids:
            data = market_data_map.get(market_id, {})
            search_terms = _extract_poly_search_terms(data)
            supabase.table("poly_market_search_configs").upsert({
                "market_id": market_id,
                "search_terms": search_terms,
                "min_count": 0,
                "logic": "any",
                "updated_at": now,
            }, on_conflict="market_id").execute()

    # Re-run analysis for all linked personas
    links = supabase.table("persona_poly_events").select("persona_id, folder_id").eq("poly_event_id", event_id).execute()
    for link in (links.data or []):
        await update_poly_market_analysis(link["persona_id"], event_id, folder_id=link.get("folder_id"))

    return await get_event_detail(event_id)


async def delete_event(event_id: str) -> bool:
    """Delete a stored Polymarket event (cascades markets, configs, results)."""
    supabase = get_supabase()
    result = supabase.table("poly_events").delete().eq("id", event_id).execute()
    return bool(result.data)


# ----- Persona linking -----


async def link_persona(persona_id: str, event_id: str, folder_id: str | None = None) -> bool:
    """Link a persona to a Polymarket event, optionally scoped to a folder."""
    supabase = get_supabase()
    try:
        row: dict[str, Any] = {
            "persona_id": persona_id,
            "poly_event_id": event_id,
        }
        if folder_id:
            row["folder_id"] = folder_id
        supabase.table("persona_poly_events").insert(row).execute()

        # Run initial analysis
        folder = folder_id
        await update_poly_market_analysis(persona_id, event_id, folder_id=folder)
        return True
    except Exception:
        return False  # already linked


async def unlink_persona(persona_id: str, event_id: str) -> bool:
    """Unlink a persona from a Polymarket event."""
    supabase = get_supabase()
    result = (
        supabase.table("persona_poly_events")
        .delete()
        .eq("persona_id", persona_id)
        .eq("poly_event_id", event_id)
        .execute()
    )
    return bool(result.data)


async def get_personas_for_event(event_id: str) -> list[str]:
    """Get persona IDs linked to a Polymarket event."""
    supabase = get_supabase()
    links = supabase.table("persona_poly_events").select("persona_id").eq("poly_event_id", event_id).execute()
    return [r["persona_id"] for r in (links.data or [])]


# ----- Market analysis -----


async def update_poly_market_analysis(persona_id: str, event_id: str, folder_id: str | None = None) -> None:
    """
    For each market in the event, for each search term: compute frequency + context,
    and upsert into poly_market_term_results.
    """
    from backend.services import persona_service, transcript_service

    supabase = get_supabase()
    markets = supabase.table("poly_markets").select("id").eq("event_id", event_id).execute()
    market_ids = [r["id"] for r in (markets.data or [])]

    persona = await persona_service.get_persona_by_id(persona_id)
    aliases = persona.get("aliases", []) if persona else []
    print(f"[update_poly_market_analysis] persona_id={persona_id}, aliases={aliases}, folder_id={folder_id}")

    persona_transcripts = await persona_service.get_transcripts_for_persona(persona_id, folder_id=folder_id)
    transcript_ids = [t["id"] for t in persona_transcripts]
    transcripts = await transcript_service.get_transcripts_by_ids(transcript_ids) if transcript_ids else []
    print(f"[update_poly_market_analysis] full transcripts count={len(transcripts)}")

    all_configs = supabase.table("poly_market_search_configs").select("*").in_("market_id", market_ids).execute()
    config_map: dict[str, dict] = {c["market_id"]: c for c in (all_configs.data or [])}

    for market_id in market_ids:
        cfg_data = config_map.get(market_id)
        search_terms = (cfg_data.get("search_terms") or []) if cfg_data else []
        if not search_terms:
            continue
        for term in search_terms:
            freq = calculate_term_frequency(transcripts, term, case_sensitive=False, speakers=aliases)
            ctx = search_term_in_context(transcripts, term, context_chars=300, speakers=aliases)
            grouped = group_nearby_mentions(ctx.get("matches", []))
            context_matches = [
                {
                    "transcript_id": g["transcript_id"],
                    "transcript_name": g["transcript_name"],
                    "date": g.get("date"),
                    "context": g["merged_context"],
                    "position": g["positions"][0] if g.get("positions") else 0,
                }
                for g in grouped
            ]
            now = datetime.now(timezone.utc).isoformat()
            supabase.table("poly_market_term_results").upsert({
                "market_id": market_id,
                "persona_id": persona_id,
                "search_term": term,
                "total_mentions": freq.get("total_mentions", 0),
                "briefings_with_term": freq.get("briefings_with_term", 0),
                "total_briefings": freq.get("total_briefings", 0),
                "percentage": freq.get("percentage", 0),
                "trend": freq.get("trend", "stable"),
                "mentions_by_date": freq.get("mentions_by_date", []),
                "context_matches": context_matches,
                "context_total_matches": ctx.get("total_matches", 0),
                "context_transcripts_with_matches": ctx.get("transcripts_with_matches", 0),
                "last_updated": now,
            }, on_conflict="market_id,persona_id,search_term").execute()


async def reprocess_persona_poly_markets(persona_id: str) -> None:
    """Reprocess all Polymarket analysis for a persona across all linked events."""
    supabase = get_supabase()
    links = supabase.table("persona_poly_events").select("poly_event_id, folder_id").eq("persona_id", persona_id).execute()
    for link in (links.data or []):
        event_id = link["poly_event_id"]
        folder_id = link.get("folder_id")
        await update_poly_market_analysis(persona_id, event_id, folder_id=folder_id)
