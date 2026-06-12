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
from backend.services.transcription_service import with_retry

logger = logging.getLogger(__name__)


GEMINI_MODEL = "gemini-3-flash-preview"
DESCRIPTION_CHARS = 1500
TRANSCRIPT_EXCERPT_CHARS = 2000
DDG_MAX_RESULTS = 10
DDG_SNIPPET_CHARS = 1800

# Per-call wall-clock timeouts (seconds). Each is generous but bounded so a
# single hung video/network/API can't stall the whole bulk run.
#
# GEMINI_TIMEOUT was 30s, which routinely cut off `gemini-3-flash-preview`
# (a thinking model) mid-response — the swallowed timeout was the root cause of
# the "everything null" bug. The working transcription path has no such cap and
# wraps calls in `with_retry`; we now mirror both.
DDG_TIMEOUT = 20
GEMINI_TIMEOUT = 120
YTDLP_TIMEOUT = 45
PROGRESS_FLUSH_EVERY = 5  # update procurement_runs.items_new every N transcripts
# Transcripts processed in parallel during a backfill. Each fires 2 Gemini calls,
# so peak in-flight requests ≈ BULK_CONCURRENCY * 2. Kept low (matches the
# auto_semaphore=3 cap elsewhere) to avoid 429 rate-limit storms.
BULK_CONCURRENCY = 3

EVENT_TYPES = [
    "rally", "press_conference", "press_briefing", "interview",
    "prepared_remarks", "signing_ceremony", "bilateral_meeting",
    "cabinet_meeting", "reception", "ceremony", "summit", "roundtable",
    "announcement", "greeting", "troop_address", "other",
]

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
  - (event_type is classified separately from the title only — not part of this call.)

Return ONLY these fields. Use null if you cannot find a confident value.

  - city: city name only, no state suffix (e.g. "Phoenix")
  - state: US state name (full name, e.g. "Arizona"); for DC use "District of Columbia"; null for non-US events
  - country: full country name. Default to "US" for US events. Use the actual country for non-US events ("Japan", "Malaysia", etc.)
  - venue: building / facility name if mentioned (e.g. "The White House", "Mar-a-Lago", "Madison Square Garden"). Be as specific as the inputs allow. If the inputs name a specific room or sub-location (e.g. "East Room of the White House", "Rose Garden", "Briefing Room"), include it here — prefer the most specific form actually stated.
  - event_datetime_utc: if you can determine the FULL event start (date AND time) from the inputs, return it as an ISO-8601 UTC timestamp like "2026-05-07T15:47:00Z". Try hard — TITLES often embed it (e.g. "May 7, 2026 15:47"), DDG snippets often include it (e.g. "5/19/26 1250 hours" or "at 3 p.m. ET on May 21"), and transcripts sometimes open with the date. Convert any local-time references to UTC using these defaults: White House / DC / Florida → ET (UTC-5 in winter, UTC-4 in summer); California → PT; if you can't determine the timezone, assume ET. null if no time can be determined.
  - primary_source: which input the location came from — one of ["title", "web", "description", "transcript", "none"]
  - reasoning: one short sentence explaining what you used and why any field is null

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
            "venue": types.Schema(type=types.Type.STRING, nullable=True),
            "event_datetime_utc": types.Schema(type=types.Type.STRING, nullable=True),
            "primary_source": types.Schema(
                type=types.Type.STRING,
                enum=["title", "web", "description", "transcript", "none"],
            ),
            "reasoning": types.Schema(type=types.Type.STRING),
        },
        required=["primary_source", "reasoning"],
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

def _usage_from_response(response) -> dict:
    """Best-effort extract token counts from a Gemini response."""
    meta = getattr(response, "usage_metadata", None)
    if not meta:
        return {"prompt_tokens": 0, "completion_tokens": 0}
    return {
        "prompt_tokens": int(getattr(meta, "prompt_token_count", 0) or 0),
        "completion_tokens": int(getattr(meta, "candidates_token_count", 0) or 0),
    }


_ZERO_USAGE = {"prompt_tokens": 0, "completion_tokens": 0}


