"""LLM-driven extraction of per-transcript metadata.

Single grounded-call architecture (replaced the old DDG + two-call design):
  ONE Gemini call per transcript with Google Search grounding ON
  (`google_search` tool) returns location / venue / event datetime AND a
  semantic event_type — using the title, description, transcript opening, and
  the model's own live web search. A deterministic keyword pre-classifier
  (`event_type_classifier`) provides a high-precision guardrail: when the title
  has an unambiguous keyword the event_type is fixed in Python and overrides the
  LLM (so e.g. "...Call with Service Members" can never regress to `other`).

  Verified via `backend/scripts/probe_thinking_config.py`: on
  `gemini-3-flash-preview`, `google_search` + `response_schema` combine in one
  call, and `thinking_level=MINIMAL` is the best quality/latency point.

All outputs are SUGGESTIONS — the admin-confirm UI is the source of truth.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from datetime import datetime, timezone

from google import genai
from google.genai import types

from backend.config import get_settings
from backend.core.database import get_analytical_table, get_supabase
from backend.services.event_type_classifier import (
    EVENT_TYPE_DEFINITIONS,
    EVENT_TYPES,
    classify_event_type_deterministic,
)
from backend.services.transcription_service import with_retry

logger = logging.getLogger(__name__)


GEMINI_MODEL = "gemini-3-flash-preview"
DESCRIPTION_CHARS = 1500
TRANSCRIPT_EXCERPT_CHARS = 2000

# Generation knobs (probe-confirmed on gemini-3-flash-preview):
#  - thinking_level=MINIMAL: fast (~3s) yet still reasons enough to pick good
#    search queries and synthesize grounded results. budget=0 is marginally
#    faster but fumbles genuinely-ambiguous events; LOW is slower with no gain.
#  - temperature=0 + a fixed seed: deterministic, reproducible eval runs.
_THINKING = types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL)
_SEED = 42

# Per-call wall-clock timeouts (seconds). Bounded so one hung video/API can't
# stall the whole bulk run. GEMINI_TIMEOUT dropped from 120s now that thinking
# is minimized (the 120s existed to accommodate unthrottled thinking); the
# grounded call + retries/backoff still fit comfortably.
GEMINI_TIMEOUT = 60
YTDLP_TIMEOUT = 45
# yt-dlp is the only per-item external call without retry; a single retry with
# a short backoff recovers most transient YouTube/network blips. (Gemini calls
# already retry inside `_call_gemini` via `with_retry`.)
YTDLP_ATTEMPTS = 2
YTDLP_RETRY_DELAY = 2.0
POPULATE_TIMEOUT = GEMINI_TIMEOUT + 30  # one grounded call + context-window compute + upsert
PROGRESS_FLUSH_EVERY = 5  # update procurement_runs.items_new every N transcripts
# Transcripts processed in parallel during a backfill. Grounded (google_search)
# calls share a *lower* quota than plain generation: a single 6-wide burst is
# fine, but sustained 6-wide load over a long run trips a throttle that hangs
# every call to the 60s timeout (observed: a 142-item run timing out 142/142).
# 4 keeps us comfortably under that ceiling; raise cautiously.
BULK_CONCURRENCY = 4

# Per-transcript resilience. A *transient* outcome (Gemini timeout / llm_failed,
# usually throttling) is retried with backoff rather than permanently failing
# the transcript — so a brief throttle window no longer wipes a whole run.
ITEM_MAX_ATTEMPTS = 3
ITEM_RETRY_BASE_DELAY = 4.0  # seconds; multiplied by the attempt number
TRANSIENT_ACTIONS = {"llm_failed", "populate_timeout"}

# Soft circuit-breaker: once transient failures cluster, pause *new* attempts
# briefly so we ride out a throttle instead of hammering the API with doomed
# calls. Strikes reset on any success or once a cooldown is armed.
THROTTLE_TRIP = 6
THROTTLE_COOLDOWN = 45.0  # seconds


# ---------------------------------------------------------------------------
# Combined grounded extraction prompt + schema
# ---------------------------------------------------------------------------

def _build_extraction_prompt(
    title: str,
    description: str,
    transcript_excerpt: str,
    persona_name: str,
    det_type: str | None,
    det_signal: str | None,
) -> str:
    if det_type:
        event_type_block = (
            f"A high-precision keyword classifier already determined "
            f"event_type = `{det_type}` (matched: \"{det_signal}\"). Return that "
            f"exact value as event_type unless the content flatly contradicts it.\n"
            f"  - matched_signal: \"keyword:{det_signal}\""
        )
    else:
        event_type_block = (
            "Classify the event into exactly ONE event_type using these definitions:\n"
            f"{EVENT_TYPE_DEFINITIONS}\n"
            "Choose `other` ONLY if the event genuinely fits none of the 15 specific "
            "types. A generic-sounding title is NOT grounds for `other` — use the "
            "description, transcript, and your web search to decide what actually "
            "happened (e.g. a 'Champion of Coal Event' in the East Room is a `ceremony`).\n"
            "  - matched_signal: short phrase + source that drove the event_type choice"
        )

    return f"""You extract structured metadata about a U.S. political event from a YouTube video. \
