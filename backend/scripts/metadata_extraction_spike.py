"""Phase 0 feasibility spike for the per-transcript metadata bundle.

Read-only. Samples 5 random transcripts, fetches fresh YouTube metadata via
yt-dlp, runs a prototype Gemini extraction prompt, and writes a findings
report to docs/metadata-spike-findings.md.

Decisions this is designed to inform (see plan
/Users/moslmn/.claude/plans/metadata-county-zesty-giraffe.md):
  * Fill rate per field (county, city, avenue, venue, event_type, audience_type)
  * Whether the YouTube upload timestamp is a usable "time of day"
  * Which input source (title vs description vs transcript) actually carries
    the location signal — user's hint: usually the title, but venue is hard
  * Whether any obviously-needed field is missing from the planned schema

Run from repo root:  python3 -m backend.scripts.metadata_extraction_spike
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

# Repo root on sys.path so `python3 backend/scripts/...` works too.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ddgs import DDGS
from google import genai
from google.genai import types

from backend.config import get_settings
from backend.core.database import get_supabase
from backend.services.yt_dlp_utils import get_yt_dlp_base_args


SAMPLE_SIZE = 10
SPEAKER_FILTER = "trump"  # transcripts must have a speaker whose name contains this (case-insensitive)
TRANSCRIPT_EXCERPT_CHARS = 2000
DESCRIPTION_CHARS = 1500
DDG_MAX_RESULTS = 10
DDG_SNIPPET_CHARS = 1800
GEMINI_MODEL = "gemini-3-flash-preview"
EVENT_TYPES = [
    "rally",
    "press_conference",
    "press_briefing",
    "interview",
    "prepared_remarks",
    "signing_ceremony",
    "bilateral_meeting",
    "cabinet_meeting",
    "reception",
    "ceremony",
    "summit",
    "roundtable",
    "announcement",
    "greeting",
    "troop_address",
    "other",
]

EVENT_TYPE_RULES = """\
- rally: campaign rally, public political gathering with supporters
- press_conference: formal Q&A with press (multi-question, often international/major topic)
- press_briefing: daily / routine press briefing (e.g. Press Secretary)
- interview: sit-down with a journalist or network
- prepared_remarks: formal speech with prepared text (SOTU, major address, commencement)
- signing_ceremony: bill / executive order / treaty / agreement signing
- bilateral_meeting: meeting with a foreign head of state
- cabinet_meeting: cabinet or interagency meeting
- reception: themed reception (Black History Month, holiday, etc.)
- ceremony: commemorative ceremony (Turkey pardoning, Medal of Honor, awards)
- summit: multi-stakeholder summit (Small Business Summit, climate summit, etc.)
- roundtable: stakeholder discussion / listening session
- announcement: formal policy / appointment / agency announcement
- greeting: meet-and-greet, photo-op, brief welcome
- troop_address: speech to military / troop visit
- other: doesn't fit any of the above
"""

AUDIENCE_TYPES = [
    "supporters",
    "general",
    "press",
    "congress",
    "foreign",
    "military",
    "cabinet",
    "invited",
    "industry",
    "mixed",
    "other",
]

AUDIENCE_TYPE_RULES = """\
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

OUTPUT_PATH = Path(__file__).resolve().parents[2] / "docs" / "metadata-spike-findings.md"


def _candidate_pool() -> list[dict]:
    """Transcripts that have a speaker matching SPEAKER_FILTER (case-insensitive),
    have a youtube_url, and a non-empty transcript body. Shuffled."""
    supabase = get_supabase()

    # 1. Find speaker IDs matching the filter
    speakers_resp = (
        supabase.table("speakers")
        .select("id, name")
        .ilike("name", f"%{SPEAKER_FILTER}%")
        .execute()
    )
    speaker_ids = [s["id"] for s in (speakers_resp.data or [])]
    if not speaker_ids:
        return []
    print(f"  matched {len(speaker_ids)} speakers via filter '{SPEAKER_FILTER}'")

    # 2. Find transcript IDs that include any of these speakers
    ts_resp = (
        supabase.table("transcript_speakers")
        .select("transcript_id")
        .in_("speaker_id", speaker_ids)
        .execute()
    )
    transcript_ids = list({r["transcript_id"] for r in (ts_resp.data or [])})
    if not transcript_ids:
        return []
    print(f"  matched {len(transcript_ids)} transcripts containing those speakers")

    # 3. Fetch the transcript rows (chunk because PostgREST has IN-clause limits)
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
    print(f"  {len(rows)} transcripts with URL + body in pool")
    random.shuffle(rows)
    return rows