def _finish_reason(response) -> str | None:
    """Best-effort extract the finish_reason of the first candidate (catches
    MAX_TOKENS / safety blocks that produce an empty `.text`)."""
    try:
        fr = response.candidates[0].finish_reason
        return str(getattr(fr, "name", fr)) if fr is not None else None
    except (AttributeError, IndexError, TypeError):
        return None


async def _call_gemini(
    client: genai.Client, prompt: str, schema: types.Schema, *, label: str = "metadata"
) -> tuple[dict | None, dict, dict]:
    """Run one structured-output Gemini call.

    Returns (parsed_json | None, usage_dict, diag_dict). `usage_dict` is always
    present (zeroed on failure). `diag_dict` is {"error", "raw", "finish_reason"}
    and is the ONLY place a failure reason is recorded — callers surface it into
    procurement_runs.details so an empty row is never indistinguishable from a
    failed extraction.

    Mirrors the working transcription path: wrapped in `with_retry` (retries
    429/5xx/rate-limit) and given a generous timeout instead of the old 30s cap
    that was silently truncating the thinking model.
    """
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
    )
    loop = asyncio.get_event_loop()

    async def _generate():
        return await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[types.Part.from_text(text=prompt)],
                config=config,
            ),
        )

    try:
        response = await asyncio.wait_for(
            with_retry(_generate, service_name=f"Gemini ({label})"),
            timeout=GEMINI_TIMEOUT,
        )
    except asyncio.TimeoutError:
        msg = f"timed out after {GEMINI_TIMEOUT}s"
        logger.error("Gemini %s extraction %s", label, msg)
        return None, dict(_ZERO_USAGE), {"error": msg, "raw": None, "finish_reason": None}
    except Exception as e:
        logger.error("Gemini %s extraction failed: %s", label, e)
        return None, dict(_ZERO_USAGE), {"error": f"call failed: {e}", "raw": None, "finish_reason": None}

    usage = _usage_from_response(response)
    finish = _finish_reason(response)
    text = (response.text or "").strip()
    if not text:
        msg = f"empty response (finish_reason={finish})"
        logger.error("Gemini %s extraction returned %s", label, msg)
        return None, usage, {"error": msg, "raw": None, "finish_reason": finish}
    try:
        return json.loads(text), usage, {"error": None, "raw": None, "finish_reason": finish}
    except json.JSONDecodeError as e:
        logger.error("Gemini %s extraction returned non-JSON: %s", label, e)
        return None, usage, {"error": f"non-JSON: {e}", "raw": text[:500], "finish_reason": finish}


# ---------------------------------------------------------------------------
# Event time derivation (factual, not LLM-inferred)
# ---------------------------------------------------------------------------

