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

    # Apply search filter if provided
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
        # Get first non-empty line as preview
        preview = ""
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
            "is_premium": t.get("is_premium", False),
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
    return transcript


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