async def _fetch_video_info(url: str) -> dict:
    """Call yt-dlp --dump-json for the given video URL.

    Returns the raw info dict (or {"_error": ...} on failure). We mirror
    youtube_service.get_video_info but keep the full dict so we can inspect
    `timestamp`, `description`, `tags`, `channel`, etc.
    """
    args = get_yt_dlp_base_args()
    args.extend(["--dump-json", "--no-download", "--no-playlist", url])

    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        return {"_error": (stderr.decode() or "yt-dlp failed").strip()}
    try:
        return json.loads(stdout.decode())
    except json.JSONDecodeError as e:
        return {"_error": f"yt-dlp JSON parse failed: {e}"}


def _build_prompt(
    title: str, description: str, transcript_excerpt: str, web_snippets: str
) -> str:
    """Prompt geared to the user's hints: location is usually in the title,
    venue is hard, and live-search snippets often unlock venue/avenue."""
    return f"""You are extracting event metadata from a YouTube video about a US political speech or appearance.

Use these inputs. PRIORITY DIFFERS BY FIELD:

  - For `city` / `state` / `country`: VIDEO TITLE is the primary signal, then VIDEO DESCRIPTION, then WEB SEARCH SNIPPETS, then TRANSCRIPT EXCERPT.
  - For `venue`: WEB SEARCH SNIPPETS are the PRIMARY signal — room-level detail (East Room, Rose Garden, Oval Office, Brady Press Briefing Room, etc.) almost always comes from news articles, not the title or description. Fall back to TRANSCRIPT EXCERPT and VIDEO DESCRIPTION only if web snippets don't name the venue. Do NOT guess a venue from the title alone.
  - For `audience_type`: use ALL inputs holistically.
  - (event_type is classified separately from the title only — not part of this call.)

Return ONLY these fields. Use null if you cannot find a confident value.

  - city: city name only, no state suffix (e.g. "Phoenix")
  - state: US state name (full name, e.g. "Arizona"); for DC use "District of Columbia"
  - county: US county name if you can infer it from the city (e.g. Phoenix -> "Maricopa"); null otherwise
  - venue: building / facility name if mentioned (e.g. "The White House", "Mar-a-Lago", "Madison Square Garden"). Be as specific as the inputs allow. If the inputs name a specific room or sub-location (e.g. "East Room of the White House", "Rose Garden", "Briefing Room"), include it here — prefer the most specific form actually stated. Street address may be appended in parentheses if explicitly stated.
  - audience_type: pick from:
{AUDIENCE_TYPE_RULES}
  - event_time_local: best guess of the event's start time in HH:MM (24-hour) local time, if any input states it (e.g. titles like "3 PM ET" or descriptions saying "spoke at 14:30"). null if not stated.
  - confidence: number 0..1 — your confidence in the overall extraction
  - primary_source: which input the location came from — one of ["title", "web", "description", "transcript", "none"]
  - reasoning: one short sentence explaining what you used

VIDEO TITLE:
{title or "(empty)"}

WEB SEARCH SNIPPETS (DuckDuckGo, query roughly "Trump {{title}}"):
{web_snippets or "(empty)"}

VIDEO DESCRIPTION:
{description or "(empty)"}

TRANSCRIPT EXCERPT (first ~{TRANSCRIPT_EXCERPT_CHARS} chars):
{transcript_excerpt or "(empty)"}
""".strip()


def _response_schema() -> types.Schema:
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "city": types.Schema(type=types.Type.STRING, nullable=True),
            "state": types.Schema(type=types.Type.STRING, nullable=True),
            "county": types.Schema(type=types.Type.STRING, nullable=True),
            "venue": types.Schema(type=types.Type.STRING, nullable=True),
            "audience_type": types.Schema(type=types.Type.STRING, enum=AUDIENCE_TYPES, nullable=True),
            "event_time_local": types.Schema(type=types.Type.STRING, nullable=True),
            "confidence": types.Schema(type=types.Type.NUMBER),
            "primary_source": types.Schema(
                type=types.Type.STRING,
                enum=["title", "web", "description", "transcript", "none"],
            ),
            "reasoning": types.Schema(type=types.Type.STRING),
        },
        required=["confidence", "primary_source", "reasoning"],
    )


