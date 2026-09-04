"""Public-facing service.

Everything here is anonymous and free. There is no subscription check and no
premium tier: if a transcript is `is_public`, it is served in full to whoever
asks. `is_premium` still exists as a column but the public API ignores it.
"""

import math
from typing import Any

from backend.core.database import get_supabase, get_folder_ids_in_tree
from backend.utils.nlp import parse_transcript_segments


async def get_public_personas() -> list[dict[str, Any]]:
    """Personas that actually have public transcripts, with their counts.

    A persona with nothing to read is not listed. Most of the 55 rows in
    `personas` are aspirational — seeded ahead of any transcription — and listing
    them sent visitors to a page whose only content was "no transcripts yet".
    The sitemap is built from this same function, so empty personas stop being
    submitted to search engines too.

    Counted in one pass rather than per persona: resolving 55 personas through
    aliases → speakers → links individually is ~165 round trips.
    """
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
    aliases_by_persona: dict[str, list[str]] = {}
    for alias in _select_all("persona_aliases", "persona_id, alias"):
        pid = alias["persona_id"]
        aliases_by_persona.setdefault(pid, []).append(alias["alias"])

    # speaker name (lowercased) -> speaker id. Alias matching is case-insensitive
    # equality, the same rule `_find_transcript_ids_by_aliases` applies.
    speaker_ids_by_name: dict[str, list[str]] = {}
    for row in _select_all("speakers", "id, name"):
        speaker_ids_by_name.setdefault((row["name"] or "").lower(), []).append(row["id"])

    # speaker id -> the transcripts they speak in
    transcripts_by_speaker: dict[str, set[str]] = {}
    for row in _select_all("transcript_speakers", "speaker_id, transcript_id"):
        transcripts_by_speaker.setdefault(row["speaker_id"], set()).add(row["transcript_id"])

    public_ids = {
        row["id"]
        for row in _select_all(
            "transcripts", "id", lambda q: q.eq("is_public", True)
        )
    }

    listed: list[dict[str, Any]] = []
    for persona in personas:
        aliases = aliases_by_persona.get(persona["id"], [])
        persona["aliases"] = aliases

        transcript_ids: set[str] = set()
        for alias in aliases:
            for speaker_id in speaker_ids_by_name.get(alias.lower(), []):
                transcript_ids |= transcripts_by_speaker.get(speaker_id, set())

        count = len(transcript_ids & public_ids)
        if not count:
            continue

        persona["transcript_count"] = count
        listed.append(persona)

    return listed


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


#: PostgREST caps an unbounded select at 1000 rows and reports no error — the
#: response simply stops. Anything that must read a whole table goes through
#: `_select_all`, or it will silently lose data the moment the archive outgrows
#: the cap. This is not hypothetical: an unpaged read of `transcript_speakers`
#: (1073 rows) returned 1000 and made 12 perfectly good transcripts look broken.
_PAGE = 1000


def _select_all(table: str, columns: str, apply_filters=None) -> list[dict[str, Any]]:
    """Read every row of a query, paging past the PostgREST row cap."""
    supabase = get_supabase()
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = supabase.table(table).select(columns)
        if apply_filters is not None:
            query = apply_filters(query)
        page = query.range(offset, offset + _PAGE - 1).execute().data or []
        rows.extend(page)
        if len(page) < _PAGE:
            return rows
        offset += _PAGE


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
        rows = _select_all(
            "transcript_speakers",
            "transcript_id",
            lambda q, b=batch: q.in_("speaker_id", b),
        )
        transcript_ids.update(r["transcript_id"] for r in rows)

    return transcript_ids


async def get_public_transcripts_for_persona(
    aliases: list[str],
    folder_id: str | None = None,
    search: str | None = None,
    sort_by: str = "date",
    sort_order: str = "desc",
    page: int = 1,
    page_size: int = 20,
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
    tree_ids = None
    if folder_id:
        folders_response = supabase.table("folders").select("*").execute()
        folders = folders_response.data or []
        tree_ids = get_folder_ids_in_tree(folder_id, folders)

    def _filters(query):
        query = query.eq("is_public", True).in_("id", list(matching_ids))
        if tree_ids is not None:
            query = query.in_("folder_id", tree_ids)
        # Sort by upload_date (YouTube date) when sorting by date, fall back to created_at
        if sort_by == "date":
            return query.order("upload_date", desc=(sort_order == "desc"), nullsfirst=False)
        return query.order("name", desc=(sort_order == "desc"))

    # Paged: this is the listing query, so truncation here would quietly hide
    # transcripts from a persona once the archive passes the row cap.
    all_transcripts = _select_all(
        "transcripts",
        "id, name, created_at, upload_date, folder_id, transcript",
        _filters,
    )

    if search:
        search_lower = search.lower()
        all_transcripts = [
            t for t in all_transcripts
            if search_lower in (t.get("transcript") or "").lower()
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
        transcript_text = t.get("transcript", "")

        # First line of what was actually said. Taking the literal first line
        # gave every card the same useless "[00:01] Donald Trump:" — the speaker
        # label — because that is how the transcripts are formatted.
        preview = ""
        for segment in parse_transcript_segments(transcript_text):
            content = (segment.get("content") or "").strip()
            if content:
                preview = content[:200]
                break
        if not preview:
            # No speaker labels matched; fall back to the first non-empty line.
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
) -> dict[str, Any]:
    """Search for a keyword across all of a persona's public transcripts.

    Every match is returned, to everyone.
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
        }

    id_list = list(matching_ids)
    batch_size = 200
    all_transcripts: list[dict[str, Any]] = []
    for i in range(0, len(id_list), batch_size):
        batch = id_list[i:i + batch_size]
        resp = (
            supabase.table("transcripts")
            .select("id, name, upload_date, transcript")
            .eq("is_public", True)
            .in_("id", batch)
            .execute()
        )
        all_transcripts.extend(resp.data or [])

    if not all_transcripts:
        return {
            "query": query,
            "total_matches": 0,
            "transcripts_with_matches": 0,
            "matches": [],
        }

    result = search_term_in_context(all_transcripts, query, context_chars=150)

    return {
        "query": query,
        "total_matches": result["total_matches"],
        "transcripts_with_matches": result["transcripts_with_matches"],
        "matches": result["matches"],
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
    matching_persona_ids = set()
    for alias_row in _select_all("persona_aliases", "persona_id, alias"):
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


async def get_public_transcript(transcript_id: str) -> dict[str, Any] | None:
    """Get a public transcript in full, or None if it should not be shown.

    `is_public` is necessary but not sufficient. A transcript with no rows in
    `transcript_speakers` is already absent from every persona listing and every
    keyword search, because both reach transcripts *through* speakers. Serving it
    at /transcripts/{id} anyway produced an orphan: reachable only by guessing the
    URL, with no breadcrumb persona, no speaker attribution and no prev/next.
    No speaker links, no page.
    """
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

    links = (
        supabase.table("transcript_speakers")
        .select("transcript_id")
        .eq("transcript_id", transcript_id)
        .limit(1)
        .execute()
    )
    if not links.data:
        return None

    # Attach persona info for navigation breadcrumbs. Absent when the speakers are
    # all unattributed ("Reporter", "Announcer"); the page still reads fine.
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
