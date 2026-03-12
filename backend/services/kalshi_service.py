"""Kalshi API client service."""

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import httpx

from backend.core.database import get_supabase
from backend.utils.nlp import calculate_term_frequency, search_term_in_context, group_nearby_mentions


KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_SEARCH_BASE = "https://api.elections.kalshi.com/v1/search"


# ----- Helpers -----


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def _parse_fixed_point(value: str | float | None) -> float | None:
    """Parse Kalshi FixedPointDollars (e.g. '0.6500') or float to Python float."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ----- Kalshi API client -----


async def fetch_series(ticker: str) -> dict[str, Any] | None:
    """Fetch a single series by ticker from Kalshi API."""
    ticker = (ticker or "").strip()
    if not ticker:
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{KALSHI_API_BASE}/series/{ticker}")
            response.raise_for_status()
            data = response.json()
            return data.get("series") or data
    except Exception as e:
        print(f"Failed to fetch series {ticker}: {e}")
        return None


async def fetch_events(
    series_ticker: str | None = None,
    status: str | None = None,
    cursor: str | None = None,
    limit: int = 200,
    with_nested_markets: bool = True,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Fetch events from Kalshi API. Returns (events, next_cursor).
    Uses cursor-based pagination.
    """
    try:
        params: dict[str, Any] = {"limit": limit}
        if series_ticker:
            params["series_ticker"] = series_ticker
        if status:
            params["status"] = status
        if cursor:
            params["cursor"] = cursor
        if with_nested_markets:
            params["with_nested_markets"] = "true"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{KALSHI_API_BASE}/events", params=params)
            response.raise_for_status()
            data = response.json()
            events = data.get("events") or []
            next_cursor = data.get("cursor") or None
            return events, next_cursor
    except Exception as e:
        print(f"Failed to fetch events: {e}")
        return [], None


async def fetch_all_events(
    series_ticker: str | None = None,
    status: str | None = None,
    with_nested_markets: bool = True,
    max_pages: int = 10,
) -> list[dict[str, Any]]:
    """Auto-paginating wrapper for fetch_events."""
    all_events: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(max_pages):
        events, next_cursor = await fetch_events(
            series_ticker=series_ticker,
            status=status,
            cursor=cursor,
            with_nested_markets=with_nested_markets,
        )
        if not events:
            break
        all_events.extend(events)
        if not next_cursor:
            break
        cursor = next_cursor
    return all_events


async def fetch_event(event_ticker: str) -> dict[str, Any] | None:
    """Fetch a single event by event_ticker from Kalshi API."""
    event_ticker = (event_ticker or "").strip()
    if not event_ticker:
        return None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{KALSHI_API_BASE}/events/{event_ticker}")
            response.raise_for_status()
            data = response.json()
            return data.get("event") or data
    except Exception as e:
        print(f"Failed to fetch event {event_ticker}: {e}")
        return None


