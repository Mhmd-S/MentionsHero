"""Swing analysis service for mention markets.

Correlates term mentions in transcripts with price movements on Polymarket.
Uses a spike-first approach: detect significant price movements, then trace
back to what was said in the transcript at that moment.

Flow:
1. Match transcripts to events using Gemini (title/date reasoning)
2. Infer event start times from transcript content
3. Detect price spikes in CLOB history
4. Map spikes back to transcript timeline to find causal words
5. Build per-term swing profiles with co-occurrence data
"""

import asyncio
import json
import math
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from google import genai
from google.genai import types

from backend.config import get_settings
from backend.core.database import get_supabase
from backend.utils.nlp import build_market_pattern

CLOB_API_BASE = "https://clob.polymarket.com"
GAMMA_API_BASE = "https://gamma-api.polymarket.com"

# Spike detection thresholds
MIN_SPIKE_CENTS = 3  # Minimum price move (in cents) to count as a spike
SPIKE_WINDOW_MINUTES = 5  # Window to measure price change over

# How many minutes of transcript to look at before a spike
LOOKBACK_MINUTES = 5


# =====================================================================
# Public API
# =====================================================================


async def analyze_swings(
    event_id: str | None = None,
    persona_id: str | None = None,
) -> dict[str, Any]:
    """
    Spike-first swing analysis.

    1. Get markets + transcripts
    2. Use Gemini to match transcripts to events and infer start times
    3. For each market, detect price spikes
    4. Trace spikes back to transcript content
    5. Build per-term and per-spike profiles
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
        return _empty_result()

    market_ids = [m["id"] for m in markets]

    # Get search configs
    configs_resp = supabase.table("poly_market_search_configs").select("*").in_("market_id", market_ids).execute()
    config_map = {c["market_id"]: c for c in (configs_resp.data or [])}

    # Get events
    event_ids_set = list({m["event_id"] for m in markets if m.get("event_id")})
    events_data: dict[str, dict[str, Any]] = {}
    if event_ids_set:
        events_resp = supabase.table("poly_events").select(
            "id, title, start_date, end_date"
        ).in_("id", event_ids_set).execute()
        events_data = {e["id"]: e for e in (events_resp.data or [])}

    # 2. Get transcripts
    transcripts = await _get_transcripts(persona_id)
    if not transcripts:
        return _empty_result()

    # 3. Match transcripts to events via Gemini
    event_matches = await _gemini_match_transcripts(events_data, transcripts)

    print(f"[swing] Gemini matched {sum(len(v) for v in event_matches.values())} "
          f"transcript-event pairs across {len(event_matches)} events")

    # 4. For each market, detect spikes and trace back
    all_spikes: list[dict[str, Any]] = []
    term_profiles: dict[str, dict[str, Any]] = {}
    markets_analyzed = 0
    matched_briefing_ids: set[str] = set()

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

            eid = market.get("event_id", "")
            matched = event_matches.get(eid, [])
            if not matched:
                continue

            # Fetch CLOB price history at 1-min fidelity
            price_history = await _fetch_price_history(client, poly_id, fidelity=1)
            if not price_history:
                continue

            markets_analyzed += 1

            # Detect spikes
            spikes = _detect_spikes(price_history)
            if not spikes:
                continue

            event_title = events_data.get(eid, {}).get("title", "")

            # Infer event start from price volatility
            clob_start_ts = infer_event_start_from_prices(price_history)

            # For each matched transcript, trace spikes to words
            for match in matched:
                transcript = match["transcript"]
                gemini_start_ts = match["event_start_ts"]

                # Use CLOB-inferred start if Gemini's is outside the price range
                start_ts = gemini_start_ts
                if clob_start_ts:
                    if not start_ts or abs(start_ts - clob_start_ts) > 12 * 3600:
                        print(f"[swing] overriding Gemini start with CLOB-inferred: "
                              f"{datetime.fromtimestamp(clob_start_ts, tz=timezone.utc).strftime('%Y-%m-%d %H:%M')}")
                        start_ts = clob_start_ts

                if not start_ts:
                    continue

                matched_briefing_ids.add(transcript.get("id", ""))

                text = transcript.get("transcript", "")

                # Parse transcript into timed segments
                timeline = _parse_transcript_timeline(text, start_ts)

                # For sparse/no timestamps: create a single segment covering the full text
                if len(timeline) < 3:
                    timeline = [{
                        "abs_ts": start_ts,
                        "offset_secs": 0,
                        "time_label": "full",
                        "speaker": "",
                        "text": text,
                    }]

                # Trace each spike back to transcript content
                for spike in spikes:
                    spike_ts = spike["timestamp"]

                    # For sparse timelines, use wider lookback
                    lookback = LOOKBACK_MINUTES if len(timeline) > 3 else 120

                    words_before = _get_words_around_spike(
                        timeline, spike_ts, lookback_min=lookback
                    )
                    if not words_before:
                        continue

                    # Check which search terms were in the words before the spike
                    mentioned_terms = []
                    for term in search_terms:
                        pattern = re.compile(build_market_pattern(term), re.IGNORECASE)
                        if pattern.search(words_before["text"]):
                            mentioned_terms.append(term)

                    spike_record = {
                        "market_id": mid,
                        "market_question": market.get("question"),
                        "event_title": event_title,
                        "transcript_name": transcript.get("name", "Unknown"),
                        "spike_time": datetime.fromtimestamp(
                            spike_ts, tz=timezone.utc
                        ).strftime("%H:%M:%S"),
                        "spike_magnitude": spike["magnitude"],
                        "spike_direction": "up" if spike["magnitude"] > 0 else "down",
                        "price_before": spike["price_before"],
                        "price_after": spike["price_after"],
                        "transcript_time": words_before["time_label"],
                        "text_before_spike": words_before["text"][:500],
                        "mentioned_terms": mentioned_terms,
                        "speaker": words_before.get("speaker", ""),
                    }
                    all_spikes.append(spike_record)

                    # Accumulate per-term stats
                    for term in mentioned_terms:
                        key = f"{term}||{eid}"
                        if key not in term_profiles:
                            term_profiles[key] = {
                                "term": term,
                                "event_title": event_title,
                                "spikes": [],
                                "magnitudes": [],
                            }
                        term_profiles[key]["spikes"].append(spike_record)
                        term_profiles[key]["magnitudes"].append(
                            spike["magnitude"]
                        )

    # 5. Build final profiles sorted by average spike magnitude
    profiles = []
    for key, tp in term_profiles.items():
        mags = tp["magnitudes"]
        profiles.append({
            "term": tp["term"],
            "event_title": tp["event_title"],
            "spike_count": len(mags),
            "avg_magnitude": round(_safe_avg(mags), 4),
            "max_magnitude": round(max(mags, key=abs), 4),
            "total_magnitude": round(sum(mags), 4),
            "consistency": round(_safe_std(mags), 4) if len(mags) >= 2 else 0,
            "spikes": tp["spikes"],
        })

    profiles.sort(key=lambda p: abs(p["avg_magnitude"]), reverse=True)

    # Sort all_spikes by absolute magnitude
    all_spikes.sort(key=lambda s: abs(s["spike_magnitude"]), reverse=True)

    return {
        "profiles": profiles,
        "spikes": all_spikes[:200],  # Top 200 spikes
        "total_markets_analyzed": markets_analyzed,
        "total_briefings": len(matched_briefing_ids),
        "total_transcripts_available": len(transcripts),
        "total_spikes_detected": len(all_spikes),
    }


# =====================================================================
# Gemini transcript-to-event matching
# =====================================================================


async def _gemini_match_transcripts(
    events: dict[str, dict[str, Any]],
    transcripts: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Use Gemini to match transcripts to events and infer event start times.

    Returns: {event_id: [{transcript, event_start_ts}, ...]}
    """
    if not events or not transcripts:
        return {}

    # Find the broadest date range across all events for pre-filtering
    all_starts = []
    all_ends = []
    for ev in events.values():
        s = _parse_date(str(ev.get("start_date", "")))
        e = _parse_date(str(ev.get("end_date", "")))
        if s:
            all_starts.append(s)
        if e:
            all_ends.append(e)

    # Pre-filter transcripts to those within the broadest event date range
    filtered_transcripts = transcripts
    if all_starts and all_ends:
        min_start = min(all_starts)
        max_end = max(all_ends)
        filtered_transcripts = []
        for t in transcripts:
            ud = t.get("upload_date", "")
            if not ud or len(ud) != 8:
                continue
            try:
                t_date = datetime(int(ud[:4]), int(ud[4:6]), int(ud[6:])).date()
            except (ValueError, TypeError):
                continue
            if min_start <= t_date <= max_end:
                filtered_transcripts.append(t)
        print(f"[swing] pre-filtered transcripts: {len(filtered_transcripts)} "
              f"(from {len(transcripts)}) within {min_start}→{max_end}")

    if not filtered_transcripts:
        print("[swing] no transcripts within event date ranges")
        return {}

    # Build compact representations for Gemini
    event_summaries = []
    for eid, ev in events.items():
        event_summaries.append({
            "event_id": eid,
            "title": ev.get("title", ""),
            "start_date": str(ev.get("start_date", ""))[:10],
            "end_date": str(ev.get("end_date", ""))[:10],
        })

    # Map filtered transcripts back to original indices
    transcript_index_map: dict[int, int] = {}  # gemini_index → original_index
    transcript_summaries = []
    for fi, t in enumerate(filtered_transcripts):
        # Find original index
        orig_idx = transcripts.index(t)
        transcript_index_map[fi] = orig_idx
        text_preview = (t.get("transcript") or "")[:200]
        transcript_summaries.append({
            "index": fi,
            "name": t.get("name", ""),
            "upload_date": t.get("upload_date", ""),
            "preview": text_preview,
        })

    prompt = f"""You are matching transcripts of speeches/briefings to Polymarket prediction events.

EVENTS (Polymarket "What will X say?" markets):
{json.dumps(event_summaries, indent=2)}

TRANSCRIPTS (speech/briefing recordings):
{json.dumps(transcript_summaries, indent=2)}

RULES — follow these strictly:
1. A transcript can ONLY match an event if its upload_date falls WITHIN the event's start_date to end_date range (inclusive). This is a hard requirement — never match outside the date range.
2. The transcript must be relevant to the event subject:
   - Weekly events like "What will Trump say this week?" match ALL transcripts by that person within the date range
   - Specific events like "Republican Members Issues Conference" match only transcripts of that specific appearance
   - "What will be said on Joe Rogan?" matches only Joe Rogan episode transcripts
3. Do NOT match transcripts whose upload_date is outside the event date range, even if the speaker matches.

For each valid match, also infer the likely START TIME (UTC) of the speech/briefing.
Use clues from the transcript name (e.g., "Mar. 13, 2026" → that date) and common patterns:
- White House press briefings: typically 13:00-15:00 ET (18:00-20:00 UTC)
- Presidential remarks/speeches: typically 11:00-17:00 ET (16:00-22:00 UTC)
- Gaggles (informal press): typically 10:00-18:00 ET (15:00-23:00 UTC)
- If unsure, use 18:00 UTC as default for the transcript's date

Return JSON array of matches. Each match has:
- event_id: string
- transcript_index: number
- event_start_utc: string (ISO format, e.g. "2026-03-07T18:00:00Z")
- confidence: "high" | "medium" | "low"
- reason: brief explanation

Return an EMPTY array [] if no transcripts match any events."""

    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=types.Schema(
            type=types.Type.ARRAY,
            items=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "event_id": types.Schema(type=types.Type.STRING),
                    "transcript_index": types.Schema(type=types.Type.INTEGER),
                    "event_start_utc": types.Schema(type=types.Type.STRING),
                    "confidence": types.Schema(type=types.Type.STRING),
                    "reason": types.Schema(type=types.Type.STRING),
                },
                required=["event_id", "transcript_index", "event_start_utc",
                           "confidence", "reason"],
            ),
        ),
    )

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=config,
            ),
        )

        matches_raw = json.loads(response.text)
    except Exception as e:
        print(f"[swing] Gemini matching error: {e}")
        # Fallback to fuzzy matching
        return _fallback_match(events, transcripts)

    # Group by event_id
    result: dict[str, list[dict[str, Any]]] = {}
    for m in matches_raw:
        eid = m.get("event_id", "")
        filtered_idx = m.get("transcript_index")
        start_utc = m.get("event_start_utc", "")
        confidence = m.get("confidence", "low")

        if filtered_idx is None or filtered_idx >= len(filtered_transcripts) or eid not in events:
            continue

        # Map back to original transcript
        orig_idx = transcript_index_map.get(filtered_idx, filtered_idx)
        if orig_idx >= len(transcripts):
            continue

        # Parse start time
        start_ts = _parse_utc_timestamp(start_utc)

        print(f"[swing] Gemini: event '{events[eid].get('title', '')[:50]}' "
              f"↔ transcript '{transcripts[orig_idx].get('name', '')[:50]}' "
              f"start={start_utc} conf={confidence} "
              f"reason={m.get('reason', '')[:60]}")

        result.setdefault(eid, []).append({
            "transcript": transcripts[orig_idx],
            "event_start_ts": start_ts,
            "confidence": confidence,
        })

    return result


