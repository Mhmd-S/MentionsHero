"""Swing analysis service for mention markets.

Correlates term mentions in transcripts with price movements on Polymarket.
Instead of predicting binary outcomes, measures how prices swing when words
are said — enabling profit from price movement rather than resolution.

Flow:
1. For each market/term, get CLOB price history
2. For each transcript (briefing), check if term was mentioned
3. Measure price before vs after the briefing
4. Build per-term swing profiles with co-occurrence data
"""

import json
import math
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx

from backend.core.database import get_supabase
from backend.utils.nlp import build_market_pattern, parse_transcript_segments

import re

CLOB_API_BASE = "https://clob.polymarket.com"
GAMMA_API_BASE = "https://gamma-api.polymarket.com"

# Hours after a briefing to measure the price swing
SWING_WINDOW_HOURS = 6


async def analyze_swings(
    event_id: str | None = None,
    persona_id: str | None = None,
) -> dict[str, Any]:
    """
    Analyze price swings correlated with term mentions across briefings.

    For each market's search term:
    - Fetches CLOB price history
    - Matches each transcript date to a price window
    - Measures swing = price_after - price_before for each briefing
    - Computes avg swing when term is mentioned vs absent
    - Finds co-occurring terms that amplify swings
    """
    supabase = get_supabase()

    # 1. Get markets with search configs
    market_query = supabase.table("poly_markets").select(
        "id, poly_id, event_id, question, group_item_title, active, closed"
    )
    if event_id:
        market_query = market_query.eq("event_id", event_id)
    markets_resp = market_query.execute()
    markets = markets_resp.data or []

    if not markets:
        return {"profiles": [], "total_markets_analyzed": 0, "total_briefings": 0}

    market_ids = [m["id"] for m in markets]
    market_map = {m["id"]: m for m in markets}

    # Get search configs
    configs_resp = supabase.table("poly_market_search_configs").select("*").in_("market_id", market_ids).execute()
    config_map = {c["market_id"]: c for c in (configs_resp.data or [])}

    # Get event titles
    event_ids_set = list({m["event_id"] for m in markets if m.get("event_id")})
    event_map: dict[str, str] = {}
    if event_ids_set:
        events_resp = supabase.table("poly_events").select("id, title, start_date, end_date").in_("id", event_ids_set).execute()
        event_map = {e["id"]: e.get("title", "") for e in (events_resp.data or [])}

    # 2. Get transcripts (optionally filtered by persona)
    transcripts = await _get_transcripts(persona_id)
    if not transcripts:
        return {"profiles": [], "total_markets_analyzed": 0, "total_briefings": 0}

    # 3. For each market+term, fetch price history and correlate with transcripts
    profiles: list[dict[str, Any]] = []
    markets_analyzed = 0

    async with httpx.AsyncClient(timeout=20.0) as client:
        for market in markets:
            mid = market["id"]
            cfg = config_map.get(mid)
            if not cfg:
                continue

            search_terms = cfg.get("search_terms") or []
            if not search_terms:
                continue

            poly_id = market.get("poly_id", "")
            if not poly_id:
                continue

            # Fetch CLOB price history
            price_history = await _fetch_price_history(client, poly_id)
            if not price_history:
                continue

            markets_analyzed += 1

            for term in search_terms:
                profile = _build_swing_profile(
                    term=term,
                    market=market,
                    event_title=event_map.get(market.get("event_id", ""), ""),
                    price_history=price_history,
                    transcripts=transcripts,
                    all_terms=search_terms,
                    persona_id=persona_id,
                )
                if profile:
                    profiles.append(profile)

    # Sort by edge (abs difference between mentioned and absent swing)
    profiles.sort(key=lambda p: abs(p.get("edge", 0)), reverse=True)

    return {
        "profiles": profiles,
        "total_markets_analyzed": markets_analyzed,
        "total_briefings": len(transcripts),
    }


async def _get_transcripts(persona_id: str | None) -> list[dict[str, Any]]:
    """Get transcripts, optionally filtered by persona."""
    supabase = get_supabase()

    if persona_id:
        from backend.services import persona_service, transcript_service
        persona_transcripts = await persona_service.get_transcripts_for_persona(persona_id)
        transcript_ids = [t["id"] for t in persona_transcripts]
        if not transcript_ids:
            return []
        return await transcript_service.get_transcripts_by_ids(transcript_ids)
    else:
        from backend.services import transcript_service
        return await transcript_service.get_all_transcripts()


async def _fetch_price_history(
    client: httpx.AsyncClient,
    poly_id: str,
) -> list[dict[str, Any]]:
    """Fetch CLOB price history for a market. Returns list of {t, p} dicts."""
    try:
        # Get clobTokenIds from Gamma
        gamma_resp = await client.get(f"{GAMMA_API_BASE}/markets/{poly_id}")
        gamma_resp.raise_for_status()
        market_data = gamma_resp.json()

        raw_clob = market_data.get("clobTokenIds")
        if isinstance(raw_clob, str):
            clob_token_ids = json.loads(raw_clob)
        elif isinstance(raw_clob, list):
            clob_token_ids = raw_clob
        else:
            return []

        if not clob_token_ids or len(clob_token_ids) < 2:
            return []

        # YES token = index 0
        yes_token_id = clob_token_ids[0]

        # Fetch price history
        clob_resp = await client.get(
            f"{CLOB_API_BASE}/prices-history",
            params={
                "market": yes_token_id,
                "interval": "all",
                "fidelity": 30,  # 30-minute resolution
            },
        )
        clob_resp.raise_for_status()
        return clob_resp.json().get("history", [])

    except Exception as e:
        print(f"[swing] price history error for poly_id={poly_id}: {e}")
        return []