async def fetch_markets(
    event_ticker: str | None = None,
    series_ticker: str | None = None,
    tickers: list[str] | None = None,
    status: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Fetch markets from Kalshi API."""
    try:
        params: dict[str, Any] = {"limit": limit}
        if event_ticker:
            params["event_ticker"] = event_ticker
        if series_ticker:
            params["series_ticker"] = series_ticker
        if tickers:
            params["tickers"] = ",".join(tickers)
        if status:
            params["status"] = status
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{KALSHI_API_BASE}/markets", params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("markets") or []
    except Exception as e:
        print(f"Failed to fetch markets: {e}")
        return []


async def discover_series(
    tags: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Discover available Mentions series from Kalshi, optionally filtered by tags.
    Always scoped to category='Mentions'.
    """
    try:
        params: dict[str, Any] = {"category": "Mentions"}
        if tags:
            # Kalshi supports comma-separated tags
            params["tags"] = ",".join(tags)
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{KALSHI_API_BASE}/series", params=params)
            response.raise_for_status()
            data = response.json()
            series_list = data.get("series") or []

        result = []
        for s in series_list:
            result.append({
                "ticker": s.get("ticker") or "",
                "title": s.get("title") or s.get("ticker") or "",
                "category": s.get("category"),
                "tags": s.get("tags") or [],
                "frequency": s.get("frequency"),
                "status": "active",
            })
        return result
    except Exception as e:
        print(f"Failed to discover series: {e}")
        return []


# ----- Search term extraction -----


def _clean_search_term(term: str) -> str:
    """Strip trailing numeric threshold patterns like '7+', '10+ times' from a term."""
    return re.sub(r'\s+\d+\+?\s*(times?)?\s*$', '', term, flags=re.IGNORECASE).strip()


def _extract_search_terms(market_data: dict[str, Any]) -> list[str]:
    """
    Extract search terms from a market row.
    Prefers custom_strike.Word (Kalshi Mentions markets) over regex parsing.
    """
    custom_strike = market_data.get("custom_strike")
    if isinstance(custom_strike, dict):
        word = custom_strike.get("Word")
        if word and isinstance(word, str) and word.strip():
            # Split on " / " to handle compound terms like "Shutdown / Shut Down"
            terms = [_clean_search_term(t) for t in word.split(" / ")]
            return [t for t in terms if t]
    # Fallback: parse quoted terms from question text
    question = market_data.get("question") or ""
    criteria = parse_market_criteria(question)
    return criteria.get("search_terms") or []


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


# ----- Market opportunity analysis -----


def analyze_market_opportunity(
    yes_price: float,
    historical_percentage: float,
) -> dict:
    """
    Analyze market and provide betting insight.
    Takes yes_price directly (0-1 float) and historical percentage (0-100).
    Returns recommendation, confidence, reason, and expected value.
    """
    # Historical percentage is our estimated true probability
    estimated_probability = historical_percentage / 100

    # Calculate expected value
    yes_ev = estimated_probability * (1 / yes_price) - 1 if yes_price > 0 else 0
    no_ev = (1 - estimated_probability) * (1 / (1 - yes_price)) - 1 if yes_price < 1 else 0

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
        "expectedValue": round(expected_value, 2),
    }


# ----- Database upsert operations -----


def _upsert_series(api_series: dict[str, Any]) -> str | None:
    """Upsert a kalshi_series record from API data. Returns internal UUID."""
    supabase = get_supabase()
    ticker = (api_series.get("ticker") or "").strip()
    if not ticker:
        return None

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "ticker": ticker,
        "title": api_series.get("title"),
        "frequency": api_series.get("frequency"),
        "category": api_series.get("category"),
        "tags": api_series.get("tags") or [],
        "settlement_sources": api_series.get("settlement_sources") or [],
        "fee_type": api_series.get("fee_type"),
        "status": "active",
        "updated_at": now,
    }

    existing = supabase.table("kalshi_series").select("id").eq("ticker", ticker).limit(1).execute()
    if existing.data and len(existing.data) > 0:
        series_id = existing.data[0]["id"]
        supabase.table("kalshi_series").update(row).eq("id", series_id).execute()
        return series_id
    else:
        supabase.table("kalshi_series").insert(row).execute()
        refetch = supabase.table("kalshi_series").select("id").eq("ticker", ticker).limit(1).execute()
        if not refetch.data or len(refetch.data) == 0:
            return None
        return refetch.data[0]["id"]