def _fallback_match(
    events: dict[str, dict[str, Any]],
    transcripts: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Simple date+keyword fallback if Gemini fails."""
    print("[swing] using fallback matching (Gemini unavailable)")
    result: dict[str, list[dict[str, Any]]] = {}

    for eid, event in events.items():
        start_date = _parse_date(str(event.get("start_date", "")))
        end_date = _parse_date(str(event.get("end_date", "")))
        if not start_date or not end_date:
            continue

        title_words = _extract_keywords(event.get("title", ""))

        for t in transcripts:
            ud = t.get("upload_date", "")
            if not ud or len(ud) != 8:
                continue
            try:
                t_date = datetime(int(ud[:4]), int(ud[4:6]), int(ud[6:])).date()
            except (ValueError, TypeError):
                continue
            if not (start_date <= t_date <= end_date):
                continue

            t_name = (t.get("name") or "").lower()
            hits = sum(1 for kw in title_words if kw in t_name)
            needed = 2 if len(title_words) >= 4 else 1
            if hits < needed:
                continue

            # Assume 18:00 UTC
            start_ts = int(datetime(
                t_date.year, t_date.month, t_date.day, 18, 0, 0,
                tzinfo=timezone.utc
            ).timestamp())

            result.setdefault(eid, []).append({
                "transcript": t,
                "event_start_ts": start_ts,
                "confidence": "low",
            })

    return result


# =====================================================================
# Spike detection
# =====================================================================


def infer_event_start_from_prices(
    price_history: list[dict[str, Any]],
) -> int | None:
    """Infer when a live event started by finding when price volatility begins.

    Scans for the first significant price movement — that's when the event
    started and traders began reacting.
    """
    if len(price_history) < 10:
        return None

    for i in range(len(price_history) - 5):
        # Look at 5-point windows
        window = price_history[i:i + 6]
        p_start = window[0]["p"]
        max_move = max(abs(h["p"] - p_start) for h in window[1:])
        if max_move >= 0.02:  # 2c move = volatility starting
            return price_history[i]["t"]

    return None


def _detect_spikes(
    price_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Detect significant price movements in CLOB price history.

    Scans with a rolling window and finds moves > MIN_SPIKE_CENTS.
    Merges nearby spikes to avoid duplicates.
    """
    if len(price_history) < 2:
        return []

    spikes = []
    window_secs = SPIKE_WINDOW_MINUTES * 60

    i = 0
    while i < len(price_history):
        # Find the price point ~SPIKE_WINDOW_MINUTES ahead
        j = i + 1
        while j < len(price_history) and \
                price_history[j]["t"] - price_history[i]["t"] < window_secs:
            j += 1

        if j >= len(price_history):
            break

        p_before = price_history[i]["p"]
        p_after = price_history[j]["p"]
        magnitude = round(p_after - p_before, 4)

        if abs(magnitude) >= MIN_SPIKE_CENTS / 100:  # Convert cents to decimal
            spikes.append({
                "timestamp": price_history[j]["t"],
                "magnitude": magnitude,
                "price_before": round(p_before, 4),
                "price_after": round(p_after, 4),
            })
            # Skip ahead to avoid overlapping spikes
            i = j
        else:
            i += 1

    # Merge spikes within 2 minutes of each other (keep the larger one)
    if not spikes:
        return []

    merged = [spikes[0]]
    for s in spikes[1:]:
        if s["timestamp"] - merged[-1]["timestamp"] < 120:
            if abs(s["magnitude"]) > abs(merged[-1]["magnitude"]):
                merged[-1] = s
        else:
            merged.append(s)

    return merged


# =====================================================================
# Transcript timeline parsing
# =====================================================================


def _parse_transcript_timeline(
    transcript_text: str,
    event_start_ts: int,
) -> list[dict[str, Any]]:
    """Parse transcript with [MM:SS] timestamps into absolute-timed segments.

    Returns list of {abs_ts, offset_secs, time_label, speaker, text}
    """
    if not transcript_text:
        return []

    # Match [MM:SS] or [HH:MM:SS] at start of lines, followed by optional speaker
    segment_pattern = re.compile(
        r'^\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*'  # timestamp
        r'(?:([A-Z0-9][\w\s\-\'._()]{0,60}?):\s*)?'  # optional speaker
        r'(.*)',  # content
        re.MULTILINE
    )

    segments = []
    matches = list(segment_pattern.finditer(transcript_text))

    for i, match in enumerate(matches):
        time_str = match.group(1)
        speaker = (match.group(2) or "").strip()

        # Parse timestamp offset
        parts = time_str.split(":")
        if len(parts) == 2:
            offset_secs = int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 3:
            offset_secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        else:
            continue

        # Get all text until the next timestamp
        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(transcript_text)
        full_text = match.group(3) + transcript_text[start_pos:end_pos]
        full_text = full_text.strip()

        abs_ts = event_start_ts + offset_secs

        segments.append({
            "abs_ts": abs_ts,
            "offset_secs": offset_secs,
            "time_label": time_str,
            "speaker": speaker,
            "text": full_text,
        })

    return segments


def _get_words_around_spike(
    timeline: list[dict[str, Any]],
    spike_ts: int,
    lookback_min: int = 5,
) -> dict[str, Any] | None:
    """Find transcript content in the minutes before a price spike.

    Returns the concatenated text from segments in the lookback window,
    plus the speaker of the closest segment.
    """
    lookback_secs = lookback_min * 60
    window_start = spike_ts - lookback_secs

    relevant = [
        seg for seg in timeline
        if window_start <= seg["abs_ts"] <= spike_ts
    ]

    if not relevant:
        return None

    text = " ".join(seg["text"] for seg in relevant)
    # Speaker from the segment closest to the spike
    closest = min(relevant, key=lambda s: abs(s["abs_ts"] - spike_ts))

    return {
        "text": text,
        "time_label": f"{relevant[0]['time_label']}–{relevant[-1]['time_label']}",
        "speaker": closest.get("speaker", ""),
    }


# =====================================================================
# CLOB price history
# =====================================================================


async def _fetch_price_history(
    client: httpx.AsyncClient,
    poly_id: str,
    fidelity: int = 1,
) -> list[dict[str, Any]]:
    """Fetch CLOB price history for a market. Returns list of {t, p} dicts."""
    try:
        # Get clobTokenIds from Gamma
        gamma_resp = await client.get(f"{GAMMA_API_BASE}/markets?id={poly_id}")
        gamma_resp.raise_for_status()
        gamma_data = gamma_resp.json()

        if isinstance(gamma_data, list):
            gamma_data = gamma_data[0] if gamma_data else {}

        raw_clob = gamma_data.get("clobTokenIds")
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
                "fidelity": fidelity,
            },
        )
        clob_resp.raise_for_status()
        return clob_resp.json().get("history", [])

    except Exception as e:
        print(f"[swing] price history error for poly_id={poly_id}: {e}")
        return []