You have a Google Search tool — USE IT to find news coverage of THIS specific event and verify the details.

PERSONA: {persona_name}

VIDEO TITLE:
{title or "(empty)"}

VIDEO DESCRIPTION:
{description or "(empty)"}

TRANSCRIPT EXCERPT (first ~{TRANSCRIPT_EXCERPT_CHARS} chars):
{transcript_excerpt or "(empty)"}

Return these fields (use null when you cannot find a confident value):

LOCATION — the title/description usually give the city; news articles give the room/venue:
  - city: city name only, no state suffix (e.g. "Phoenix"); null if unknown
  - state: full US state name (e.g. "Arizona"); use "District of Columbia" for DC; null for non-US events
  - country: full country name; default "US" for US events; the actual country otherwise ("Japan", "Malaysia")
  - venue: the MOST SPECIFIC building/room named anywhere (e.g. "East Room of the White House", "Rose Garden", "Mar-a-Lago", "Madison Square Garden"). Prefer room-level detail from news articles. If your search is unhelpful, fall back to the TRANSCRIPT/DESCRIPTION — speakers and chyrons routinely state the location ("here in Phoenix", "the East Room"). Do NOT invent a venue.
  - event_datetime_utc: full event START as an ISO-8601 UTC timestamp (e.g. "2026-05-07T15:47:00Z") if determinable from the title, your search, or the transcript; null otherwise. Convert local times to UTC: White House / DC / Florida → ET, California → PT; assume ET if unsure.

EVENT TYPE:
{event_type_block}

  - event_type: one of {EVENT_TYPES}
  - event_type_confidence: number 0..1
  - primary_source: which input the LOCATION came from — one of ["title", "web", "description", "transcript", "none"]
  - reasoning: one short sentence on what you used and why any field is null
"""


def _extraction_response_schema() -> types.Schema:
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "city": types.Schema(type=types.Type.STRING, nullable=True),
            "state": types.Schema(type=types.Type.STRING, nullable=True),
            "country": types.Schema(type=types.Type.STRING, nullable=True),
            "venue": types.Schema(type=types.Type.STRING, nullable=True),
            "event_datetime_utc": types.Schema(type=types.Type.STRING, nullable=True),
            "event_type": types.Schema(type=types.Type.STRING, enum=EVENT_TYPES),
            "event_type_confidence": types.Schema(type=types.Type.NUMBER, nullable=True),
            "matched_signal": types.Schema(type=types.Type.STRING, nullable=True),
            "primary_source": types.Schema(
                type=types.Type.STRING,
                enum=["title", "web", "description", "transcript", "none"],
            ),
            "reasoning": types.Schema(type=types.Type.STRING),
        },
        required=["event_type", "primary_source", "reasoning"],
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


def _grounding_from_response(response) -> dict | None:
    """Best-effort extract Google Search grounding signals (queries it ran +
    how many web chunks it cited). Lets callers distinguish 'searched but found
    nothing' from 'never searched'."""
    try:
        gm = response.candidates[0].grounding_metadata
    except (AttributeError, IndexError, TypeError):
        return None
    if not gm:
        return None
    return {
        "queries": list(gm.web_search_queries or []),
        "chunks": len(gm.grounding_chunks or []),
    }