def _upsert_event_and_markets(
    api_event: dict[str, Any],
    series_id: str | None = None,
) -> tuple[str | None, list[str]]:
    """
    Insert or update kalshi_events and kalshi_markets from Kalshi event payload.
    Returns (event_id, list of market_ids).
    """
    supabase = get_supabase()
    event_ticker = (api_event.get("event_ticker") or "").strip()
    if not event_ticker:
        return None, []

    title = api_event.get("title")
    sub_title = api_event.get("sub_title")
    series_ticker = api_event.get("series_ticker")
    mutually_exclusive = api_event.get("mutually_exclusive", False)
    category = api_event.get("category")
    status = api_event.get("status") or "active"
    strike_date = _parse_iso(api_event.get("strike_date"))
    strike_period = api_event.get("strike_period")

    # Upsert event (by event_ticker)
    existing = supabase.table("kalshi_events").select("id").eq("event_ticker", event_ticker).limit(1).execute()
    now = datetime.now(timezone.utc).isoformat()
    event_row: dict[str, Any] = {
        "title": title,
        "sub_title": sub_title,
        "series_ticker": series_ticker,
        "mutually_exclusive": mutually_exclusive,
        "category": category,
        "status": status,
        "strike_date": strike_date.isoformat() if strike_date else None,
        "strike_period": strike_period,
        "updated_at": now,
    }
    if series_id:
        event_row["series_id"] = series_id

    if existing.data and len(existing.data) > 0:
        event_id = existing.data[0]["id"]
        supabase.table("kalshi_events").update(event_row).eq("id", event_id).execute()
    else:
        event_row["event_ticker"] = event_ticker
        supabase.table("kalshi_events").insert(event_row).execute()
        refetch = supabase.table("kalshi_events").select("id").eq("event_ticker", event_ticker).limit(1).execute()
        if not refetch.data or len(refetch.data) == 0:
            return None, []
        event_id = refetch.data[0]["id"]

    # Markets
    markets_payload = api_event.get("markets") or []
    if not isinstance(markets_payload, list):
        markets_payload = []
    market_ids: list[str] = []

    for m in markets_payload:
        market_ticker = (m.get("ticker") or "").strip()
        if not market_ticker:
            continue

        market_event_ticker = m.get("event_ticker") or event_ticker
        market_type = m.get("market_type") or "binary"
        yes_sub_title = m.get("yes_sub_title")
        no_sub_title = m.get("no_sub_title")
        m_status = m.get("status") or "active"
        result = m.get("result") or ""
        last_price = _parse_fixed_point(m.get("last_price") or m.get("last_price_dollars"))
        yes_bid = _parse_fixed_point(m.get("yes_bid") or m.get("yes_bid_dollars"))
        yes_ask = _parse_fixed_point(m.get("yes_ask") or m.get("yes_ask_dollars"))
        no_bid = _parse_fixed_point(m.get("no_bid") or m.get("no_bid_dollars"))
        no_ask = _parse_fixed_point(m.get("no_ask") or m.get("no_ask_dollars"))
        previous_price = _parse_fixed_point(m.get("previous_price") or m.get("previous_price_dollars"))
        volume = _parse_fixed_point(m.get("volume") or m.get("volume_fp"))
        open_interest = _parse_fixed_point(m.get("open_interest") or m.get("open_interest_fp"))
        close_time = _parse_iso(m.get("close_time"))
        open_time = _parse_iso(m.get("open_time"))
        settlement_value = _parse_fixed_point(m.get("settlement_value") or m.get("settlement_value_dollars"))
        rules_primary = m.get("rules_primary")
        rules_secondary = m.get("rules_secondary")
        custom_strike = m.get("custom_strike")

        # For Mentions markets, use custom_strike.Word as the question (the tracked term)
        if isinstance(custom_strike, dict) and custom_strike.get("Word"):
            question = custom_strike["Word"]
        else:
            question = yes_sub_title or m.get("title") or market_ticker

        # Upsert market by ticker
        existing_m = supabase.table("kalshi_markets").select("id").eq("ticker", market_ticker).limit(1).execute()

        row = {
            "event_ticker": market_event_ticker,
            "event_id": event_id,
            "market_type": market_type,
            "question": question,
            "yes_sub_title": yes_sub_title,
            "no_sub_title": no_sub_title,
            "status": m_status,
            "result": result if result else None,
            "last_price": last_price,
            "yes_bid": yes_bid,
            "yes_ask": yes_ask,
            "no_bid": no_bid,
            "no_ask": no_ask,
            "previous_price": previous_price,
            "volume": volume,
            "open_interest": open_interest,
            "close_time": close_time.isoformat() if close_time else None,
            "open_time": open_time.isoformat() if open_time else None,
            "settlement_value": settlement_value,
            "rules_primary": rules_primary,
            "rules_secondary": rules_secondary,
            "custom_strike": custom_strike,
            "updated_at": now,
        }
        if existing_m.data and len(existing_m.data) > 0:
            market_id = existing_m.data[0]["id"]
            supabase.table("kalshi_markets").update(row).eq("id", market_id).execute()
        else:
            row["ticker"] = market_ticker
            row["created_at"] = now
            supabase.table("kalshi_markets").insert(row).execute()
            refetch_m = supabase.table("kalshi_markets").select("id").eq("ticker", market_ticker).limit(1).execute()
            if not refetch_m.data or len(refetch_m.data) == 0:
                continue
            market_id = refetch_m.data[0]["id"]
        market_ids.append(market_id)

        # Build search config so terms are available on first load
        search_terms = _extract_search_terms({"custom_strike": custom_strike, "question": question})
        if search_terms:
            supabase.table("market_search_configs").upsert({
                "market_id": market_id,
                "search_terms": search_terms,
                "min_count": 0,
                "logic": "any",
                "updated_at": now,
            }, on_conflict="market_id").execute()

    return event_id, market_ids