def _parse_iso(value: str | None) -> datetime | None:
    """Parse an ISO-8601 string into an aware datetime. Returns None on failure."""
    if not value:
        return None
    s = value.strip()
    if not s:
        return None
    # Python's fromisoformat doesn't accept the trailing 'Z' until 3.11+ does;
    # normalize defensively.
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def compute_event_time(
    was_live: bool | None,
    release_timestamp: int | None,
    timestamp: int | None,
    llm_event_datetime: str | None = None,
) -> datetime | None:
    """Return the best available event-time estimate.

    Priority (highest first):
      1. `release_timestamp` when `was_live=True` — gold standard for livestream
         VODs (verified in Phase 0 spike to match the actual stream start to
         within ~2 minutes).
      2. `llm_event_datetime` — when the LLM was able to read a full date+time
         from the title / DDG snippets / transcript / description (e.g. titles
         like "May 7, 2026 15:47"). Better than upload time for non-live videos.
      3. `timestamp` (upload time) — weakest fallback. For non-live videos this
         is when the video was POSTED, not when the speech happened.
      4. None.
    """
    if was_live and release_timestamp:
        try:
            return datetime.fromtimestamp(release_timestamp, tz=timezone.utc)
        except (ValueError, OSError):
            pass
    parsed = _parse_iso(llm_event_datetime)
    if parsed is not None:
        return parsed
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

    Extracts only the fields we keep: event_type (Call B) and
    city/state/country/venue + the full event datetime (Call A), plus
    `classification_source='auto_llm'`. Diagnostics (`_errors`, `_llm_failed`,
    `_reasoning`, `_tokens_used`) are surfaced for procurement_runs but not
    persisted. Returns {} only when the API key is missing.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY not set — cannot run metadata extraction")
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

    location_task = _call_gemini(
        client, location_prompt, _location_response_schema(), label="location"
    )
    event_type_task = _call_gemini(
        client, event_type_prompt, _event_type_response_schema(), label="event_type"
    )
    (
        (location_result, location_usage, location_diag),
        (event_type_result, event_type_usage, event_type_diag),
    ) = await asyncio.gather(location_task, event_type_task)

    result: dict = {"classification_source": "auto_llm"}
    if location_result:
        for field in ("city", "state", "country", "venue"):
            val = location_result.get(field)
            if val is not None:
                result[field] = val
        # Surface the LLM-extracted full datetime separately — callers feed it
        # to compute_event_time as a fallback when release_timestamp is absent.
        if location_result.get("event_datetime_utc"):
            result["_llm_event_datetime"] = location_result["event_datetime_utc"]
        if location_result.get("reasoning"):
            result["_reasoning"] = location_result["reasoning"]

    if event_type_result and event_type_result.get("event_type"):
        result["event_type"] = event_type_result["event_type"]
    # No fallback event_type here — the caller defaults to "other".

    # Distinguish "ran but found nothing" from "the call failed", so an empty
    # row is never mistaken for a clean extraction (the original null bug).
    errors = []
    if location_diag.get("error"):
        errors.append({"call": "location", **location_diag})
    if event_type_diag.get("error"):
        errors.append({"call": "event_type", **event_type_diag})
    if errors:
        result["_errors"] = errors
    result["_llm_failed"] = bool(errors)

    # Surface cumulative token usage for observability (procurement_runs).
    result["_tokens_used"] = {
        "prompt_tokens": location_usage["prompt_tokens"] + event_type_usage["prompt_tokens"],
        "completion_tokens": location_usage["completion_tokens"] + event_type_usage["completion_tokens"],
    }
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

    crash_error: str | None = None
    try:
        extracted = await extract_metadata(
            title=title or "",
            description=description or "",
            transcript_text=transcript_text or "",
        )
    except Exception as e:
        logger.error("extract_metadata crashed for %s: %s", transcript_id, e)
        extracted = {}
        crash_error = str(e)

    event_time = compute_event_time(
        was_live=bool(was_live),
        release_timestamp=release_timestamp,
        timestamp=timestamp,
        llm_event_datetime=extracted.get("_llm_event_datetime"),
    )
    if was_live and release_timestamp:
        event_time_source = "release_timestamp"
    elif extracted.get("_llm_event_datetime"):
        event_time_source = "llm"
    elif timestamp:
        event_time_source = "upload_timestamp"
    else:
        event_time_source = "none"

    row: dict = {
        "transcript_id": transcript_id,
        "event_type": extracted.get("event_type") or "other",
        "classification_source": extracted.get("classification_source", "auto_llm"),
    }
    for key in ("city", "state", "country", "venue"):
        if extracted.get(key) is not None:
            row[key] = extracted[key]
    if event_time is not None:
        row["event_time"] = event_time.isoformat()

    # Did the LLM actually run, or did it fail? A failed extraction must NOT
    # look like a successful-but-empty one (that was the original null bug).
    llm_errors = extracted.get("_errors")
    if crash_error:
        action = "llm_failed"
    elif not extracted:
        action = "llm_failed"  # extract_metadata returned {} (e.g. no API key)
    elif extracted.get("_llm_failed"):
        action = "llm_failed"
    else:
        action = "extracted"

    status: dict = {
        "transcript_id": transcript_id,
        "event_type": row.get("event_type"),
        "city": row.get("city"),
        "venue": row.get("venue"),
        "event_time": event_time.isoformat() if event_time else None,
        "event_time_source": event_time_source,
        "reasoning": extracted.get("_reasoning"),
        "action": action,
        "tokens_used": extracted.get("_tokens_used", {"prompt_tokens": 0, "completion_tokens": 0}),
    }
    if action == "llm_failed":
        status["errors"] = llm_errors or ([{"call": "extract_metadata", "error": crash_error}]
                                          if crash_error else
                                          [{"call": "extract_metadata", "error": "no result (missing API key?)"}])
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