# =====================================================================
# Transcript fetching
# =====================================================================


async def _get_transcripts(persona_id: str | None) -> list[dict[str, Any]]:
    """Get transcripts, optionally filtered by persona."""
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


# =====================================================================
# Helpers
# =====================================================================


def _parse_utc_timestamp(s: str) -> int | None:
    """Parse an ISO UTC timestamp string to unix timestamp."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except (ValueError, TypeError):
        return None


def _parse_date(date_str: str) -> Any:
    """Parse a date string to a date object."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        pass
    try:
        return datetime.strptime(date_str[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


_FUZZY_STOP_WORDS = {
    "what", "will", "say", "this", "week", "during", "the", "a", "an", "and",
    "or", "at", "in", "on", "of", "to", "be", "said", "next", "event",
    "first", "episode", "remarks", "march", "april", "may", "june", "july",
    "august", "september", "october", "november", "december", "january",
    "february",
}


def _extract_keywords(title: str) -> list[str]:
    cleaned = re.sub(r'\([^)]*\)', '', title).replace('?', '')
    words = re.findall(r'[a-zA-Z]+', cleaned.lower())
    return [w for w in words if w not in _FUZZY_STOP_WORDS and len(w) > 2]


def _safe_avg(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0


def _safe_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0
    avg = _safe_avg(values)
    variance = sum((v - avg) ** 2 for v in values) / (len(values) - 1)
    return math.sqrt(variance)


def _empty_result() -> dict[str, Any]:
    return {
        "profiles": [],
        "spikes": [],
        "total_markets_analyzed": 0,
        "total_briefings": 0,
        "total_transcripts_available": 0,
        "total_spikes_detected": 0,
    }