# ----- Series management -----


async def add_series(ticker: str) -> tuple[dict[str, Any] | None, str | None]:
    """
    Add a Kalshi series by ticker.
    Fetches series metadata, then fetches events with nested markets, upserts all.
    """
    ticker = (ticker or "").strip()
    if not ticker:
        return None, "not_found"

    # Fetch series metadata
    api_series = await fetch_series(ticker)
    if not api_series:
        return None, "not_found"

    # Upsert series
    series_id = _upsert_series(api_series)
    if not series_id:
        return None, "db_error"

    # Fetch events with nested markets
    events = await fetch_all_events(series_ticker=ticker, with_nested_markets=True)
    for ev in events:
        _upsert_event_and_markets(ev, series_id=series_id)

    detail = await get_series_detail(series_id)
    if not detail:
        return None, "db_error"
    return detail, None


async def get_series_detail(series_id: str) -> dict[str, Any] | None:
    """Get series with events."""
    supabase = get_supabase()
    series_row = supabase.table("kalshi_series").select("*").eq("id", series_id).single().execute()
    if not series_row.data:
        return None

    events = supabase.table("kalshi_events").select("*").eq("series_id", series_id).order("strike_date", desc=True).execute()
    events_data = events.data or []

    return {
        "series": series_row.data,
        "events": events_data,
    }


async def get_all_series() -> list[dict[str, Any]]:
    """List all stored series with event counts."""
    supabase = get_supabase()
    series_rows = supabase.table("kalshi_series").select("*").order("updated_at", desc=True).execute()
    result = []
    for s in (series_rows.data or []):
        sid = s["id"]
        events = supabase.table("kalshi_events").select("id").eq("series_id", sid).execute()
        event_count = len(events.data or [])
        result.append({
            **s,
            "event_count": event_count,
        })
    return result


async def delete_series(series_id: str) -> bool:
    """Delete a stored series (cascades to junction, events set null)."""
    supabase = get_supabase()
    result = supabase.table("kalshi_series").delete().eq("id", series_id).execute()
    return bool(result.data)