def _lenient_json(text: str) -> dict | None:
    """Parse a JSON object out of text, tolerating ``` fences / leading prose.
    With response_schema the text is already clean JSON; this is a safety net."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    t = re.sub(r"^```(?:json)?", "", text.strip()).strip()
    t = re.sub(r"```$", "", t).strip()
    start = t.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(t)):
        if t[i] == "{":
            depth += 1
        elif t[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(t[start : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def _extraction_config(schema: types.Schema, *, grounded: bool) -> types.GenerateContentConfig:
    """Structured-output config with thinking minimized + (optionally) the
    Google Search grounding tool. Probe-confirmed that grounding + response_schema
    + thinking_config all combine on gemini-3-flash-preview."""
    kwargs: dict = {
        "response_mime_type": "application/json",
        "response_schema": schema,
        "temperature": 0.0,
        "seed": _SEED,
        "thinking_config": _THINKING,
    }
    if grounded:
        kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
    return types.GenerateContentConfig(**kwargs)


async def _call_gemini(
    client: genai.Client,
    prompt: str,
    schema: types.Schema,
    *,
    label: str = "metadata",
    grounded: bool = False,
) -> tuple[dict | None, dict, dict]:
    """Run one structured-output Gemini call (optionally Google-Search grounded).

    Returns (parsed_json | None, usage_dict, diag_dict). `usage_dict` is always
    present (zeroed on failure). `diag_dict` is {"error", "raw", "finish_reason",
    "grounding"} and is the ONLY place a failure reason is recorded — callers
    surface it into procurement_runs.details so an empty row is never
    indistinguishable from a failed extraction.

    Mirrors the working transcription path: wrapped in `with_retry` (retries
    429/5xx/rate-limit) under a bounded timeout.
    """
    config = _extraction_config(schema, grounded=grounded)
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
        return None, dict(_ZERO_USAGE), {"error": msg, "raw": None, "finish_reason": None, "grounding": None}
    except Exception as e:
        logger.error("Gemini %s extraction failed: %s", label, e)
        return None, dict(_ZERO_USAGE), {"error": f"call failed: {e}", "raw": None, "finish_reason": None, "grounding": None}

    usage = _usage_from_response(response)
    finish = _finish_reason(response)
    grounding = _grounding_from_response(response)
    text = (response.text or "").strip()
    if not text:
        msg = f"empty response (finish_reason={finish})"
        logger.error("Gemini %s extraction returned %s", label, msg)
        return None, usage, {"error": msg, "raw": None, "finish_reason": finish, "grounding": grounding}
    parsed = _lenient_json(text)
    if parsed is None:
        logger.error("Gemini %s extraction returned non-JSON", label)
        return None, usage, {"error": "non-JSON", "raw": text[:500], "finish_reason": finish, "grounding": grounding}
    return parsed, usage, {"error": None, "raw": None, "finish_reason": finish, "grounding": grounding}


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
         from the title / web search / transcript / description (e.g. titles
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
    """Run the single grounded extraction call and return a dict ready to upsert
    into event_tags.

    One Gemini call (Google Search grounding ON) returns
    city/state/country/venue + the full event datetime + a semantic event_type.
    A deterministic keyword pre-classifier overrides event_type whenever the
    title has an unambiguous keyword (high-precision guardrail). Diagnostics
    (`_errors`, `_llm_failed`, `_reasoning`, `_grounding`, `_event_type_source`,
    `_tokens_used`) are surfaced for procurement_runs but not persisted. Returns
    {} only when the API key is missing.
    """
    settings = get_settings()
    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY not set — cannot run metadata extraction")
        return {}

    client = genai.Client(api_key=settings.gemini_api_key)

    description = (description or "")[:DESCRIPTION_CHARS]
    transcript_excerpt = (transcript_text or "")[:TRANSCRIPT_EXCERPT_CHARS]

    # Deterministic guardrail: a clear keyword fixes event_type before the LLM,
    # so e.g. "...Call with Service Members" can never regress to `other`.
    det_type, det_signal = classify_event_type_deterministic(title)

    prompt = _build_extraction_prompt(
        title, description, transcript_excerpt, persona_name, det_type, det_signal
    )
    parsed, usage, diag = await _call_gemini(
        client, prompt, _extraction_response_schema(), label="extract", grounded=True
    )

    result: dict = {"classification_source": "auto_llm"}
    llm_type = None
    if parsed:
        for field in ("city", "state", "country", "venue"):
            val = parsed.get(field)
            if val is not None:
                result[field] = val
        # Surface the LLM-extracted full datetime separately — callers feed it
        # to compute_event_time as a fallback when release_timestamp is absent.
        if parsed.get("event_datetime_utc"):
            result["_llm_event_datetime"] = parsed["event_datetime_utc"]
        if parsed.get("reasoning"):
            result["_reasoning"] = parsed["reasoning"]
        llm_type = parsed.get("event_type")

    # event_type: deterministic keyword wins; else the grounded LLM; else the
    # caller defaults to "other".
    if det_type:
        result["event_type"] = det_type
        result["_event_type_source"] = "deterministic"
        result["_matched_signal"] = det_signal
    elif llm_type:
        result["event_type"] = llm_type
        result["_event_type_source"] = "llm"
        result["_matched_signal"] = parsed.get("matched_signal")
        result["_event_type_confidence"] = parsed.get("event_type_confidence")

    # Distinguish "ran but found nothing" from "the call failed", so an empty
    # row is never mistaken for a clean extraction (the original null bug).
    if diag.get("error"):
        result["_errors"] = [{"call": "extract", **diag}]
    result["_llm_failed"] = bool(diag.get("error"))
    if diag.get("grounding"):
        result["_grounding"] = diag["grounding"]

    # Surface token usage for observability (procurement_runs).
    result["_tokens_used"] = dict(usage)
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
        "event_type_source": extracted.get("_event_type_source"),
        "city": row.get("city"),
        "state": row.get("state"),
        "venue": row.get("venue"),
        "event_time": event_time.isoformat() if event_time else None,
        "event_time_source": event_time_source,
        "reasoning": extracted.get("_reasoning"),
        "grounding": extracted.get("_grounding"),
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
    retry_of: str | None = None,
    attempt: int = 1,
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
        "params": {"force": force, "limit": limit},
        "retry_of": retry_of,
        "attempt": attempt,
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

        # Soft circuit-breaker shared across the in-flight tasks. Single-threaded
        # asyncio, so a plain dict needs no lock.
        throttle = {"strikes": 0, "cooldown_until": 0.0}

        def _note_transient() -> None:
            throttle["strikes"] += 1
            if throttle["strikes"] >= THROTTLE_TRIP:
                throttle["cooldown_until"] = time.monotonic() + THROTTLE_COOLDOWN
                throttle["strikes"] = 0
                logger.warning(
                    "metadata backfill %s: transient failures clustered — cooling down %.0fs",
                    run_id, THROTTLE_COOLDOWN,
                )

        def _note_success() -> None:
            throttle["strikes"] = 0

        async def _await_cooldown() -> None:
            wait = throttle["cooldown_until"] - time.monotonic()
            if wait > 0:
                await asyncio.sleep(min(wait, THROTTLE_COOLDOWN))

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

                # yt-dlp with timeout + a single transient retry — most common
                # hang/blip source.
                video_info = None
                ytdlp_err: tuple[str, str] | None = None  # (action, error)
                for ydl_attempt in range(YTDLP_ATTEMPTS):
                    if cancel_event.is_set():
                        return
                    try:
                        video_info = await asyncio.wait_for(
                            get_video_info(t["youtube_url"]),
                            timeout=YTDLP_TIMEOUT,
                        )
                        ytdlp_err = None
                        break
                    except asyncio.TimeoutError:
                        ytdlp_err = ("ytdlp_timeout", f"timed out after {YTDLP_TIMEOUT}s")
                        logger.warning("  [%d] yt-dlp timed out (attempt %d/%d)",
                                       i, ydl_attempt + 1, YTDLP_ATTEMPTS)
                    except Exception as e:
                        ytdlp_err = ("ytdlp_failed", str(e))
                        logger.warning("  [%d] yt-dlp failed (attempt %d/%d): %s",
                                       i, ydl_attempt + 1, YTDLP_ATTEMPTS, e)
                    if ydl_attempt < YTDLP_ATTEMPTS - 1:
                        await asyncio.sleep(YTDLP_RETRY_DELAY)

                if ytdlp_err is not None:
                    action, err = ytdlp_err
                    failed += 1
                    completed_count += 1
                    detail = {
                        "transcript_id": t["id"],
                        "name": name,
                        "action": action,
                        "attempts": YTDLP_ATTEMPTS,
                    }
                    if action == "ytdlp_failed":
                        detail["error"] = err
                    details.append(detail)
                    if completed_count % PROGRESS_FLUSH_EVERY == 0:
                        _flush_progress()
                    return

                # Extraction with bounded item-level retries. A transient outcome
                # (Gemini timeout / llm_failed — usually throttling under sustained
                # grounded load) is retried with backoff instead of permanently
                # failing the transcript, and the circuit-breaker pauses new
                # attempts when failures cluster — so a brief throttle window no
                # longer wipes the whole run.
                status: dict = {}
                attempts_made = 0
                for item_attempt in range(1, ITEM_MAX_ATTEMPTS + 1):
                    if cancel_event.is_set():
                        return
                    await _await_cooldown()
                    attempts_made = item_attempt
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
                            timeout=POPULATE_TIMEOUT,
                        )
                    except asyncio.TimeoutError:
                        status = {"transcript_id": t["id"], "action": "populate_timeout"}

                    # Every attempt is a real (billable) Gemini call — count its
                    # tokens whether it succeeded or not.
                    used = status.get("tokens_used") or {}
                    prompt_tokens += int(used.get("prompt_tokens", 0))
                    completion_tokens += int(used.get("completion_tokens", 0))

                    if status.get("action") not in TRANSIENT_ACTIONS:
                        _note_success()
                        break
                    _note_transient()
                    if item_attempt < ITEM_MAX_ATTEMPTS:
                        logger.warning("  [%d] %s (attempt %d/%d) — retrying",
                                       i, status.get("action"), item_attempt, ITEM_MAX_ATTEMPTS)
                        await asyncio.sleep(ITEM_RETRY_BASE_DELAY * item_attempt)

                status["name"] = name
                status["attempts"] = attempts_made
                if status.get("action") == "extracted":
                    succeeded += 1
                    logger.info("  [%d] -> %s | %s | %s | time=%s (%s)",
                                i, status.get("event_type"), status.get("city"), status.get("venue"),
                                status.get("event_time") or "—", status.get("event_time_source"))
                else:
                    failed += 1
                    logger.info("  [%d] -> %s after %d attempt(s)", i, status.get("action"), attempts_made)
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


async def get_run(run_id: str) -> dict | None:
    """Fetch a single procurement_run row (or None). Shared by the retry
    dispatcher and any single-run inspection."""
    resp = (
        get_analytical_table("procurement_runs")
        .select("*")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    rows = resp.data or []
    return rows[0] if rows else None


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
