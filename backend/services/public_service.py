"""Public-facing service for unauthenticated/user-level access."""

import math
from typing import Any

from backend.core.database import get_supabase, get_folder_ids_in_tree


async def get_public_personas() -> list[dict[str, Any]]:
    """Fetch all personas for public listing."""
    supabase = get_supabase()

    personas_response = (
        supabase.table("personas")
        .select("id, name, description, slug, image_url, meta_title, meta_description, updated_at")
        .order("name")
        .execute()
    )
    personas = personas_response.data or []

    if not personas:
        return []

    # Get aliases grouped by persona
    aliases_response = supabase.table("persona_aliases").select("persona_id, alias").execute()
    aliases_by_persona: dict[str, list[str]] = {}
    for alias in aliases_response.data or []:
        pid = alias["persona_id"]
        aliases_by_persona.setdefault(pid, []).append(alias["alias"])

    for persona in personas:
        persona["aliases"] = aliases_by_persona.get(persona["id"], [])

    return personas


async def get_persona_by_slug(slug: str) -> dict[str, Any] | None:
    """Fetch a single persona by slug (or by id as fallback) with aliases."""
    supabase = get_supabase()

    response = (
        supabase.table("personas")
        .select("id, name, description, slug, image_url, meta_title, meta_description")
        .eq("slug", slug)
        .limit(1)
        .execute()
    )

    # Fallback: try matching by id (for personas without a slug)
    if not response.data:
        response = (
            supabase.table("personas")
            .select("id, name, description, slug, image_url, meta_title, meta_description")
            .eq("id", slug)
            .limit(1)
            .execute()
        )

    if not response.data:
        return None

    persona = response.data[0]

    aliases_response = (
        supabase.table("persona_aliases")
        .select("alias")
        .eq("persona_id", persona["id"])
        .execute()
    )
    persona["aliases"] = [a["alias"] for a in (aliases_response.data or [])]

    return persona


async def _find_transcript_ids_by_aliases(aliases: list[str]) -> set[str]:
    """Find transcript IDs where a speaker name matches any alias (case-insensitive)."""
    supabase = get_supabase()
    if not aliases:
        return set()

    # Find speakers whose name matches any alias (case-insensitive)
    speaker_ids: list[str] = []
    for alias in aliases:
        resp = (
            supabase.table("speakers")
            .select("id")
            .ilike("name", alias)
            .execute()
        )
        speaker_ids.extend(r["id"] for r in (resp.data or []))

    if not speaker_ids:
        return set()

    # Find transcript IDs linked to those speakers
    batch_size = 200
    transcript_ids: set[str] = set()
    unique_speaker_ids = list(set(speaker_ids))
    for i in range(0, len(unique_speaker_ids), batch_size):
        batch = unique_speaker_ids[i:i + batch_size]
        ts_resp = (
            supabase.table("transcript_speakers")
            .select("transcript_id")
            .in_("speaker_id", batch)
            .execute()
        )
        transcript_ids.update(r["transcript_id"] for r in (ts_resp.data or []))

    return transcript_ids