def _build_event_type_prompt(title: str) -> str:
    """Title-only classifier prompt with strict keyword→type mapping rules.

    Per user direction: event_type is derived from the title alone. WH-channel
    titles are formulaic enough that this is more reliable than letting the
    model wander into the description / web snippets / transcript.
    """
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
13. If the title contains "Troop" / "Troops" / "Address to the Military" -> troop_address
14. If the title contains any of: "Halloween", "Easter", "Christmas", "Thanksgiving", "Turkey Pardoning", "Mother's Day", "Father's Day", "Veterans Day", "Memorial Day", "Independence Day", "Medal of Honor", "Medal Presentation", "Honors", "State Dinner", "Hanukkah", "Tree Lighting", "Awards", "Swearing-In", "Ball", "Gala", "Inauguration" -> ceremony
15. If the title contains "Delivers Remarks" / "Remarks at" / "Remarks on" / "Address to" / "Speech" -> prepared_remarks
16. Otherwise -> other

Allowed event_types: {EVENT_TYPES}

Return JSON with:
  - event_type: one of the allowed values
  - matched_rule: the rule number that fired (1-16), or null if none applied
  - reasoning: brief, one sentence

VIDEO TITLE:
{title or "(empty)"}
"""


def _event_type_response_schema() -> types.Schema:
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "event_type": types.Schema(type=types.Type.STRING, enum=EVENT_TYPES),
            "matched_rule": types.Schema(type=types.Type.INTEGER, nullable=True),
            "reasoning": types.Schema(type=types.Type.STRING),
        },
        required=["event_type", "reasoning"],
    )


async def _classify_event_type(client: genai.Client, title: str) -> dict:
    """Dedicated title-only event_type classification via Gemini."""
    prompt = _build_event_type_prompt(title)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_event_type_response_schema(),
    )
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[types.Part.from_text(text=prompt)],
                config=config,
            ),
        )
    except Exception as e:
        return {"_error": f"event_type call failed: {e}"}
    text = (response.text or "").strip()
    if not text:
        return {"_error": "event_type empty response"}
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        return {"_error": f"event_type JSON parse failed: {e}", "_raw": text}


def _ddg_search(query: str) -> tuple[str, list[dict]]:
    """Run a DuckDuckGo text search and return (combined_snippet_text, raw_results).

    Mirrors the existing analytical_event_tag_service approach but keeps the
    raw results so the report can show what the model actually saw.
    """
    try:
        results = list(DDGS().text(query, max_results=DDG_MAX_RESULTS))
    except Exception as e:
        return (f"(DDG search failed: {e})", [])

    snippets: list[str] = []
    for r in results:
        title = (r.get("title") or "").strip()
        body = (r.get("body") or "").strip()
        if title or body:
            snippets.append(f"- {title} — {body}")
    combined = "\n".join(snippets)[:DDG_SNIPPET_CHARS]
    return combined, results


async def _extract_with_gemini(
    client: genai.Client,
    title: str,
    description: str,
    transcript_excerpt: str,
    web_snippets: str,
) -> dict:
    prompt = _build_prompt(title, description, transcript_excerpt, web_snippets)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=_response_schema(),
    )
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[types.Part.from_text(text=prompt)],
                config=config,
            ),
        )
    except Exception as e:  # network/API/etc — surface, don't crash
        return {"_error": f"gemini call failed: {e}"}

    text = (response.text or "").strip()
    if not text:
        return {"_error": "gemini returned empty response"}
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        return {"_error": f"gemini JSON parse failed: {e}", "_raw": text}


def _format_timestamp(epoch: int | None) -> str:
    if not epoch:
        return "(none)"
    try:
        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
        return f"{dt.isoformat()} (UTC) — HH:MM = {dt.strftime('%H:%M')}"
    except (ValueError, OSError) as e:
        return f"(invalid timestamp {epoch!r}: {e})"


def _event_time_source(info: dict) -> tuple[str, int | None]:
    """Choose the best yt-dlp signal for actual event time.

    For livestreams (was_live=True), release_timestamp is when the stream
    actually went live → that's the event start. Otherwise fall back to the
    upload timestamp.
    """
    if info.get("was_live") and info.get("release_timestamp"):
        return ("release_timestamp", info.get("release_timestamp"))
    if info.get("timestamp"):
        return ("timestamp (upload)", info.get("timestamp"))
    return ("none", None)


def _render_report(per_transcript: list[dict]) -> str:
    """Write a markdown report aggregating per-transcript results."""
    now = datetime.now(timezone.utc).isoformat()
    lines: list[str] = [
        "# Metadata Extraction Spike — Findings",
        "",
        f"_Generated {now} from `backend/scripts/metadata_extraction_spike.py`._",
        "",
        "## Per-transcript results",
        "",
    ]

    fill_counts: dict[str, int] = {
        k: 0 for k in ["city", "state", "county", "venue", "event_time_local"]
    }
    source_counts: dict[str, int] = {}
    has_timestamp = 0
    has_release_timestamp = 0
    livestream_count = 0
    extraction_errors = 0
    channel_counts: dict[str, int] = {}

    for i, row in enumerate(per_transcript, 1):
        name = row["transcript"].get("name") or "(no name)"
        url = row["transcript"].get("youtube_url")
        upload_date = row["transcript"].get("upload_date")
        info = row["video_info"]
        extraction = row["extraction"]

        lines.append(f"### {i}. {name}")
        lines.append("")
        lines.append(f"- **URL:** {url}")
        lines.append(f"- **DB upload_date:** `{upload_date}`")
        if "_error" in info:
            lines.append(f"- **yt-dlp:** ERROR — {info['_error']}")
        else:
            channel = info.get("channel") or info.get("uploader") or "(none)"
            lines.append(f"- **yt-dlp title:** {info.get('title') or '(none)'}")
            lines.append(f"- **yt-dlp channel:** {channel}")
            lines.append(f"- **yt-dlp upload_date:** {info.get('upload_date') or '(none)'}")
            lines.append(f"- **live_status:** {info.get('live_status')!r}, **was_live:** {info.get('was_live')!r}")
            lines.append(f"- **timestamp (upload):** {_format_timestamp(info.get('timestamp'))}")
            lines.append(f"- **release_timestamp (stream start):** {_format_timestamp(info.get('release_timestamp'))}")
            chosen_label, chosen_epoch = _event_time_source(info)
            lines.append(f"- **best event-time source:** `{chosen_label}` → {_format_timestamp(chosen_epoch)}")
            description = (info.get('description') or '').strip()
            desc_preview = description[:240].replace("\n", " ")
            lines.append(f"- **Description length:** {len(description)} chars")
            if desc_preview:
                lines.append(f"  > {desc_preview}{'…' if len(description) > 240 else ''}")
            if info.get('timestamp'):
                has_timestamp += 1
            if info.get('release_timestamp'):
                has_release_timestamp += 1
            if info.get('was_live'):
                livestream_count += 1
            channel_counts[channel] = channel_counts.get(channel, 0) + 1

        lines.append(f"- **DDG snippets:** {row.get('ddg_result_count', 0)} results")
        ddg = row.get("ddg_snippets") or ""
        if ddg:
            preview = ddg[:600].replace("\n", " ")
            lines.append(f"  > {preview}{'…' if len(ddg) > 600 else ''}")

        lines.append("")
        lines.append("**LLM extraction:**")
        lines.append("")
        if "_error" in extraction:
            lines.append(f"- ERROR: {extraction['_error']}")
            if "_raw" in extraction:
                lines.append(f"  raw: `{extraction['_raw'][:200]}`")
            extraction_errors += 1
        else:
            for field in ("city", "state", "county", "venue"):
                val = extraction.get(field)
                lines.append(f"- {field}: `{val}`")
                if val:
                    fill_counts[field] += 1
            et = extraction.get("event_type")
            rule = extraction.get("event_type_matched_rule")
            et_reasoning = extraction.get("event_type_reasoning")
            lines.append(f"- event_type (title-only): `{et}` (rule #{rule}) — {et_reasoning}")
            lines.append(f"- audience_type: `{extraction.get('audience_type')}`")
            etl = extraction.get("event_time_local")
            lines.append(f"- event_time_local (LLM): `{etl}`")
            if etl:
                fill_counts["event_time_local"] += 1
            lines.append(f"- confidence: `{extraction.get('confidence')}`")
            source = extraction.get("primary_source")
            lines.append(f"- primary_source: `{source}`")
            if source:
                source_counts[source] = source_counts.get(source, 0) + 1
            lines.append(f"- reasoning: {extraction.get('reasoning')}")
        lines.append("")

    n = len(per_transcript)
    lines.extend([
        "## Summary",
        "",
        f"- Sample size: {n}",
        f"- Extraction errors: {extraction_errors}",
        f"- Videos that were livestreams (`was_live=True`): {livestream_count}/{n}",
        f"- Videos with `timestamp` (upload time): {has_timestamp}/{n}",
        f"- Videos with `release_timestamp` (stream-start time): {has_release_timestamp}/{n}",
        "",
        "### Fill rate per field",
        "",
    ])
    for field, count in fill_counts.items():
        lines.append(f"- **{field}**: {count}/{n}")
    lines.append("")
    if source_counts:
        lines.append("### Where the location signal came from")
        lines.append("")
        for src, count in sorted(source_counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {src}: {count}")
        lines.append("")
    if channel_counts:
        lines.append("### Channel distribution")
        lines.append("")
        for ch, count in sorted(channel_counts.items(), key=lambda kv: -kv[1]):
            lines.append(f"- {ch}: {count}")
        lines.append("")

    lines.extend([
        "## Things to review with the user",
        "",
        "- Is the per-field fill rate (especially venue room-level granularity) acceptable?",
        "- For livestream VODs, does `release_timestamp` (stream start) line up with the actual event time better than upload `timestamp`?",
        "- Anything obviously missing from the extracted fields?",
        "",
    ])
    return "\n".join(lines)


async def main() -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        print("ERROR: GEMINI_API_KEY is not set in .env", file=sys.stderr)
        sys.exit(1)

    client = genai.Client(api_key=settings.gemini_api_key)

    print(f"Building pool of Trump-speaker transcripts (filter '{SPEAKER_FILTER}')...")
    pool = _candidate_pool()
    if not pool:
        print("No transcripts available — aborting.")
        return

    print(f"Drawing {SAMPLE_SIZE} samples...\n")

    per_transcript: list[dict] = []
    pool_idx = 0

    while len(per_transcript) < SAMPLE_SIZE and pool_idx < len(pool):
        t = pool[pool_idx]
        pool_idx += 1
        name = t.get("name") or "(no name)"
        i = len(per_transcript) + 1
        print(f"[{i}/{SAMPLE_SIZE}] {name}")
        print(f"  url: {t.get('youtube_url')}")

        print("  fetching yt-dlp info...")
        video_info = await _fetch_video_info(t["youtube_url"])
        if "_error" in video_info:
            print(f"    yt-dlp FAILED: {video_info['_error']} — discarding from sample")
            print()
            continue

        title = video_info.get("title") or t.get("name") or ""
        description = (video_info.get("description") or "")[:DESCRIPTION_CHARS]
        transcript_excerpt = (t.get("transcript") or "")[:TRANSCRIPT_EXCERPT_CHARS]

        ddg_query = f"Trump {title}".strip()
        print(f"  DDG search: {ddg_query[:80]}...")
        ddg_snippets, ddg_results = _ddg_search(ddg_query)

        print("  calling Gemini for location/audience/time...")
        extraction = await _extract_with_gemini(
            client, title, description, transcript_excerpt, ddg_snippets
        )
        if "_error" in extraction:
            print(f"    Gemini FAILED: {extraction['_error']}")
        else:
            summary = {k: extraction.get(k) for k in ("city", "state", "venue", "audience_type", "event_time_local", "primary_source", "confidence")}
            print(f"    -> {summary}")

        print("  calling Gemini for event_type (title-only)...")
        event_type_result = await _classify_event_type(client, title)
        if "_error" in event_type_result:
            print(f"    event_type FAILED: {event_type_result['_error']}")
            if "_error" not in extraction:
                extraction["event_type"] = None
                extraction["event_type_matched_rule"] = None
                extraction["event_type_reasoning"] = event_type_result["_error"]
        else:
            et = event_type_result.get("event_type")
            rule = event_type_result.get("matched_rule")
            print(f"    -> event_type={et} (rule #{rule})")
            if "_error" not in extraction:
                extraction["event_type"] = et
                extraction["event_type_matched_rule"] = rule
                extraction["event_type_reasoning"] = event_type_result.get("reasoning")

        per_transcript.append({
            "transcript": t,
            "video_info": video_info,
            "ddg_snippets": ddg_snippets,
            "ddg_result_count": len(ddg_results),
            "extraction": extraction,
        })
        print()

    if len(per_transcript) < SAMPLE_SIZE:
        print(f"WARNING: only filled {len(per_transcript)}/{SAMPLE_SIZE} slots from pool of {len(pool)}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(_render_report(per_transcript), encoding="utf-8")
    print(f"Wrote report to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