async def _search_events_by_tag(tag: str) -> list[dict[str, Any]]:
    """
    Fetch open/unopened Mentions events for a single tag via the v1 search API.
    Returns raw items from the API (each is an event with nested markets).
    """
    try:
        params: dict[str, Any] = {
            "category": "Mentions",
            "tag": tag,
            "status": "open,unopened",
            "order_by": "closing",
            "reverse": "false",
            "page_size": 50,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{KALSHI_SEARCH_BASE}/series", params=params)
            response.raise_for_status()
            data = response.json()
            return data.get("current_page") or []
    except Exception as e:
        print(f"Failed to search events for tag {tag}: {e}")
        return []


async def browse_events() -> dict[str, list[dict[str, Any]]]:
    """
    Browse all open Mentions events from Kalshi v1 search API,
    grouped by tag (Politicians, Earnings, Sports).
    Each item is an event with nested markets.
    """
    tags = ["Politicians", "Earnings", "Sports"]
    results: dict[str, list[dict[str, Any]]] = {}

    for tag in tags:
        raw_items = await _search_events_by_tag(tag)
        events = []
        for item in raw_items:
            markets = []
            for m in (item.get("markets") or []):
                markets.append({
                    "ticker": m.get("ticker") or "",
                    "word": _clean_search_term((m.get("custom_strike") or {}).get("Word") or m.get("yes_subtitle") or ""),
                    "yes_bid": m.get("yes_bid"),
                    "yes_ask": m.get("yes_ask"),
                    "last_price": m.get("last_price"),
                    "result": m.get("result") or "",
                    "volume": m.get("volume"),
                    "close_ts": m.get("close_ts"),
                })
            events.append({
                "series_ticker": item.get("series_ticker") or "",
                "event_ticker": item.get("event_ticker") or "",
                "event_title": item.get("event_title") or "",
                "event_subtitle": item.get("event_subtitle") or "",
                "series_title": item.get("series_title") or "",
                "total_market_count": item.get("total_market_count") or 0,
                "active_market_count": item.get("active_market_count") or 0,
                "markets": markets,
                "tag": tag,
                "strike_date": item.get("strike_date") or None,
            })
        results[tag] = events

    return results


async def ensure_series(ticker: str) -> str | None:
    """
    Ensure a series exists in the DB by ticker.
    If not stored, fetch from Kalshi API and upsert series + events + markets.
    Returns the DB UUID.
    """
    supabase = get_supabase()
    existing = supabase.table("kalshi_series").select("id").eq("ticker", ticker).limit(1).execute()
    if existing.data and len(existing.data) > 0:
        return existing.data[0]["id"]

    api_series = await fetch_series(ticker)
    if not api_series:
        return None
    series_id = _upsert_series(api_series)
    if not series_id:
        return None

    events = await fetch_all_events(series_ticker=ticker, with_nested_markets=True)
    for ev in events:
        _upsert_event_and_markets(ev, series_id=series_id)

    return series_id


async def get_series_detail_by_ticker(ticker: str) -> dict[str, Any] | None:
    """Get series detail by ticker, auto-creating in DB if needed."""
    series_id = await ensure_series(ticker)
    if not series_id:
        return None
    return await get_series_detail(series_id)


async def ensure_event(event_ticker: str) -> str | None:
    """
    Ensure an event exists in the DB by event_ticker.
    If not stored, derives the series_ticker, ensures the series
    (which fetches all events+markets), then returns the event's DB UUID.
    """
    supabase = get_supabase()
    existing = supabase.table("kalshi_events").select("id").eq("event_ticker", event_ticker).limit(1).execute()
    if existing.data and len(existing.data) > 0:
        return existing.data[0]["id"]

    # Derive series_ticker: event tickers are like KXTRUMPMENTION-26FEB22
    # The series ticker is the part before the last dash-separated date segment
    # Use the v2 event API to get the series_ticker
    api_event = await fetch_event(event_ticker)
    if not api_event:
        return None
    series_ticker = api_event.get("series_ticker") or ""
    if not series_ticker:
        return None

    # Ensure the series (fetches all events + markets)
    await ensure_series(series_ticker)

    # Now the event should be in DB
    refetch = supabase.table("kalshi_events").select("id").eq("event_ticker", event_ticker).limit(1).execute()
    if refetch.data and len(refetch.data) > 0:
        return refetch.data[0]["id"]
    return None


async def get_event_detail_by_ticker(
    event_ticker: str, persona_id: str | None = None
) -> dict[str, Any] | None:
    """Get event detail by event_ticker, auto-creating in DB if needed."""
    event_id = await ensure_event(event_ticker)
    if not event_id:
        return None
    result = await get_event_with_analysis(event_id, persona_id=persona_id)
    if not result:
        return None
    # Also include series info for the header
    supabase = get_supabase()
    event_row = result.get("event") or {}
    series_id = event_row.get("series_id")
    series_data = None
    if series_id:
        series_row = supabase.table("kalshi_series").select("*").eq("id", series_id).limit(1).execute()
        series_data = series_row.data[0] if series_row.data else None
    result["series"] = series_data
    return result


async def refresh_series(series_id: str) -> dict[str, Any] | None:
    """Re-fetch the series and events from Kalshi API and update."""
    supabase = get_supabase()
    series_row = supabase.table("kalshi_series").select("ticker").eq("id", series_id).single().execute()
    if not series_row.data:
        return None
    ticker = series_row.data["ticker"]

    # Refresh series metadata
    api_series = await fetch_series(ticker)
    if api_series:
        _upsert_series(api_series)

    # Refresh events with nested markets
    events = await fetch_all_events(series_ticker=ticker, with_nested_markets=True)
    for ev in events:
        _upsert_event_and_markets(ev, series_id=series_id)

    return await get_series_detail(series_id)


# ----- Event operations -----


async def get_active_event_for_series(series_id: str) -> dict[str, Any] | None:
    """Get the most recent active event for a series, fallback to most recent closed."""
    supabase = get_supabase()
    events = (
        supabase.table("kalshi_events")
        .select("*")
        .eq("series_id", series_id)
        .order("strike_date", desc=True)
        .limit(20)
        .execute()
    )
    events_data = events.data or []
    # Prefer active events
    for ev in events_data:
        if ev.get("status") in ("active", "open"):
            return ev
    # Fallback to most recent
    return events_data[0] if events_data else None


async def get_event_markets(event_id: str) -> dict[str, Any] | None:
    """Get event + markets without persona-specific analysis."""
    supabase = get_supabase()
    event_row = supabase.table("kalshi_events").select("*").eq("id", event_id).single().execute()
    if not event_row.data:
        return None
    markets = supabase.table("kalshi_markets").select("*").eq("event_id", event_id).order("created_at").execute()
    return {
        "event": event_row.data,
        "markets": markets.data or [],
    }


async def get_event_with_analysis(
    event_id: str, persona_id: str | None = None
) -> dict[str, Any] | None:
    """Get event + markets + optional persona analysis."""
    if persona_id:
        return await _get_persona_event_internal(persona_id, event_id)
    return await get_event_markets(event_id)


async def _get_persona_event_internal(persona_id: str, event_id: str) -> dict[str, Any] | None:
    """Build event response with markets + persona-specific term analysis."""
    supabase = get_supabase()
    event_row = supabase.table("kalshi_events").select("*").eq("id", event_id).single().execute()
    if not event_row.data:
        return None
    event_data = event_row.data
    markets_rows = supabase.table("kalshi_markets").select("*").eq("event_id", event_id).order("created_at").execute()
    markets_data = markets_rows.data or []

    if not markets_data:
        return {"event": event_data, "markets": []}

    market_ids = [m["id"] for m in markets_data]

    # Batch fetch all configs and term results in 2 queries instead of 2N
    all_configs = supabase.table("market_search_configs").select("*").in_("market_id", market_ids).execute()
    all_terms = supabase.table("market_term_results").select("*").in_("market_id", market_ids).eq("persona_id", persona_id).execute()

    config_map: dict[str, dict] = {c["market_id"]: c for c in (all_configs.data or [])}
    terms_map: dict[str, list[dict]] = {}
    for r in (all_terms.data or []):
        terms_map.setdefault(r["market_id"], []).append(r)

    market_with_analysis = []
    for m in markets_data:
        mid = m["id"]
        term_results = terms_map.get(mid, [])
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
                for r in term_results
            ],
        })
    return {
        "event": event_data,
        "markets": market_with_analysis,
    }


