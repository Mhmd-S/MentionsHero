"""Event context tagging service for transcript classification."""

import logging
from datetime import datetime, timezone

from ddgs import DDGS

from backend.core.database import get_analytical_table, get_supabase

logger = logging.getLogger(__name__)


def _tbl(name: str):
    return get_analytical_table(name)


# Event type detection keywords used when searching DDG results.
# Fallback classifier — primary classification now runs via
# metadata_extraction_service. Taxonomy mirrors the expanded event_type enum.
_EVENT_TYPE_KEYWORDS: dict[str, list[str]] = {
    "rally": ["rally", "campaign event", "campaign rally", "maga rally", "supporters gathered"],
    "press_briefing": [
        "press briefing", "briefs members of the media", "briefs the media",
        "briefing room", "podium", "white house briefing", "press secretary",
    ],
    "press_conference": [
        "press conference", "news conference", "joint press conference", "gaggle",
    ],
    "interview": [
        "interview", "sat down with", "spoke with", "told fox",
        "told cnn", "told msnbc", "told newsmax", "exclusive",
    ],
    "signing_ceremony": [
        "signing ceremony", "bill signing", "signed into law", "signs ",
        "executive order signing",
    ],
    "bilateral_meeting": [
        "bilateral meeting", "bilateral", "meeting with the president",
        "meeting with the prime minister", "meeting with the king",
        "meeting with the chancellor", "meeting with the crown prince",
        "meeting with the secretary general",
    ],
    "cabinet_meeting": ["cabinet meeting"],
    "reception": ["reception"],
    "summit": ["summit"],
    "roundtable": ["roundtable", "task force", "listening session"],
    "announcement": ["announcement", "announces", "makes an announcement"],
    "greeting": ["greeting", "welcomes", "photo op"],
    "troop_address": ["troop visit", "address to the military", "service members"],
    "ceremony": [
        "swearing-in", "swearing in", "medal of honor", "medal presentation",
        "state dinner", "tree lighting", "turkey pardoning",
        "thanksgiving", "halloween", "christmas", "easter",
        "mother's day", "father's day", "veterans day", "memorial day",
        "independence day", "honors", "ball ", "gala", "awards",
    ],
    "prepared_remarks": [
        "state of the union", "address to", "remarks at", "inaugural",
        "teleprompter", "prepared statement", "oval office address",
        "joint session", "commencement",
    ],
}

# Known networks for interview detection
_NETWORKS = [
    "Fox News", "Fox Business", "CNN", "MSNBC", "NBC", "ABC", "CBS",
    "Newsmax", "OAN", "OANN", "BBC", "Reuters", "AP",
]


