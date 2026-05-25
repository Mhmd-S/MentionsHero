"""LLM-driven extraction of per-transcript metadata.

Two-call architecture (locked in via Phase 0 spike):
  Call A: location/venue/audience/event_time_local — Gemini sees title,
          description, DDG snippets, transcript excerpt. Venue extraction
          prioritizes DDG snippets (room-level detail lives there).
  Call B: event_type — Gemini sees the title only. Strict 16-rule mapping.

All outputs are SUGGESTIONS — the admin-confirm UI is the source of truth.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from ddgs import DDGS
from google import genai
from google.genai import types

from backend.config import get_settings
from backend.core.database import get_analytical_table, get_supabase

logger = logging.getLogger(__name__)


GEMINI_MODEL = "gemini-3-flash-preview"
DESCRIPTION_CHARS = 1500
TRANSCRIPT_EXCERPT_CHARS = 2000
DDG_MAX_RESULTS = 10
DDG_SNIPPET_CHARS = 1800

# Per-call wall-clock timeouts (seconds). Each is generous but bounded so a
# single hung video/network/API can't stall the whole bulk run.
DDG_TIMEOUT = 20
GEMINI_TIMEOUT = 30
YTDLP_TIMEOUT = 45
PROGRESS_FLUSH_EVERY = 5  # update procurement_runs.items_new every N transcripts

EVENT_TYPES = [
    "rally", "press_conference", "press_briefing", "interview",
    "prepared_remarks", "signing_ceremony", "bilateral_meeting",
    "cabinet_meeting", "reception", "ceremony", "summit", "roundtable",
    "announcement", "greeting", "troop_address", "other",
]

AUDIENCE_TYPES = [
    "supporters", "general", "press", "congress", "foreign", "military",
    "cabinet", "invited", "industry", "mixed", "other",
]

_AUDIENCE_RULES = """\
- supporters: political supporters (rally crowd)
- general: general public
- press: journalists / media corps
- congress: members of congress
- foreign: foreign leaders / delegations
- military: troops, service members
- cabinet: cabinet, admin officials, staff
- invited: invited guests (receptions, ceremonies)
- industry: business leaders, sector representatives
- mixed: combination of the above
- other: doesn't fit
"""


# ---------------------------------------------------------------------------
# DDG search
# ---------------------------------------------------------------------------

def _ddg_search(query: str) -> str:
    """Return a combined snippet string from DuckDuckGo text search.
    Returns empty string on failure — never raises."""
    try:
        results = list(DDGS().text(query, max_results=DDG_MAX_RESULTS))
    except Exception as e:
        logger.warning("DDG search failed for %r: %s", query, e)
        return ""
    snippets: list[str] = []
    for r in results:
        title = (r.get("title") or "").strip()
        body = (r.get("body") or "").strip()
        if title or body:
            snippets.append(f"- {title} — {body}")
    return "\n".join(snippets)[:DDG_SNIPPET_CHARS]


# ---------------------------------------------------------------------------
# Call A: location / venue / audience / event_time_local
# ---------------------------------------------------------------------------

def _build_location_prompt(
    title: str, description: str, transcript_excerpt: str, web_snippets: str
) -> str:
    return f"""You are extracting event metadata from a YouTube video about a US political speech or appearance.

Use these inputs. PRIORITY DIFFERS BY FIELD:

  - For `city` / `state` / `country`: VIDEO TITLE is the primary signal, then VIDEO DESCRIPTION, then WEB SEARCH SNIPPETS, then TRANSCRIPT EXCERPT.
  - For `venue`: WEB SEARCH SNIPPETS are the PRIMARY signal — room-level detail (East Room, Rose Garden, Oval Office, Brady Press Briefing Room, etc.) almost always comes from news articles, not the title or description. Fall back to TRANSCRIPT EXCERPT and VIDEO DESCRIPTION only if web snippets don't name the venue. Do NOT guess a venue from the title alone.
  - For `audience_type`: use ALL inputs holistically.
  - (event_type is classified separately from the title only — not part of this call.)

Return ONLY these fields. Use null if you cannot find a confident value.

  - city: city name only, no state suffix (e.g. "Phoenix")
  - state: US state name (full name, e.g. "Arizona"); for DC use "District of Columbia"; null for non-US events
  - country: full country name. Default to "US" for US events. Use the actual country for non-US events ("Japan", "Malaysia", etc.)
  - county: US county name if you can infer it from the city (e.g. Phoenix -> "Maricopa"); null otherwise
  - venue: building / facility name if mentioned (e.g. "The White House", "Mar-a-Lago", "Madison Square Garden"). Be as specific as the inputs allow. If the inputs name a specific room or sub-location (e.g. "East Room of the White House", "Rose Garden", "Briefing Room"), include it here — prefer the most specific form actually stated.
  - audience_type: pick from:
{_AUDIENCE_RULES}
  - event_time_local: best guess of the event's start time in HH:MM (24-hour) local time, if any input states it (e.g. titles like "3 PM ET" or descriptions saying "spoke at 14:30"). null if not stated.
  - confidence: number 0..1 — your confidence in the overall extraction