async def refresh_single_event(event_id: str) -> dict[str, Any] | None:
    """Re-fetch a single event from Kalshi, update markets, re-run analysis for linked personas."""
    supabase = get_supabase()
    event_row = supabase.table("kalshi_events").select("event_ticker, series_id").eq("id", event_id).single().execute()
    if not event_row.data:
        return None
    event_ticker = event_row.data.get("event_ticker")
    series_id = event_row.data.get("series_id")
    if not event_ticker:
        return None

    # Fetch event with nested markets in one call
    api_event = await fetch_event(event_ticker)
    if not api_event:
        return await get_event_markets(event_id)

    # If the event doesn't include markets, fetch them separately
    if not api_event.get("markets"):
        api_markets = await fetch_markets(event_ticker=event_ticker)
        api_event["markets"] = api_markets

    _, market_ids = _upsert_event_and_markets(api_event, series_id=series_id)

    # Build search configs for all markets using custom_strike.Word
    now = datetime.now(timezone.utc).isoformat()
    all_market_rows = supabase.table("kalshi_markets").select("id, question, custom_strike").in_("id", market_ids).execute()
    market_data_map = {r["id"]: r for r in (all_market_rows.data or [])}
    for market_id in market_ids:
        data = market_data_map.get(market_id, {})
        search_terms = _extract_search_terms(data)
        supabase.table("market_search_configs").upsert({
            "market_id": market_id,
            "search_terms": search_terms,
            "min_count": 0,
            "logic": "any",
            "updated_at": now,
        }, on_conflict="market_id").execute()

    return await get_event_markets(event_id)