async def auto_tag_transcript(transcript_id: str) -> dict | None:
    """Use DuckDuckGo to search for context about a transcript and classify it.

    Searches by the transcript's name/title to determine event type.
    """
    # Check if already tagged
    existing = (
        _tbl("event_tags")
        .select("id")
        .eq("transcript_id", transcript_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        return None  # Already tagged

    # Get transcript info from public schema
    supabase = get_supabase()
    transcript = (
        supabase.table("transcripts")
        .select("id, name, youtube_url")
        .eq("id", transcript_id)
        .single()
        .execute()
    )
    if not transcript.data:
        return None

    name = transcript.data.get("name", "")
    if not name:
        return None

    try:
        ddgs = DDGS()
        results = list(ddgs.text(f"Trump {name}", max_results=10))

        # Combine all result snippets for analysis
        combined_text = " ".join(
            f"{r.get('title', '')} {r.get('body', '')}"
            for r in results
        ).lower()

        # Classify event type from search results
        event_type = _classify_event_type(combined_text)

        # Try to extract network/interviewer
        network = _extract_network(combined_text)

        tag_data = {
            "transcript_id": transcript_id,
            "event_type": event_type,
            "classification_source": "auto_ddgs",
            "confidence": 0.7 if event_type != "other" else 0.3,
            "network": network,
        }

        response = _tbl("event_tags").insert(tag_data).execute()
        return response.data[0] if response.data else None

    except Exception as e:
        logger.error("Auto-tag failed for transcript %s: %s", transcript_id, e)
        return None


async def bulk_auto_tag(persona_id: str) -> dict:
    """Run auto-tagger on all untagged transcripts for a persona.

    Finds transcripts linked to persona via speaker aliases, then
    classifies each untagged one.
    """
    # Create procurement run for audit
    run_resp = _tbl("procurement_runs").insert({
        "source_type": "event_tag_auto",
        "persona_id": persona_id,
        "status": "running",
    }).execute()
    run_id = run_resp.data[0]["id"]

    try:
        supabase = get_supabase()

        # Get persona info
        persona_resp = (
            supabase.table("personas")
            .select("id, name")
            .eq("id", persona_id)
            .single()
            .execute()
        )
        if not persona_resp.data:
            raise ValueError("Persona not found")

        # Find all transcripts
        all_transcripts = (
            supabase.table("transcripts")
            .select("id, name, youtube_url")
            .order("created_at", desc=True)
            .execute()
        )

        # Get already-tagged transcript IDs
        tagged_resp = (
            _tbl("event_tags")
            .select("transcript_id")
            .execute()
        )
        tagged_ids = {t["transcript_id"] for t in (tagged_resp.data or [])}

        # Filter to untagged transcripts with names
        untagged = [
            t for t in (all_transcripts.data or [])
            if t["id"] not in tagged_ids and t.get("name")
        ]

        tagged = 0
        skipped = 0
        failed = 0
        details: list[dict] = []

        for transcript in untagged:
            try:
                result = await auto_tag_transcript(transcript["id"])
                if result:
                    tagged += 1
                    details.append({
                        "transcript_id": transcript["id"],
                        "name": transcript.get("name"),
                        "event_type": result.get("event_type"),
                        "action": "tagged",
                    })
                else:
                    skipped += 1
            except Exception as e:
                failed += 1
                details.append({
                    "transcript_id": transcript["id"],
                    "action": "error",
                    "error": str(e),
                })

        _tbl("procurement_runs").update({
            "status": "completed",
            "items_found": len(untagged),
            "items_new": tagged,
            "items_skipped": skipped,
            "details": details,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()

        logger.info("Bulk auto-tag: tagged=%d, skipped=%d, failed=%d", tagged, skipped, failed)

        return {
            "run_id": run_id,
            "tagged": tagged,
            "skipped": skipped,
            "failed": failed,
        }

    except Exception as e:
        logger.error("Bulk auto-tag failed: %s", e, exc_info=True)
        _tbl("procurement_runs").update({
            "status": "failed",
            "error_message": str(e),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
        return {"run_id": run_id, "tagged": 0, "skipped": 0, "failed": 0}


# ---------------------------------------------------------------------------
# Manual CRUD
# ---------------------------------------------------------------------------

async def tag_transcript(data: dict) -> dict:
    """Manually tag a transcript with event context."""
    from postgrest.exceptions import APIError
    try:
        response = _tbl("event_tags").upsert(
            data, on_conflict="transcript_id"
        ).execute()
    except APIError as e:
        if "23503" in str(e):
            raise ValueError("Transcript not found")
        raise
    return response.data[0]


async def get_tag(transcript_id: str) -> dict | None:
    """Get event tag for a transcript."""
    response = (
        _tbl("event_tags")
        .select("*")
        .eq("transcript_id", transcript_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


async def update_tag(transcript_id: str, data: dict) -> dict | None:
    """Update an event tag."""
    update_data = {k: v for k, v in data.items() if v is not None}
    if not update_data:
        return await get_tag(transcript_id)

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["classification_source"] = "manual"

    response = (
        _tbl("event_tags")
        .update(update_data)
        .eq("transcript_id", transcript_id)
        .execute()
    )
    return response.data[0] if response.data else None


async def delete_tag(transcript_id: str) -> bool:
    """Delete an event tag."""
    response = (
        _tbl("event_tags")
        .delete()
        .eq("transcript_id", transcript_id)
        .execute()
    )
    return bool(response.data)


async def get_tags_by_event_type(
    event_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Get event tags, optionally filtered by type."""
    query = _tbl("event_tags").select("*")
    if event_type:
        query = query.eq("event_type", event_type)
    response = query.order("created_at", desc=True).limit(limit).execute()
    return response.data or []


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

def _classify_event_type(text: str) -> str:
    """Classify event type from combined DDG search result text."""
    scores: dict[str, int] = {}
    for event_type, keywords in _EVENT_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[event_type] = score

    if not scores:
        return "other"

    return max(scores, key=scores.get)


def _extract_network(text: str) -> str | None:
    """Try to extract a network name from search results."""
    text_lower = text.lower()
    for network in _NETWORKS:
        if network.lower() in text_lower:
            return network
    return None