VIDEO TITLE:
{title or "(empty)"}

WEB SEARCH SNIPPETS (DuckDuckGo, query roughly "Trump {{title}}"):
{web_snippets or "(empty)"}

VIDEO DESCRIPTION:
{description or "(empty)"}

TRANSCRIPT EXCERPT (first ~{TRANSCRIPT_EXCERPT_CHARS} chars):
{transcript_excerpt or "(empty)"}
"""


def _location_response_schema() -> types.Schema:
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "city": types.Schema(type=types.Type.STRING, nullable=True),
            "state": types.Schema(type=types.Type.STRING, nullable=True),
            "country": types.Schema(type=types.Type.STRING, nullable=True),
            "county": types.Schema(type=types.Type.STRING, nullable=True),
            "venue": types.Schema(type=types.Type.STRING, nullable=True),
            "audience_type": types.Schema(type=types.Type.STRING, enum=AUDIENCE_TYPES, nullable=True),
            "event_time_local": types.Schema(type=types.Type.STRING, nullable=True),
            "confidence": types.Schema(type=types.Type.NUMBER),
        },
        required=["confidence"],
    )


# ---------------------------------------------------------------------------
# Call B: event_type from title only
# ---------------------------------------------------------------------------

def _build_event_type_prompt(title: str) -> str:
    return f"""Classify the YouTube video title below into a single event_type.

Use ONLY the title. Ignore everything else.