def _build_swing_profile(
    term: str,
    market: dict[str, Any],
    event_title: str,
    price_history: list[dict[str, Any]],
    transcripts: list[dict[str, Any]],
    all_terms: list[str],
    persona_id: str | None,
) -> dict[str, Any] | None:
    """Build a swing profile for a single term against price history and transcripts."""
    if not price_history or len(price_history) < 2:
        return None

    # Price history time range
    first_ts = price_history[0]["t"]
    last_ts = price_history[-1]["t"]

    pattern = re.compile(build_market_pattern(term), re.IGNORECASE)

    # Other terms for co-occurrence tracking
    other_terms = [t for t in all_terms if t.lower() != term.lower()]
    other_patterns = {t: re.compile(build_market_pattern(t), re.IGNORECASE) for t in other_terms}

    swing_events: list[dict[str, Any]] = []
    swings_mentioned: list[float] = []
    swings_absent: list[float] = []

    # Co-occurrence tracking: other_term -> list of swings when both present
    co_swings: dict[str, list[float]] = {t: [] for t in other_terms}

    for transcript in transcripts:
        upload_date = transcript.get("upload_date")
        if not upload_date or len(upload_date) != 8:
            continue

        # Convert YYYYMMDD to unix timestamp (assume midday UTC — briefings are typically afternoon)
        try:
            dt = datetime(
                int(upload_date[:4]),
                int(upload_date[4:6]),
                int(upload_date[6:]),
                12, 0, 0,
                tzinfo=timezone.utc,
            )
            briefing_ts = int(dt.timestamp())
        except (ValueError, TypeError):
            continue

        # Skip transcripts outside the market's price history window
        if briefing_ts < first_ts - 86400 or briefing_ts > last_ts + 86400:
            continue

        # Find price before and after the briefing
        price_before = _find_price_at(price_history, briefing_ts)
        price_after = _find_price_at(price_history, briefing_ts + SWING_WINDOW_HOURS * 3600)

        if price_before is None or price_after is None:
            continue

        swing = round(price_after - price_before, 4)

        # Check if term was mentioned
        text = transcript.get("transcript", "")
        mentions = len(pattern.findall(text))

        if mentions > 0:
            swings_mentioned.append(swing)

            # Check co-occurring terms
            mentioned_others = []
            for ot, op in other_patterns.items():
                if op.search(text):
                    mentioned_others.append(ot)
                    co_swings[ot].append(swing)

            swing_events.append({
                "term": term,
                "transcript_name": transcript.get("name", "Unknown"),
                "transcript_date": f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}",
                "mention_count": mentions,
                "price_before": round(price_before, 4),
                "price_after": round(price_after, 4),
                "swing": swing,
                "co_terms": mentioned_others,
            })
        else:
            swings_absent.append(swing)

    # Need at least some data to be meaningful
    total_briefings = len(swings_mentioned) + len(swings_absent)
    if total_briefings == 0:
        return None

    avg_mentioned = _safe_avg(swings_mentioned)
    avg_absent = _safe_avg(swings_absent)
    edge = round(avg_mentioned - avg_absent, 4) if swings_mentioned else 0

    # Consistency: lower std dev = more predictable
    consistency = round(_safe_std(swings_mentioned), 4) if len(swings_mentioned) >= 2 else 0

    # Top co-occurring terms
    top_co = []
    for ot in other_terms:
        if co_swings[ot]:
            top_co.append({
                "term": ot,
                "co_count": len(co_swings[ot]),
                "avg_combined_swing": round(_safe_avg(co_swings[ot]), 4),
            })
    top_co.sort(key=lambda x: abs(x["avg_combined_swing"]), reverse=True)

    return {
        "term": term,
        "market_question": market.get("question"),
        "event_title": event_title,
        "total_briefings": total_briefings,
        "mentioned_in": len(swings_mentioned),
        "avg_swing_when_mentioned": round(avg_mentioned, 4),
        "avg_swing_when_absent": round(avg_absent, 4),
        "edge": edge,
        "max_swing": round(max(swings_mentioned), 4) if swings_mentioned else 0,
        "min_swing": round(min(swings_mentioned), 4) if swings_mentioned else 0,
        "consistency": consistency,
        "swing_events": sorted(swing_events, key=lambda e: abs(e["swing"]), reverse=True),
        "top_co_terms": top_co[:10],
    }


def _find_price_at(history: list[dict[str, Any]], target_ts: int) -> float | None:
    """Find the closest price point to a target timestamp."""
    if not history:
        return None
    closest = min(history, key=lambda h: abs(h["t"] - target_ts))
    # Only use if within 12 hours of target
    if abs(closest["t"] - target_ts) > 12 * 3600:
        return None
    return closest["p"]


def _safe_avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0


def _safe_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0
    avg = _safe_avg(values)
    variance = sum((v - avg) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)