# ----- Market analysis (NLP layer — unchanged logic) -----


async def update_market_analysis(persona_id: str, event_id: str, folder_id: str | None = None) -> None:
    """
    For each market in the event, for each search term: compute frequency + context,
    and upsert into market_term_results.
    """
    from backend.services import persona_service, transcript_service

    supabase = get_supabase()
    markets = supabase.table("kalshi_markets").select("id").eq("event_id", event_id).execute()
    market_ids = [r["id"] for r in (markets.data or [])]

    persona = await persona_service.get_persona_by_id(persona_id)
    aliases = persona.get("aliases", []) if persona else []
    print(f"[update_market_analysis] persona_id={persona_id}, aliases={aliases}, folder_id={folder_id}")

    persona_transcripts = await persona_service.get_transcripts_for_persona(persona_id, folder_id=folder_id)
    transcript_ids = [t["id"] for t in persona_transcripts]
    transcripts = await transcript_service.get_transcripts_by_ids(transcript_ids) if transcript_ids else []
    print(f"[update_market_analysis] full transcripts count={len(transcripts)}")

    all_configs = supabase.table("market_search_configs").select("*").in_("market_id", market_ids).execute()
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
            # Map grouped clusters back to the context_matches format the frontend expects
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
                "context_matches": context_matches,
                "context_total_matches": ctx.get("total_matches", 0),
                "context_transcripts_with_matches": ctx.get("transcripts_with_matches", 0),
                "last_updated": now,
            }, on_conflict="market_id,persona_id,search_term").execute()


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


# ----- Past events loading -----


async def fetch_past_events_for_series(series_id: str) -> dict[str, Any]:
    """
    Fetch closed events for a series from Kalshi API.
    Uses series_ticker to directly query closed events.
    """
    supabase = get_supabase()
    series_row = supabase.table("kalshi_series").select("ticker").eq("id", series_id).single().execute()
    if not series_row.data:
        return {"added": 0, "total_matching": 0}

    ticker = series_row.data["ticker"]

    # Fetch all closed events for this series
    closed_events = await fetch_all_events(
        series_ticker=ticker,
        status="settled",
        with_nested_markets=True,
        max_pages=10,
    )

    added = 0
    for api_event in closed_events:
        event_id, market_ids = _upsert_event_and_markets(api_event, series_id=series_id)
        if not event_id:
            continue

        # Build search configs using custom_strike.Word (skip if already populated)
        now = datetime.now(timezone.utc).isoformat()
        if market_ids:
            existing_cfgs = supabase.table("market_search_configs").select("id, market_id, search_terms").in_("market_id", market_ids).execute()
            populated_ids = {c["market_id"] for c in (existing_cfgs.data or []) if c.get("search_terms")}
            missing_ids = [mid for mid in market_ids if mid not in populated_ids]
            if missing_ids:
                all_market_rows = supabase.table("kalshi_markets").select("id, question, custom_strike").in_("id", missing_ids).execute()
                market_data_map = {r["id"]: r for r in (all_market_rows.data or [])}
                for market_id in missing_ids:
                    data = market_data_map.get(market_id, {})
                    search_terms = _extract_search_terms(data)
                    supabase.table("market_search_configs").upsert({
                        "market_id": market_id,
                        "search_terms": search_terms,
                        "min_count": 0,
                        "logic": "any",
                        "updated_at": now,
                    }, on_conflict="market_id").execute()
        added += 1

    return {"added": added, "total_matching": len(closed_events)}


# ----- Date extraction utilities (unchanged) -----


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