async def get_public_transcripts_for_persona(
    aliases: list[str],
    folder_id: str | None = None,
    search: str | None = None,
    sort_by: str = "date",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
    is_subscribed: bool = False,
) -> dict[str, Any]:
    """Find public transcripts where the persona is an actual speaker."""
    supabase = get_supabase()

    # Find transcript IDs where persona is a speaker (via aliases)
    matching_ids = await _find_transcript_ids_by_aliases(aliases)
    if not matching_ids:
        return {
            "items": [],
            "total": 0,
            "page": page,
            "page_size": page_size,
            "total_pages": 0,
        }

    # Query public transcripts limited to those IDs
    query = supabase.table("transcripts").select(
        "id, name, created_at, upload_date, folder_id, is_premium, transcript"
    ).eq("is_public", True).in_("id", list(matching_ids))

    if folder_id:
        folders_response = supabase.table("folders").select("*").execute()
        folders = folders_response.data or []
        tree_ids = get_folder_ids_in_tree(folder_id, folders)
        query = query.in_("folder_id", tree_ids)

    # Sort by upload_date (YouTube date) when sorting by date, fall back to created_at
    if sort_by == "date":
        query = query.order("upload_date", desc=(sort_order == "desc"), nullsfirst=False)
    else:
        query = query.order("name", desc=(sort_order == "desc"))

    response = query.execute()
    all_transcripts = response.data or []

    # Apply search filter if provided — only search non-premium transcripts
    # for non-subscribers to prevent probing premium content via search
    if search:
        search_lower = search.lower()
        all_transcripts = [
            t for t in all_transcripts
            if search_lower in (t.get("transcript") or "").lower()
            and (is_subscribed or not t.get("is_premium", False))
        ]

    total = len(all_transcripts)
    total_pages = max(1, math.ceil(total / page_size))

    # Paginate
    start = (page - 1) * page_size
    page_items = all_transcripts[start:start + page_size]

    # Get folder names for the page items
    folder_ids = list({t["folder_id"] for t in page_items if t.get("folder_id")})
    folder_names: dict[str, str] = {}
    if folder_ids:
        folders_resp = (
            supabase.table("folders")
            .select("id, name")
            .in_("id", folder_ids)
            .execute()
        )
        folder_names = {f["id"]: f["name"] for f in (folders_resp.data or [])}

    # Build summaries (strip full transcript text, add preview)
    items = []
    for t in page_items:
        is_premium = t.get("is_premium", False)
        transcript_text = t.get("transcript", "")

        # Don't leak premium transcript text as preview to non-subscribers
        preview = ""
        if not is_premium or is_subscribed:
            for line in transcript_text.split("\n"):
                stripped = line.strip()
                if stripped:
                    preview = stripped[:200]
                    break

        items.append({
            "id": t["id"],
            "name": t.get("name"),
            "created_at": t["created_at"],
            "upload_date": t.get("upload_date"),
            "is_premium": is_premium,
            "folder_id": t.get("folder_id"),
            "folder_name": folder_names.get(t.get("folder_id", ""), None),
            "preview": preview,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


async def keyword_search_for_persona(
    aliases: list[str],
    query: str,
    is_subscribed: bool = False,
) -> dict[str, Any]:
    """Search for a keyword across all of a persona's public transcripts.

    Free users: only non-premium transcripts are searched, limited to 3 matches with 1 snippet each.
    Subscribed: all public transcripts (including premium), full results up to 100 matches.
    """
    from backend.utils.nlp import search_term_in_context

    supabase = get_supabase()

    # Find transcript IDs for this persona
    matching_ids = await _find_transcript_ids_by_aliases(aliases)
    if not matching_ids:
        return {
            "query": query,
            "total_matches": 0,
            "transcripts_with_matches": 0,
            "matches": [],
            "is_limited": False,
        }

    # Fetch public transcripts — exclude premium for non-subscribers
    id_list = list(matching_ids)
    batch_size = 200
    all_transcripts: list[dict[str, Any]] = []
    for i in range(0, len(id_list), batch_size):
        batch = id_list[i:i + batch_size]
        q = (
            supabase.table("transcripts")
            .select("id, name, upload_date, transcript")
            .eq("is_public", True)
            .in_("id", batch)
        )
        if not is_subscribed:
            q = q.eq("is_premium", False)
        resp = q.execute()
        all_transcripts.extend(resp.data or [])

    if not all_transcripts:
        return {
            "query": query,
            "total_matches": 0,
            "transcripts_with_matches": 0,
            "matches": [],
            "is_limited": False,
        }

    result = search_term_in_context(all_transcripts, query, context_chars=150)

    total_matches = result["total_matches"]
    transcripts_with_matches = result["transcripts_with_matches"]
    matches = result["matches"]

    # Apply snippet limits for free users
    is_limited = False
    if not is_subscribed:
        FREE_TRANSCRIPT_LIMIT = 3
        FREE_SNIPPET_LIMIT = 1

        # Limit transcripts shown and snippets per transcript
        seen_transcripts: dict[str, int] = {}
        limited_matches: list[dict[str, Any]] = []
        for m in matches:
            tid = m["transcript_id"]
            if tid not in seen_transcripts:
                if len(seen_transcripts) >= FREE_TRANSCRIPT_LIMIT:
                    is_limited = True
                    continue
                seen_transcripts[tid] = 0
            if seen_transcripts[tid] >= FREE_SNIPPET_LIMIT:
                is_limited = True
                continue
            seen_transcripts[tid] += 1
            limited_matches.append(m)

        if len(seen_transcripts) < transcripts_with_matches or total_matches > len(limited_matches):
            is_limited = True
        matches = limited_matches

    return {
        "query": query,
        "total_matches": total_matches,
        "transcripts_with_matches": transcripts_with_matches,
        "matches": matches,
        "is_limited": is_limited,
    }


async def _find_personas_for_transcript(transcript_id: str) -> list[dict[str, Any]]:
    """Find persona(s) associated with a transcript via speakers + aliases."""
    supabase = get_supabase()

    # Get speaker names for this transcript
    ts_resp = (
        supabase.table("transcript_speakers")
        .select("speaker_id, speakers(name)")
        .eq("transcript_id", transcript_id)
        .execute()
    )
    if not ts_resp.data:
        return []

    speaker_names = [r["speakers"]["name"] for r in ts_resp.data if r.get("speakers")]

    if not speaker_names:
        return []

    # Find personas whose aliases match any speaker name
    aliases_resp = (
        supabase.table("persona_aliases")
        .select("persona_id, alias")
        .execute()
    )
    matching_persona_ids = set()
    for alias_row in aliases_resp.data or []:
        if alias_row["alias"].lower() in [s.lower() for s in speaker_names]:
            matching_persona_ids.add(alias_row["persona_id"])

    if not matching_persona_ids:
        return []

    # Fetch persona details
    personas_resp = (
        supabase.table("personas")
        .select("id, name, slug, image_url")
        .in_("id", list(matching_persona_ids))
        .execute()
    )
    return personas_resp.data or []


async def get_public_transcript(
    transcript_id: str,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    """Get a public transcript with access control."""
    supabase = get_supabase()

    response = (
        supabase.table("transcripts")
        .select("*")
        .eq("id", transcript_id)
        .eq("is_public", True)
        .single()
        .execute()
    )

    if not response.data:
        return None

    transcript = response.data
    is_premium = transcript.get("is_premium", False)
    is_locked = False

    if is_premium and user_id:
        # Check subscription
        has_sub = await check_user_subscription(user_id)
        if not has_sub:
            is_locked = True
    elif is_premium:
        is_locked = True

    if is_locked:
        # Truncate transcript for preview (100-word limit, break at last newline)
        full_text = transcript.get("transcript", "")
        words = full_text.split()
        if len(words) > 125:
            cut = " ".join(words[:125])
            # Try to break at last newline for clean cut
            last_nl = cut.rfind("\n")
            if last_nl > 0:
                cut = cut[:last_nl]
            transcript["transcript"] = cut

    transcript["is_locked"] = is_locked

    # Attach persona info for navigation breadcrumbs
    personas = await _find_personas_for_transcript(transcript_id)
    if personas:
        # Use the first persona as primary (most transcripts belong to one persona)
        p = personas[0]
        transcript["persona"] = {
            "name": p["name"],
            "slug": p.get("slug") or p["id"],
            "image_url": p.get("image_url"),
        }

    return transcript


async def get_transcript_neighbors(
    transcript_id: str,
    persona_slug: str,
) -> dict[str, Any]:
    """Get previous and next transcript IDs within a persona's transcript list (by date desc)."""
    supabase = get_supabase()

    # Resolve persona by slug
    persona_resp = (
        supabase.table("personas")
        .select("id, name, slug")
        .eq("slug", persona_slug)
        .single()
        .execute()
    )
    if not persona_resp.data:
        return {"prev": None, "next": None}

    persona_id = persona_resp.data["id"]

    # Get aliases
    aliases_resp = (
        supabase.table("persona_aliases")
        .select("alias")
        .eq("persona_id", persona_id)
        .execute()
    )
    aliases = [a["alias"] for a in (aliases_resp.data or [])]
    if not aliases:
        return {"prev": None, "next": None}

    # Find all transcript IDs for this persona
    matching_ids = await _find_transcript_ids_by_aliases(aliases)
    if not matching_ids or transcript_id not in matching_ids:
        return {"prev": None, "next": None}

    # Fetch ordered list of public transcripts
    id_list = list(matching_ids)
    all_transcripts: list[dict[str, Any]] = []
    batch_size = 200
    for i in range(0, len(id_list), batch_size):
        batch = id_list[i : i + batch_size]
        resp = (
            supabase.table("transcripts")
            .select("id, name, upload_date")
            .eq("is_public", True)
            .in_("id", batch)
            .order("upload_date", desc=True)
            .execute()
        )
        all_transcripts.extend(resp.data or [])

    # Sort combined results
    all_transcripts.sort(key=lambda t: t.get("upload_date") or "", reverse=True)

    # Find current index
    idx = next((i for i, t in enumerate(all_transcripts) if t["id"] == transcript_id), None)
    if idx is None:
        return {"prev": None, "next": None}

    prev_t = all_transcripts[idx - 1] if idx > 0 else None
    next_t = all_transcripts[idx + 1] if idx < len(all_transcripts) - 1 else None

    return {
        "prev": {"id": prev_t["id"], "name": prev_t.get("name")} if prev_t else None,
        "next": {"id": next_t["id"], "name": next_t.get("name")} if next_t else None,
    }


async def check_user_subscription(user_id: str) -> bool:
    """Check if user has an active subscription."""
    supabase = get_supabase()

    response = (
        supabase.table("subscriptions")
        .select("status")
        .eq("user_id", user_id)
        .eq("status", "active")
        .limit(1)
        .execute()
    )

    return bool(response.data)


def _is_event_active_kalshi(event: dict, markets_by_event: dict[str, list[dict]]) -> bool:
    """Check if a Kalshi event is still active (has at least one non-finalized market)."""
    event_markets = markets_by_event.get(event["id"], [])
    return any(m.get("status") == "active" for m in event_markets)


def _is_event_active_poly(event: dict) -> bool:
    """Check if a Polymarket event is still active (not closed and end_date in the future)."""
    from datetime import datetime, timezone
    if event.get("closed"):
        return False
    end_date = event.get("end_date")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            if end_dt < datetime.now(timezone.utc):
                return False
        except (ValueError, TypeError):
            pass
    return True


_COMMON_WORDS = {
    "the", "and", "for", "say", "will", "what", "press", "next",
    "this", "that", "with", "from", "during", "event", "week",
    "conference", "confrence", "transcripts", "transcript",
    "market", "markets", "mentions", "mention", "briefing",
}


def _build_persona_name_variants(name: str, aliases: list[str]) -> list[str]:
    """Build name variants for matching: full names, aliases, and surname parts.

    Only adds individual words as variants if they are 4+ chars and not common words.
    """
    variants = set()
    for n in [name] + aliases:
        n_lower = n.lower().strip()
        if n_lower:
            variants.add(n_lower)
            # Add individual words that are distinctive (4+ chars, not common)
            for part in n_lower.split():
                if len(part) >= 4 and part not in _COMMON_WORDS:
                    variants.add(part)
    return list(variants)


def _persona_excluded_from_event(
    persona_id: str,
    event_title: str,
    all_personas: dict[str, dict],
    all_aliases: dict[str, list[str]],
) -> bool:
    """Check if the event title names a DIFFERENT persona — if so, exclude this persona.

    If the event title contains another persona's name/alias but NOT this persona's,
    it means the event belongs to someone else and this persona was just cross-analyzed.
    """
    title_lower = (event_title or "").lower()
    if not title_lower:
        return False

    this_persona = all_personas.get(persona_id)
    if not this_persona:
        return False

    this_variants = _build_persona_name_variants(
        this_persona["name"], all_aliases.get(persona_id, [])
    )
    this_matches = any(v in title_lower for v in this_variants)

    # Check if any OTHER persona's name variants are in the title
    other_matches = False
    for pid, p in all_personas.items():
        if pid == persona_id:
            continue
        other_variants = _build_persona_name_variants(p["name"], all_aliases.get(pid, []))
        if any(v in title_lower for v in other_variants):
            other_matches = True
            break

    # Exclude only if another persona matches but this one doesn't
    return other_matches and not this_matches


async def get_public_markets_listing() -> list[dict[str, Any]]:
    """Get all market events grouped by persona for the public markets listing.

    Returns personas that have analyzed markets, with event summaries and top terms.
    Only shows active events where the persona is the subject of the event.
    """
    supabase = get_supabase()

    # Get Kalshi term results — only those with actual mentions
    kalshi_results = (
        supabase.table("market_term_results")
        .select("persona_id, market_id, search_term, total_mentions")
        .gt("total_mentions", 0)
        .execute()
    ).data or []

    # Get Polymarket term results — only those with actual mentions
    poly_results = (
        supabase.table("poly_market_term_results")
        .select("persona_id, market_id, search_term, total_mentions")
        .gt("total_mentions", 0)
        .execute()
    ).data or []

    # Collect all persona IDs
    persona_ids = list({r["persona_id"] for r in kalshi_results} | {r["persona_id"] for r in poly_results})
    if not persona_ids:
        return []

    # Fetch persona info + aliases for ownership matching
    personas_resp = (
        supabase.table("personas")
        .select("id, name, slug, image_url")
        .in_("id", persona_ids)
        .order("name")
        .execute()
    )
    personas = {p["id"]: p for p in (personas_resp.data or [])}

    # --- Kalshi: get market + event info ---
    kalshi_market_ids = list({r["market_id"] for r in kalshi_results})
    kalshi_markets: dict[str, dict] = {}
    if kalshi_market_ids:
        for i in range(0, len(kalshi_market_ids), 200):
            batch = kalshi_market_ids[i:i + 200]
            resp = (
                supabase.table("kalshi_markets")
                .select("id, event_id, question, last_price, result, status")
                .in_("id", batch)
                .execute()
            )
            for m in (resp.data or []):
                kalshi_markets[m["id"]] = m

    kalshi_event_ids = list({m["event_id"] for m in kalshi_markets.values()})
    kalshi_events: dict[str, dict] = {}
    if kalshi_event_ids:
        for i in range(0, len(kalshi_event_ids), 200):
            batch = kalshi_event_ids[i:i + 200]
            resp = (
                supabase.table("kalshi_events")
                .select("id, event_ticker, title, strike_date, status")
                .eq("show_public", True)
                .in_("id", batch)
                .execute()
            )
            for e in (resp.data or []):
                kalshi_events[e["id"]] = e

    # --- Polymarket: get market + event info ---
    poly_market_ids = list({r["market_id"] for r in poly_results})
    poly_markets: dict[str, dict] = {}
    if poly_market_ids:
        for i in range(0, len(poly_market_ids), 200):
            batch = poly_market_ids[i:i + 200]
            resp = (
                supabase.table("poly_markets")
                .select("id, event_id, question, last_trade_price, result, active, closed")
                .in_("id", batch)
                .execute()
            )
            for m in (resp.data or []):
                poly_markets[m["id"]] = m

    poly_event_ids = list({m["event_id"] for m in poly_markets.values()})
    poly_events: dict[str, dict] = {}
    if poly_event_ids:
        for i in range(0, len(poly_event_ids), 200):
            batch = poly_event_ids[i:i + 200]
            resp = (
                supabase.table("poly_events")
                .select("id, title, end_date, image, active, closed")
                .eq("show_public", True)
                .in_("id", batch)
                .execute()
            )
            for e in (resp.data or []):
                poly_events[e["id"]] = e

    # --- Group by persona → events ---
    persona_events: dict[str, dict[str, dict]] = {}

    # Process Kalshi results
    for r in kalshi_results:
        pid = r["persona_id"]
        persona = personas.get(pid)
        if not persona:
            continue
        market = kalshi_markets.get(r["market_id"])
        if not market:
            continue
        event = kalshi_events.get(market["event_id"])
        if not event:
            continue

        eid = event["id"]
        pe = persona_events.setdefault(pid, {})
        if eid not in pe:
            pe[eid] = {
                "source": "kalshi",
                "event_id": eid,
                "event_ticker": event.get("event_ticker"),
                "title": event.get("title", ""),
                "strike_date": event.get("strike_date"),
                "end_date": None,
                "status": "active",
                "image": None,
                "market_ids": set(),
                "terms": [],
            }
        pe[eid]["market_ids"].add(r["market_id"])
        pe[eid]["terms"].append({
            "term": r["search_term"],
            "mentions": r["total_mentions"],
            "price": int(round((market.get("last_price") or 0) * 100)),
        })

    # Process Polymarket results
    for r in poly_results:
        pid = r["persona_id"]
        persona = personas.get(pid)
        if not persona:
            continue
        market = poly_markets.get(r["market_id"])
        if not market:
            continue
        event = poly_events.get(market["event_id"])
        if not event:
            continue

        eid = event["id"]
        pe = persona_events.setdefault(pid, {})
        if eid not in pe:
            pe[eid] = {
                "source": "polymarket",
                "event_id": eid,
                "event_ticker": None,
                "title": event.get("title", ""),
                "strike_date": None,
                "end_date": event.get("end_date"),
                "status": "active",
                "image": event.get("image"),
                "market_ids": set(),
                "terms": [],
            }
        pe[eid]["market_ids"].add(r["market_id"])
        pe[eid]["terms"].append({
            "term": r["search_term"],
            "mentions": r["total_mentions"],
            "price": int(round((market.get("last_trade_price") or 0) * 100)),
        })

    # Build final response
    result = []
    for pid in persona_ids:
        persona = personas.get(pid)
        if not persona or pid not in persona_events:
            continue

        events = []
        for ev_data in persona_events[pid].values():
            # Deduplicate and sort terms by mentions desc, take top 3
            seen_terms: dict[str, dict] = {}
            for t in ev_data["terms"]:
                key = t["term"]
                if key not in seen_terms or t["mentions"] > seen_terms[key]["mentions"]:
                    seen_terms[key] = t
            top_terms = sorted(seen_terms.values(), key=lambda x: x["mentions"], reverse=True)[:3]

            events.append({
                "source": ev_data["source"],
                "event_id": ev_data["event_id"],
                "event_ticker": ev_data["event_ticker"],
                "title": ev_data["title"],
                "strike_date": ev_data["strike_date"],
                "end_date": ev_data["end_date"],
                "status": ev_data["status"],
                "image": ev_data["image"],
                "market_count": len(ev_data["market_ids"]),
                "top_terms": top_terms,
            })

        if not events:
            continue

        events.sort(key=lambda e: (e["title"] or ""))

        result.append({
            "persona": {
                "id": persona["id"],
                "name": persona["name"],
                "slug": persona.get("slug"),
                "image_url": persona.get("image_url"),
            },
            "events": events,
        })

    return result


async def get_public_persona_markets(
    slug: str,
    user_id: str | None = None,
) -> dict[str, Any] | None:
    """Get all market events and analysis for a persona (subscription-gated).

    Free users see market questions and prices but not analysis data.
    Subscribers see full mention counts, trends, and percentages.
    Only shows active events where the persona is the subject.
    """
    supabase = get_supabase()

    # Get persona + aliases
    persona = await get_persona_by_slug(slug)
    if not persona:
        return None

    pid = persona["id"]
    is_subscribed = False
    if user_id:
        is_subscribed = await check_user_subscription(user_id)

    # --- Kalshi term results for this persona (only with mentions) ---
    kalshi_results = (
        supabase.table("market_term_results")
        .select("market_id, search_term, total_mentions, briefings_with_term, total_briefings, percentage, trend")
        .eq("persona_id", pid)
        .gt("total_mentions", 0)
        .execute()
    ).data or []

    # Get Kalshi markets
    kalshi_market_ids = list({r["market_id"] for r in kalshi_results})
    kalshi_markets: dict[str, dict] = {}
    if kalshi_market_ids:
        for i in range(0, len(kalshi_market_ids), 200):
            batch = kalshi_market_ids[i:i + 200]
            resp = (
                supabase.table("kalshi_markets")
                .select("id, event_id, question, last_price, result, status, close_time")
                .in_("id", batch)
                .execute()
            )
            for m in (resp.data or []):
                kalshi_markets[m["id"]] = m

    # Get Kalshi events (only show_public)
    kalshi_event_ids = list({m["event_id"] for m in kalshi_markets.values()})
    kalshi_events: dict[str, dict] = {}
    if kalshi_event_ids:
        for i in range(0, len(kalshi_event_ids), 200):
            batch = kalshi_event_ids[i:i + 200]
            resp = (
                supabase.table("kalshi_events")
                .select("id, event_ticker, title, strike_date, status")
                .eq("show_public", True)
                .in_("id", batch)
                .execute()
            )
            for e in (resp.data or []):
                kalshi_events[e["id"]] = e

    # --- Polymarket term results for this persona (only with mentions) ---
    poly_results = (
        supabase.table("poly_market_term_results")
        .select("market_id, search_term, total_mentions, briefings_with_term, total_briefings, percentage, trend")
        .eq("persona_id", pid)
        .gt("total_mentions", 0)
        .execute()
    ).data or []

    # Get Poly markets
    poly_market_ids = list({r["market_id"] for r in poly_results})
    poly_markets: dict[str, dict] = {}
    if poly_market_ids:
        for i in range(0, len(poly_market_ids), 200):
            batch = poly_market_ids[i:i + 200]
            resp = (
                supabase.table("poly_markets")
                .select("id, event_id, question, last_trade_price, result, active, closed, closed_time")
                .in_("id", batch)
                .execute()
            )
            for m in (resp.data or []):
                poly_markets[m["id"]] = m

    # Get Poly events (only show_public)
    poly_event_ids = list({m["event_id"] for m in poly_markets.values()})
    poly_events: dict[str, dict] = {}
    if poly_event_ids:
        for i in range(0, len(poly_event_ids), 200):
            batch = poly_event_ids[i:i + 200]
            resp = (
                supabase.table("poly_events")
                .select("id, title, end_date, image, active, closed")
                .eq("show_public", True)
                .in_("id", batch)
                .execute()
            )
            for e in (resp.data or []):
                poly_events[e["id"]] = e

    # --- Group into events with markets ---
    events_map: dict[str, dict] = {}

    # Kalshi
    for r in kalshi_results:
        market = kalshi_markets.get(r["market_id"])
        if not market:
            continue
        event = kalshi_events.get(market["event_id"])
        if not event:
            continue

        eid = event["id"]
        if eid not in events_map:
            events_map[eid] = {
                "source": "kalshi",
                "event_id": eid,
                "event_ticker": event.get("event_ticker"),
                "title": event.get("title", ""),
                "strike_date": event.get("strike_date"),
                "end_date": None,
                "status": "active",
                "image": None,
                "markets": [],
            }

        market_entry: dict[str, Any] = {
            "market_id": market["id"],
            "question": market.get("question"),
            "search_term": r["search_term"],
            "price": int(round((market.get("last_price") or 0) * 100)),
            "result": market.get("result"),
            "status": market.get("status"),
        }

        if is_subscribed:
            market_entry.update({
                "total_mentions": r["total_mentions"],
                "briefings_with_term": r["briefings_with_term"],
                "total_briefings": r["total_briefings"],
                "percentage": r["percentage"],
                "trend": r["trend"],
            })

        events_map[eid]["markets"].append(market_entry)

    # Polymarket
    for r in poly_results:
        market = poly_markets.get(r["market_id"])
        if not market:
            continue
        event = poly_events.get(market["event_id"])
        if not event:
            continue

        eid = event["id"]
        if eid not in events_map:
            events_map[eid] = {
                "source": "polymarket",
                "event_id": eid,
                "event_ticker": None,
                "title": event.get("title", ""),
                "strike_date": None,
                "end_date": event.get("end_date"),
                "status": "active",
                "image": event.get("image"),
                "markets": [],
            }

        market_entry = {
            "market_id": market["id"],
            "question": market.get("question"),
            "search_term": r["search_term"],
            "price": int(round((market.get("last_trade_price") or 0) * 100)),
            "result": market.get("result"),
            "status": "closed" if market.get("closed") else "active",
        }

        if is_subscribed:
            market_entry.update({
                "total_mentions": r["total_mentions"],
                "briefings_with_term": r["briefings_with_term"],
                "total_briefings": r["total_briefings"],
                "percentage": r["percentage"],
                "trend": r["trend"],
            })

        events_map[eid]["markets"].append(market_entry)

    # Sort events by title
    events = sorted(events_map.values(), key=lambda e: (e["title"] or ""))

    # Sort markets within each event by mentions (desc) if subscribed, else by price
    for event in events:
        if is_subscribed:
            event["markets"].sort(key=lambda m: m.get("total_mentions", 0), reverse=True)
        else:
            event["markets"].sort(key=lambda m: m.get("price", 0), reverse=True)

    return {
        "persona": {
            "id": persona["id"],
            "name": persona["name"],
            "slug": persona.get("slug"),
            "image_url": persona.get("image_url"),
            "description": persona.get("description"),
        },
        "events": events,
        "is_limited": not is_subscribed,
    }