IMPORTANT: Check rules in the order listed. The FIRST rule whose condition is satisfied wins, even if a later rule would also match. In particular, ceremony triggers (rule #14) MUST be checked before prepared_remarks (rule #15) — so "Delivers Remarks at the Congressional Ball" becomes `ceremony`, not `prepared_remarks`.

1. If the title contains "Cabinet Meeting" -> cabinet_meeting
2. If the title contains "Bilateral Meeting" / "Bilateral Lunch" / "Bilateral Dinner" / "Bilateral Breakfast" OR matches the pattern "(Meeting|Lunch|Dinner|Breakfast|Tea|Working Lunch|Working Dinner) with the (Secretary General|President|Prime Minister|King|Queen|Chancellor|Crown Prince|Ambassador|Premier|Emir|Sultan|Chairman|Foreign Minister|Director|Vice President) of [country/org]" -> bilateral_meeting
3. If the title contains "Signing Ceremony" / "Bill Signing" / "Signs " / "Signing with" -> signing_ceremony
4. If the title contains "Press Conference" -> press_conference
5. If the title contains "Press Briefing" / "Briefs Members of the Media" / "Briefs the Media" -> press_briefing
6. If the title contains "Rally" -> rally
7. If the title contains "Interview" / "Sits Down with" / "Joins " (network name) -> interview
8. If the title contains "Reception" -> reception
9. If the title contains "Roundtable" / "Task Force" / "Listening Session" -> roundtable
10. If the title contains "Summit" -> summit
11. If the title contains "Announcement" / "Makes an Announcement" / "Announces" -> announcement
12. If the title contains "Greeting" / "Welcomes" / "Photo Op" -> greeting
13. If the title contains "Troop" / "Troops" / "Address to the Military" / "Service Members" -> troop_address
14. If the title contains any of: "Halloween", "Easter", "Christmas", "Thanksgiving", "Turkey Pardoning", "Mother's Day", "Father's Day", "Veterans Day", "Memorial Day", "Independence Day", "Medal of Honor", "Medal Presentation", "Honors", "State Dinner", "Hanukkah", "Tree Lighting", "Awards", "Swearing-In", "Ball", "Gala", "Inauguration" -> ceremony
15. If the title contains "Delivers Remarks" / "Remarks at" / "Remarks on" / "Address to" / "Speech" -> prepared_remarks
16. Otherwise -> other

Allowed event_types: {EVENT_TYPES}

Return JSON with:
  - event_type: one of the allowed values
  - matched_rule: the rule number that fired (1-16), or null if none applied

VIDEO TITLE:
{title or "(empty)"}
"""


def _event_type_response_schema() -> types.Schema:
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "event_type": types.Schema(type=types.Type.STRING, enum=EVENT_TYPES),
            "matched_rule": types.Schema(type=types.Type.INTEGER, nullable=True),
        },
        required=["event_type"],
    )


# ---------------------------------------------------------------------------
# Gemini call wrappers
# ---------------------------------------------------------------------------

async def _call_gemini(
    client: genai.Client, prompt: str, schema: types.Schema
) -> dict | None:
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
    )
    loop = asyncio.get_event_loop()
    try:
        response = await asyncio.wait_for(
            loop.run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=[types.Part.from_text(text=prompt)],
                    config=config,
                ),
            ),
            timeout=GEMINI_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("Gemini metadata extraction timed out after %ds", GEMINI_TIMEOUT)
        return None
    except Exception as e:
        logger.warning("Gemini metadata extraction failed: %s", e)
        return None
    text = (response.text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning("Gemini metadata returned non-JSON: %s", e)
        return None


# ---------------------------------------------------------------------------
# Event time derivation (factual, not LLM-inferred)
# ---------------------------------------------------------------------------

def compute_event_time(
    was_live: bool | None,
    release_timestamp: int | None,
    timestamp: int | None,
) -> datetime | None:
    """Return release_timestamp for livestream VODs (matches the actual
    stream-start time), else fall back to the upload timestamp.

    Verified in the Phase 0 spike: for `was_live=True` livestreams, the yt-dlp
    `release_timestamp` matches DDG-reported event start times to within ~2
    minutes. The upload `timestamp` was consistently 1–2 hours later.
    """
    if was_live and release_timestamp:
        try:
            return datetime.fromtimestamp(release_timestamp, tz=timezone.utc)
        except (ValueError, OSError):
            pass
    if timestamp:
        try:
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (ValueError, OSError):
            pass
    return None


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------

async def extract_metadata(
    title: str,
    description: str,
    transcript_text: str,
    persona_name: str = "Trump",
) -> dict:
    """Run both LLM calls and return a dict ready to upsert into event_tags.

    Returns the extracted fields plus `classification_source='auto_llm'` and
    `confidence`. Any field the LLM could not determine is null. If both calls
    fail entirely, returns at least {"classification_source": "auto_llm",
    "confidence": 0.0} so the caller can still upsert a placeholder row.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        logger.warning("GEMINI_API_KEY not set — skipping metadata extraction")
        return {}

    client = genai.Client(api_key=settings.gemini_api_key)

    description = (description or "")[:DESCRIPTION_CHARS]
    transcript_excerpt = (transcript_text or "")[:TRANSCRIPT_EXCERPT_CHARS]

    # DDG search runs in a thread because the lib is synchronous.
    loop = asyncio.get_event_loop()
    ddg_query = f"{persona_name} {title}".strip()
    try:
        web_snippets = await asyncio.wait_for(
            loop.run_in_executor(None, _ddg_search, ddg_query),
            timeout=DDG_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("DDG search timed out after %ds for %r", DDG_TIMEOUT, ddg_query[:80])
        web_snippets = ""

    location_prompt = _build_location_prompt(
        title, description, transcript_excerpt, web_snippets
    )
    event_type_prompt = _build_event_type_prompt(title)

    location_task = _call_gemini(client, location_prompt, _location_response_schema())
    event_type_task = _call_gemini(client, event_type_prompt, _event_type_response_schema())
    location_result, event_type_result = await asyncio.gather(
        location_task, event_type_task
    )

    result: dict = {"classification_source": "auto_llm"}
    if location_result:
        for field in ("city", "state", "country", "venue", "audience_type", "event_time_local"):
            val = location_result.get(field)
            if val is not None:
                result[field] = val
        result["confidence"] = location_result.get("confidence") or 0.0
    else:
        result["confidence"] = 0.0

    if event_type_result and event_type_result.get("event_type"):
        result["event_type"] = event_type_result["event_type"]
    # No fallback event_type here — the caller (jobs.py) can default to "other"
    # or skip the upsert. The keyword classifier in analytical_event_tag_service
    # remains available as a separate fallback path.

    return result


# ---------------------------------------------------------------------------
# Single-transcript backfill (shared by jobs.py and the bulk backfiller)
# ---------------------------------------------------------------------------

async def populate_for_transcript(
    transcript_id: str,
    title: str,
    description: str,
    transcript_text: str,
    was_live: bool | None,
    release_timestamp: int | None,
    timestamp: int | None,
    persona_id: str | None = None,
) -> dict:
    """Run extraction + upsert for one transcript. Returns a status dict
    suitable for inclusion in procurement_runs.details.

    Used by:
      - jobs.py (single-transcript on creation)
      - bulk_backfill_metadata (one row per call)
      - the CLI backfill script

    Best-effort — failures are caught and surfaced in the return value;
    they don't raise to the caller.
    """
    # Import here to avoid circular import on module load — context service
    # transitively imports from this module via analytical router pieces.
    from backend.services.analytical_context_service import compute_context_window

    try:
        extracted = await extract_metadata(
            title=title or "",
            description=description or "",
            transcript_text=transcript_text or "",
        )
    except Exception as e:
        logger.warning("extract_metadata crashed for %s: %s", transcript_id, e)
        extracted = {}

    event_time = compute_event_time(
        was_live=bool(was_live),
        release_timestamp=release_timestamp,
        timestamp=timestamp,
    )

    row: dict = {
        "transcript_id": transcript_id,
        "event_type": extracted.get("event_type") or "other",
        "classification_source": extracted.get("classification_source", "auto_llm"),
    }
    for key in ("city", "state", "country", "venue", "audience_type", "event_time_local"):
        if extracted.get(key) is not None:
            row[key] = extracted[key]
    if extracted.get("confidence") is not None:
        row["confidence"] = extracted["confidence"]
    if event_time is not None:
        row["event_time"] = event_time.isoformat()

    status: dict = {
        "transcript_id": transcript_id,
        "event_type": row.get("event_type"),
        "city": row.get("city"),
        "venue": row.get("venue"),
        "action": "extracted",
    }
    try:
        get_analytical_table("event_tags").upsert(
            row, on_conflict="transcript_id"
        ).execute()
    except Exception as e:
        logger.warning("event_tag upsert failed for %s: %s", transcript_id, e)
        status["action"] = "upsert_failed"
        status["error"] = str(e)
        return status

    if persona_id:
        try:
            await compute_context_window(
                transcript_id=transcript_id,
                persona_id=persona_id,
                hours_before=72,
            )
            status["context_window"] = "computed"
        except Exception as e:
            logger.info("context_window skipped for %s: %s", transcript_id, e)
            status["context_window"] = f"skipped: {e}"
    return status


# ---------------------------------------------------------------------------
# Bulk backfill across all of a persona's transcripts
# ---------------------------------------------------------------------------

RATE_LIMIT_SECONDS = 0.5


def _persona_transcript_pool(persona_name_filter: str) -> list[dict]:
    """All transcripts that have a speaker whose name matches the filter
    (case-insensitive) and have a youtube_url + a non-empty transcript."""
    supabase = get_supabase()
    speakers = (
        supabase.table("speakers")
        .select("id")
        .ilike("name", f"%{persona_name_filter}%")
        .execute()
    )
    speaker_ids = [s["id"] for s in (speakers.data or [])]
    if not speaker_ids:
        return []

    ts = (
        supabase.table("transcript_speakers")
        .select("transcript_id")
        .in_("speaker_id", speaker_ids)
        .execute()
    )
    transcript_ids = list({r["transcript_id"] for r in (ts.data or [])})
    if not transcript_ids:
        return []

    rows: list[dict] = []
    CHUNK = 200
    for i in range(0, len(transcript_ids), CHUNK):
        chunk = transcript_ids[i:i + CHUNK]
        resp = (
            supabase.table("transcripts")
            .select("id, name, youtube_url, upload_date, transcript")
            .in_("id", chunk)
            .neq("youtube_url", "")
            .not_.is_("transcript", "null")
            .execute()
        )
        rows.extend(r for r in (resp.data or []) if r.get("transcript"))
    return rows


async def bulk_backfill_metadata(
    persona_id: str,
    force: bool = False,
    limit: int | None = None,
) -> dict:
    """Backfill the metadata bundle for every transcript belonging to a
    persona. Mirrors the bulk_auto_tag pattern: creates a procurement_runs
    row, processes each transcript, writes counts back.

    Skips transcripts whose existing event_tag has
    `classification_source='manual'` unless `force=True`.

    Re-fetches YouTube info via yt-dlp for each transcript (so
    release_timestamp / description are current).
    """
    # Import here to avoid pulling yt-dlp on module load.
    from backend.services.youtube_service import get_video_info

    supabase = get_supabase()

    # Resolve persona name for the speaker filter.
    persona_resp = (
        supabase.table("personas")
        .select("id, name")
        .eq("id", persona_id)
        .single()
        .execute()
    )
    if not persona_resp.data:
        raise ValueError("Persona not found")
    persona_name = persona_resp.data.get("name") or ""

    # Audit row first so failures still leave a trail.
    run_resp = get_analytical_table("procurement_runs").insert({
        "source_type": "metadata_backfill",
        "persona_id": persona_id,
        "status": "running",
    }).execute()
    run_id = run_resp.data[0]["id"]

    try:
        candidates = _persona_transcript_pool(persona_name)

        # Skip rows that an admin has already confirmed manually.
        if not force:
            existing = (
                get_analytical_table("event_tags")
                .select("transcript_id, classification_source")
                .execute()
            )
            manual_ids = {
                r["transcript_id"] for r in (existing.data or [])
                if r.get("classification_source") == "manual"
            }
            candidates = [t for t in candidates if t["id"] not in manual_ids]

        if limit is not None:
            candidates = candidates[:limit]

        total = len(candidates)
        logger.info("metadata backfill: starting run %s with %d candidates", run_id, total)
        succeeded = 0
        failed = 0
        details: list[dict] = []

        def _flush_progress() -> None:
            try:
                get_analytical_table("procurement_runs").update({
                    "items_found": total,
                    "items_new": succeeded,
                    "items_skipped": failed,
                }).eq("id", run_id).execute()
            except Exception as e:
                logger.warning("progress flush failed: %s", e)

        for i, t in enumerate(candidates, 1):
            name = t.get("name") or "(no name)"
            logger.info("metadata backfill [%d/%d]: %s", i, total, name[:80])

            # yt-dlp with timeout — most common hang source.
            try:
                video_info = await asyncio.wait_for(
                    get_video_info(t["youtube_url"]),
                    timeout=YTDLP_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning("  yt-dlp timed out after %ds — skipping", YTDLP_TIMEOUT)
                failed += 1
                details.append({
                    "transcript_id": t["id"],
                    "name": name,
                    "action": "ytdlp_timeout",
                })
                if i % PROGRESS_FLUSH_EVERY == 0:
                    _flush_progress()
                await asyncio.sleep(RATE_LIMIT_SECONDS)
                continue
            except Exception as e:
                logger.warning("  yt-dlp failed: %s", e)
                failed += 1
                details.append({
                    "transcript_id": t["id"],
                    "name": name,
                    "action": "ytdlp_failed",
                    "error": str(e),
                })
                if i % PROGRESS_FLUSH_EVERY == 0:
                    _flush_progress()
                await asyncio.sleep(RATE_LIMIT_SECONDS)
                continue

            # Wrap populate_for_transcript with a generous overall budget too,
            # in case both Gemini calls time out simultaneously.
            try:
                status = await asyncio.wait_for(
                    populate_for_transcript(
                        transcript_id=t["id"],
                        title=video_info.title or name,
                        description=video_info.description or "",
                        transcript_text=t.get("transcript") or "",
                        was_live=video_info.was_live,
                        release_timestamp=video_info.release_timestamp,
                        timestamp=video_info.timestamp,
                        persona_id=persona_id,
                    ),
                    timeout=GEMINI_TIMEOUT * 3 + DDG_TIMEOUT,  # generous total budget
                )
            except asyncio.TimeoutError:
                logger.warning("  populate_for_transcript timed out — skipping")
                failed += 1
                details.append({
                    "transcript_id": t["id"],
                    "name": name,
                    "action": "populate_timeout",
                })
                if i % PROGRESS_FLUSH_EVERY == 0:
                    _flush_progress()
                await asyncio.sleep(RATE_LIMIT_SECONDS)
                continue

            status["name"] = name
            if status.get("action") == "extracted":
                succeeded += 1
                logger.info("  -> %s | %s | %s",
                            status.get("event_type"), status.get("city"), status.get("venue"))
            else:
                failed += 1
                logger.info("  -> %s", status.get("action"))
            details.append(status)
            if i % PROGRESS_FLUSH_EVERY == 0:
                _flush_progress()
            await asyncio.sleep(RATE_LIMIT_SECONDS)

        get_analytical_table("procurement_runs").update({
            "status": "completed",
            "items_found": total,
            "items_new": succeeded,
            "items_skipped": failed,
            "details": details,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()

        logger.info(
            "metadata backfill (persona=%s): succeeded=%d failed=%d",
            persona_id, succeeded, failed,
        )
        return {
            "run_id": run_id,
            "candidates": len(candidates),
            "succeeded": succeeded,
            "failed": failed,
        }

    except Exception as e:
        logger.error("metadata backfill crashed: %s", e, exc_info=True)
        get_analytical_table("procurement_runs").update({
            "status": "failed",
            "error_message": str(e),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
        return {"run_id": run_id, "candidates": 0, "succeeded": 0, "failed": 0}