def _persona_transcript_pool(persona_id: str, aliases: list[str]) -> list[dict]:
    """All transcripts that have a speaker matching ANY of the persona's
    aliases (case-insensitive, exact match per alias) and have a youtube_url
    + a non-empty transcript.

    Mirrors persona_service._find_transcript_ids_by_aliases — that's the
    canonical persona→transcripts mapping used by the personas page. Earlier
    versions of this function did a substring match on the persona's primary
    name, which silently excluded transcripts whose speaker name didn't
    contain the full persona name (e.g. persona 'Donald J. Trump' vs speaker
    'TRUMP').
    """
    supabase = get_supabase()
    if not aliases:
        # Fall back to the persona's primary name from the personas table.
        persona_resp = (
            supabase.table("personas")
            .select("name")
            .eq("id", persona_id)
            .single()
            .execute()
        )
        if persona_resp.data and persona_resp.data.get("name"):
            aliases = [persona_resp.data["name"]]
        else:
            return []

    speaker_ids: set[str] = set()
    for alias in aliases:
        if not alias or not alias.strip():
            continue
        resp = (
            supabase.table("speakers")
            .select("id")
            .ilike("name", alias.strip())  # exact match, case-insensitive
            .execute()
        )
        speaker_ids.update(r["id"] for r in (resp.data or []))
    if not speaker_ids:
        return []

    transcript_ids: set[str] = set()
    speaker_id_list = list(speaker_ids)
    CHUNK = 200
    for i in range(0, len(speaker_id_list), CHUNK):
        batch = speaker_id_list[i:i + CHUNK]
        ts_resp = (
            supabase.table("transcript_speakers")
            .select("transcript_id")
            .in_("speaker_id", batch)
            .execute()
        )
        transcript_ids.update(r["transcript_id"] for r in (ts_resp.data or []))
    if not transcript_ids:
        return []

    rows: list[dict] = []
    transcript_id_list = list(transcript_ids)
    for i in range(0, len(transcript_id_list), CHUNK):
        chunk = transcript_id_list[i:i + CHUNK]
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

    # Pull all aliases for this persona so we can find every transcript where
    # they actually speak — not just rows whose speaker name contains the
    # persona's primary name.
    aliases_resp = (
        supabase.table("persona_aliases")
        .select("alias")
        .eq("persona_id", persona_id)
        .execute()
    )
    aliases = [a["alias"] for a in (aliases_resp.data or []) if a.get("alias")]
    if persona_name and persona_name not in aliases:
        aliases.append(persona_name)
    logger.info(
        "metadata backfill: persona '%s' has %d aliases: %s",
        persona_name, len(aliases), aliases[:10],
    )

    # Audit row first so failures still leave a trail.
    run_resp = get_analytical_table("procurement_runs").insert({
        "source_type": "metadata_backfill",
        "persona_id": persona_id,
        "status": "running",
    }).execute()
    run_id = run_resp.data[0]["id"]

    try:
        candidates = _persona_transcript_pool(persona_id, aliases)

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
        prompt_tokens = 0
        completion_tokens = 0

        def _flush_progress() -> None:
            try:
                get_analytical_table("procurement_runs").update({
                    "items_found": total,
                    "items_new": succeeded,
                    "items_skipped": failed,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", run_id).execute()
            except Exception as e:
                logger.warning("progress flush failed: %s", e)

        def _mark_current(index: int, name: str) -> None:
            """Lightweight per-item PATCH so the Operations dashboard sees a
            moving cursor AND acts as a heartbeat for stale-detection."""
            try:
                get_analytical_table("procurement_runs").update({
                    "current_item_index": index,
                    "current_item_name": (name or "")[:200],
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", run_id).execute()
            except Exception as e:
                logger.debug("current-item write failed: %s", e)

        def _is_cancel_requested() -> bool:
            """Poll the cancel flag. Wire-cheap (single column select)."""
            try:
                resp = (
                    get_analytical_table("procurement_runs")
                    .select("cancel_requested")
                    .eq("id", run_id)
                    .single()
                    .execute()
                )
                return bool((resp.data or {}).get("cancel_requested"))
            except Exception:
                return False

        # Parallel processing — up to BULK_CONCURRENCY transcripts in flight.
        # Single-threaded asyncio so the shared counters (succeeded, failed,
        # tokens, details) don't need locks; we only mutate them from inside
        # the task coroutines, which run cooperatively. `cancel_event` is the
        # single source of truth for cancellation.
        completed_count = 0  # succeeded + failed (drives progress flushes)
        sem = asyncio.Semaphore(BULK_CONCURRENCY)
        cancel_event = asyncio.Event()

        async def _process_one(i: int, t: dict) -> None:
            nonlocal succeeded, failed, prompt_tokens, completion_tokens, completed_count
            if cancel_event.is_set():
                return
            async with sem:
                # Re-check after acquiring slot — the cancel might've fired
                # while we were queued.
                if cancel_event.is_set():
                    return

                name = t.get("name") or "(no name)"
                logger.info("metadata backfill [%d/%d]: %s", i, total, name[:80])
                _mark_current(i, name)

                # yt-dlp with timeout — most common hang source.
                try:
                    video_info = await asyncio.wait_for(
                        get_video_info(t["youtube_url"]),
                        timeout=YTDLP_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.warning("  [%d] yt-dlp timed out after %ds — skipping", i, YTDLP_TIMEOUT)
                    failed += 1
                    completed_count += 1
                    details.append({
                        "transcript_id": t["id"],
                        "name": name,
                        "action": "ytdlp_timeout",
                    })
                    if completed_count % PROGRESS_FLUSH_EVERY == 0:
                        _flush_progress()
                    return
                except Exception as e:
                    logger.warning("  [%d] yt-dlp failed: %s", i, e)
                    failed += 1
                    completed_count += 1
                    details.append({
                        "transcript_id": t["id"],
                        "name": name,
                        "action": "ytdlp_failed",
                        "error": str(e),
                    })
                    if completed_count % PROGRESS_FLUSH_EVERY == 0:
                        _flush_progress()
                    return

                # Generous overall budget per transcript.
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
                        timeout=GEMINI_TIMEOUT * 3 + DDG_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    logger.warning("  [%d] populate_for_transcript timed out — skipping", i)
                    failed += 1
                    completed_count += 1
                    details.append({
                        "transcript_id": t["id"],
                        "name": name,
                        "action": "populate_timeout",
                    })
                    if completed_count % PROGRESS_FLUSH_EVERY == 0:
                        _flush_progress()
                    return

                status["name"] = name
                used = status.get("tokens_used") or {}
                prompt_tokens += int(used.get("prompt_tokens", 0))
                completion_tokens += int(used.get("completion_tokens", 0))
                if status.get("action") == "extracted":
                    succeeded += 1
                    logger.info("  [%d] -> %s | %s | %s | time=%s (%s)",
                                i, status.get("event_type"), status.get("city"), status.get("venue"),
                                status.get("event_time") or "—", status.get("event_time_source"))
                else:
                    failed += 1
                    logger.info("  [%d] -> %s", i, status.get("action"))
                completed_count += 1
                details.append(status)
                if completed_count % PROGRESS_FLUSH_EVERY == 0:
                    _flush_progress()

        # Kick off all tasks; the semaphore caps in-flight work to BULK_CONCURRENCY.
        tasks = [
            asyncio.create_task(_process_one(i, t))
            for i, t in enumerate(candidates, 1)
        ]
        # Background cancel watcher — polls the DB flag every 2s and flips
        # cancel_event so queued tasks bail when they acquire the semaphore.
        async def _watch_cancel() -> None:
            while not cancel_event.is_set() and any(not task.done() for task in tasks):
                if _is_cancel_requested():
                    cancel_event.set()
                    return
                await asyncio.sleep(2)
        watcher = asyncio.create_task(_watch_cancel())

        await asyncio.gather(*tasks, return_exceptions=True)
        watcher.cancel()
        try:
            await watcher
        except (asyncio.CancelledError, Exception):
            pass
        cancelled = cancel_event.is_set()

        final_status = "cancelled" if cancelled else "completed"
        get_analytical_table("procurement_runs").update({
            "status": final_status,
            "items_found": total,
            "items_new": succeeded,
            "items_skipped": failed,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "current_item_index": None,
            "current_item_name": None,
            "details": details,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()

        logger.info(
            "metadata backfill (persona=%s): status=%s succeeded=%d failed=%d",
            persona_id, final_status, succeeded, failed,
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


# ---------------------------------------------------------------------------
# Run control (cancel / reset stale / delete)
# ---------------------------------------------------------------------------

STALE_THRESHOLD_SECONDS = 120  # no heartbeat in 2 min → consider the run dead


async def reset_orphaned_runs_on_startup() -> dict:
    """Called from FastAPI lifespan on every backend boot.

    Any procurement_run still marked `status='running'` cannot possibly be live
    (no worker survives a backend restart), so flip them all to `cancelled`
    with a clear error_message. Mirrors `resume_orphaned_jobs` for the jobs
    system, but procurement runs are NOT resumable (candidate lists +
    accumulated counts/tokens are lost), so we mark + move on.
    """
    orphans = (
        get_analytical_table("procurement_runs")
        .select("id, source_type, persona_id, started_at")
        .eq("status", "running")
        .execute()
    )
    rows = orphans.data or []
    if not rows:
        return {"reset": 0}

    ids = [r["id"] for r in rows]
    (
        get_analytical_table("procurement_runs")
        .update({
            "status": "cancelled",
            "error_message": "orphaned: backend restarted before completion",
            "current_item_index": None,
            "current_item_name": None,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .in_("id", ids)
        .execute()
    )
    logger.info("startup: reset %d orphaned procurement_runs: %s", len(ids), ids)
    return {"reset": len(ids), "run_ids": ids}


async def cancel_run(run_id: str) -> dict:
    """Request cancellation of a running procurement_run.

    Sets `cancel_requested=true`. The bulk loop polls this flag at the top of
    each iteration and exits cleanly with status='cancelled'. If the run is
    already terminal this is a no-op.
    """
    # Avoid .single() — it raises on 0 rows; we want a clean 404 path.
    existing = (
        get_analytical_table("procurement_runs")
        .select("id, status")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    rows = existing.data or []
    if not rows:
        raise ValueError("procurement_run not found")
    row = rows[0]
    if row["status"] != "running":
        return {"run_id": run_id, "status": row["status"], "cancel_requested": False}

    get_analytical_table("procurement_runs").update({
        "cancel_requested": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", run_id).execute()
    logger.info("procurement_run %s: cancel requested", run_id)
    return {"run_id": run_id, "status": "running", "cancel_requested": True}


async def reset_stale_runs() -> dict:
    """Mark any `status='running'` row whose `updated_at` is older than
    STALE_THRESHOLD_SECONDS as cancelled (worker died without writing terminal
    state). Idempotent — safe to call repeatedly."""
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=STALE_THRESHOLD_SECONDS)).isoformat()
    stale = (
        get_analytical_table("procurement_runs")
        .select("id, updated_at")
        .eq("status", "running")
        .lt("updated_at", cutoff)
        .execute()
    )
    rows = stale.data or []
    if not rows:
        return {"reset": 0}

    ids = [r["id"] for r in rows]
    (
        get_analytical_table("procurement_runs")
        .update({
            "status": "cancelled",
            "error_message": "auto-reset: no heartbeat",
            "current_item_index": None,
            "current_item_name": None,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .in_("id", ids)
        .execute()
    )
    logger.info("reset %d stale procurement_runs: %s", len(ids), ids)
    return {"reset": len(ids), "run_ids": ids}


async def delete_run(run_id: str) -> bool:
    """Delete a procurement_run row. Refuses to delete a row that's still
    `status='running'` — caller must cancel + wait first."""
    existing = (
        get_analytical_table("procurement_runs")
        .select("id, status")
        .eq("id", run_id)
        .single()
        .execute()
    )
    if not existing.data:
        return False
    if existing.data["status"] == "running":
        raise ValueError("Cannot delete a running run. Cancel it first.")

    get_analytical_table("procurement_runs").delete().eq("id", run_id).execute()
    logger.info("procurement_run %s: deleted", run_id)
    return True
