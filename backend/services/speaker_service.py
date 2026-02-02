"""Speaker service for database operations and extraction."""

from collections import Counter
from typing import Any

from backend.core.database import get_supabase
from backend.services import transcript_service
from backend.utils.nlp import parse_transcript_segments


async def get_or_create_speaker(name: str) -> dict[str, Any]:
    """Get speaker by name, or create if not exists. Returns speaker row with id."""
    supabase = get_supabase()
    name = name.strip()
    if not name:
        raise ValueError("Speaker name cannot be empty")

    # Try to get existing
    response = (
        supabase.table("speakers")
        .select("id, name, created_at")
        .eq("name", name)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    if rows:
        return rows[0]

    # Insert new (execute() returns inserted row with default representation)
    insert_response = supabase.table("speakers").insert({"name": name}).execute()
    if insert_response.data and len(insert_response.data) > 0:
        return insert_response.data[0]
    # Fallback: fetch by name if client did not return data
    response = (
        supabase.table("speakers")
        .select("id, name, created_at")
        .eq("name", name)
        .limit(1)
        .execute()
    )
    return (response.data or [])[0]


async def extract_and_save_transcript_speakers(
    transcript_id: str,
    transcript_text: str
) -> list[dict[str, Any]]:
    """
    Parse transcript text, create/link speakers, and save transcript_speakers.
    Replaces any existing links for this transcript (idempotent).
    """
    if not (transcript_text or "").strip():
        return []

    segments = parse_transcript_segments(transcript_text)
    if not segments:
        return []

    # Segment counts per speaker name
    counts: Counter = Counter()
    for s in segments:
        name = (s.get("speaker") or "").strip()
        if name:
            counts[name] += 1

    supabase = get_supabase()

    # Remove existing links for this transcript
    supabase.table("transcript_speakers").delete().eq(
        "transcript_id", transcript_id
    ).execute()

    result: list[dict[str, Any]] = []
    for speaker_name, segment_count in counts.items():
        speaker = await get_or_create_speaker(speaker_name)
        row = {
            "transcript_id": transcript_id,
            "speaker_id": speaker["id"],
            "segment_count": segment_count,
        }
        insert_resp = supabase.table("transcript_speakers").insert(row).execute()
        if insert_resp.data and len(insert_resp.data) > 0:
            result.append(insert_resp.data[0])
        else:
            result.append(row)

    return result


def _aggregate_speakers_from_ts_rows(
    ts_rows: list[dict[str, Any]],
    speakers_by_id: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Aggregate transcript_speakers rows into list of { name, segment_count, briefings }."""
    agg: dict[str, dict[str, Any]] = {}
    for row in ts_rows:
        sid = row.get("speaker_id")
        if not sid:
            continue
        if sid not in agg:
            agg[sid] = {"segment_count": 0, "briefing_ids": set()}
        agg[sid]["segment_count"] += row.get("segment_count") or 0
        tid = row.get("transcript_id")
        if tid:
            agg[sid]["briefing_ids"].add(tid)

    out: list[dict[str, Any]] = []
    for sid, data in agg.items():
        speaker = speakers_by_id.get(sid)
        if not speaker:
            continue
        out.append({
            "name": speaker.get("name", ""),
            "segment_count": data["segment_count"],
            "briefings": len(data["briefing_ids"]),
        })
    out.sort(key=lambda x: (-x["briefings"], x["name"]))
    return out


async def get_all_speakers(folder_id: str | None = None) -> list[dict[str, Any]]:
    """
    Get all speakers with aggregated stats (name, segment_count, briefings).
    If folder_id is set, only includes transcripts in that folder tree.
    """
    supabase = get_supabase()

    if folder_id:
        transcripts = await transcript_service.get_transcripts_in_folder_tree(folder_id)
    else:
        transcripts = await transcript_service.get_all_transcripts()
    transcript_ids = [str(t["id"]) for t in transcripts]

    if not transcript_ids:
        return []

    # Fetch transcript_speakers for these transcripts (Supabase has limit on in_ list size)
    batch_size = 200
    ts_rows: list[dict[str, Any]] = []
    for i in range(0, len(transcript_ids), batch_size):
        batch = transcript_ids[i : i + batch_size]
        response = (
            supabase.table("transcript_speakers")
            .select("speaker_id, transcript_id, segment_count")
            .in_("transcript_id", batch)
            .execute()
        )
        ts_rows.extend(response.data or [])

    if not ts_rows:
        return []

    speaker_ids = list({r["speaker_id"] for r in ts_rows})
    speakers_response = (
        supabase.table("speakers")
        .select("id, name")
        .in_("id", speaker_ids)
        .execute()
    )
    speakers_list = speakers_response.data or []
    speakers_by_id = {str(s["id"]): s for s in speakers_list}

    return _aggregate_speakers_from_ts_rows(ts_rows, speakers_by_id)


async def get_speakers_for_transcript(transcript_id: str) -> list[dict[str, Any]]:
    """Get speakers linked to a single transcript with segment counts."""
    supabase = get_supabase()
    ts_response = (
        supabase.table("transcript_speakers")
        .select("speaker_id, segment_count")
        .eq("transcript_id", transcript_id)
        .execute()
    )
    ts_rows = ts_response.data or []
    if not ts_rows:
        return []

    speaker_ids = [r["speaker_id"] for r in ts_rows]
    speakers_response = (
        supabase.table("speakers")
        .select("id, name")
        .in_("id", speaker_ids)
        .execute()
    )
    speakers_by_id = {str(s["id"]): s for s in (speakers_response.data or [])}

    return [
        {
            "name": speakers_by_id.get(r["speaker_id"], {}).get("name", ""),
            "segment_count": r.get("segment_count", 0),
            "briefings": 1,
        }
        for r in ts_rows
    ]


async def search_speakers(query: str, limit: int = 50) -> list[dict[str, Any]]:
    """
    Search speakers by name (case-insensitive), return aggregated stats.
    """
    query = (query or "").strip()
    supabase = get_supabase()

    if not query:
        return await get_all_speakers(folder_id=None)

    # Search by name (ilike)
    response = (
        supabase.table("speakers")
        .select("id, name")
        .ilike("name", f"%{query}%")
        .limit(limit)
        .execute()
    )
    speakers_list = response.data or []
    if not speakers_list:
        return []

    speaker_ids = [s["id"] for s in speakers_list]
    speakers_by_id = {str(s["id"]): s for s in speakers_list}

    # Get all transcript_speakers for these speakers
    batch_size = 200
    ts_rows: list[dict[str, Any]] = []
    for i in range(0, len(speaker_ids), batch_size):
        batch = speaker_ids[i : i + batch_size]
        ts_response = (
            supabase.table("transcript_speakers")
            .select("speaker_id, transcript_id, segment_count")
            .in_("speaker_id", batch)
            .execute()
        )
        ts_rows.extend(ts_response.data or [])

    return _aggregate_speakers_from_ts_rows(ts_rows, speakers_by_id)
