"""Public (unauthenticated) API routes for transcript viewing and persona browsing."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from backend.core.database import get_supabase
from backend.models.persona import PublicPersona, PublicPersonaDetail, PublicPersonaTranscript
from backend.models.transcript import (
    PublicSegment,
    PublicTranscriptResponse,
    ReadStatusResponse,
    RecordReadRequest,
)
from backend.services import persona_service, transcript_service
from backend.utils.transcript_filter import escape_html, parse_transcript

router = APIRouter(prefix="/api/public", tags=["public"])

FREE_TIER_LIMIT = 5  # reads per calendar month


# --- Profile endpoint ---


@router.get("/profile")
async def get_profile(request: Request) -> dict:
    """Get current user's profile (role). Requires Bearer token."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = auth_header[7:]
    supabase = get_supabase()

    try:
        user_resp = supabase.auth.get_user(token)
        if not user_resp or not user_resp.user:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_id = user_resp.user.id
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = (
        supabase.table("profiles")
        .select("role")
        .eq("id", user_id)
        .execute()
    )

    if not result.data:
        # Profile doesn't exist yet (user created before migration) — create it
        supabase.table("profiles").insert({"id": user_id, "role": "client"}).execute()
        return {"role": "client"}

    return {"role": result.data[0]["role"]}


# --- Persona endpoints ---


@router.get("/personas", response_model=list[PublicPersona])
async def list_public_personas() -> list[PublicPersona]:
    """List all published personas for the public directory. No auth required."""
    personas = await persona_service.get_public_personas()
    return [PublicPersona(**p) for p in personas]


@router.get("/personas/{slug}", response_model=PublicPersonaDetail)
async def get_public_persona(slug: str) -> PublicPersonaDetail:
    """Get a persona by slug with their transcript list. No auth required."""
    persona = await persona_service.get_persona_by_slug(slug)
    if not persona:
        raise HTTPException(status_code=404, detail="Persona not found")

    transcripts_data = await persona_service.get_public_transcripts_for_persona(persona["id"])
    transcripts = [PublicPersonaTranscript(**t) for t in transcripts_data]

    return PublicPersonaDetail(
        id=persona["id"],
        name=persona["name"],
        slug=persona.get("slug"),
        image_url=persona.get("image_url"),
        description=persona.get("description"),
        transcripts=transcripts,
    )


# --- Transcript endpoint ---


@router.get("/transcripts/{transcript_id}", response_model=PublicTranscriptResponse)
async def get_public_transcript(transcript_id: str) -> PublicTranscriptResponse:
    """Public read-only transcript with resolved speaker names. No auth required."""
    transcript = await transcript_service.get_transcript_by_id(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    raw_text = transcript.get("transcript", "")
    segments_raw = parse_transcript(raw_text)

    # Build alias map and resolve speakers
    alias_map = await persona_service.build_alias_to_persona_map()
    raw_speakers = list({s["speaker"] for s in segments_raw})
    speaker_map = persona_service.resolve_transcript_speakers(raw_speakers, alias_map)

    # Build response segments with counts and ordering
    segment_counts: dict[str, int] = {}
    speakers_ordered: list[str] = []
    seen: set[str] = set()
    public_segments: list[PublicSegment] = []

    for seg in segments_raw:
        raw_sp = seg["speaker"]
        display_sp = speaker_map.get(raw_sp, raw_sp)
        resolved = display_sp != raw_sp

        public_segments.append(PublicSegment(
            speaker=display_sp,
            speaker_raw=raw_sp,
            resolved=resolved,
            content=escape_html(seg["content"]),
        ))

        segment_counts[display_sp] = segment_counts.get(display_sp, 0) + 1
        if display_sp not in seen:
            seen.add(display_sp)
            speakers_ordered.append(display_sp)

    return PublicTranscriptResponse(
        id=transcript["id"],
        name=transcript.get("name"),
        youtube_url=transcript.get("youtube_url"),
        upload_date=transcript.get("upload_date"),
        created_at=transcript["created_at"],
        segments=public_segments,
        speaker_map=speaker_map,
        speakers=speakers_ordered,
        segment_counts=segment_counts,
    )


# --- Read metering endpoint ---


@router.post("/reads/record", response_model=ReadStatusResponse)
async def record_transcript_read(body: RecordReadRequest, request: Request) -> ReadStatusResponse:
    """Record a transcript read and check monthly limit. Requires Bearer token."""
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return ReadStatusResponse(allowed=False, reads_this_month=0, limit=FREE_TIER_LIMIT)

    token = auth_header[7:]
    supabase = get_supabase()

    try:
        user_resp = supabase.auth.get_user(token)
        if not user_resp or not user_resp.user:
            return ReadStatusResponse(allowed=False, reads_this_month=0, limit=FREE_TIER_LIMIT)
        user_id = user_resp.user.id
    except Exception:
        return ReadStatusResponse(allowed=False, reads_this_month=0, limit=FREE_TIER_LIMIT)

    # Check current month read count
    month_start = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    count_resp = (
        supabase.table("transcript_reads")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .gte("read_at", month_start.isoformat())
        .execute()
    )
    current_count = count_resp.count or 0

    # Check if already read (don't double-count)
    existing = (
        supabase.table("transcript_reads")
        .select("id")
        .eq("user_id", user_id)
        .eq("transcript_id", body.transcript_id)
        .execute()
    )
    already_read = bool(existing.data)

    if already_read:
        return ReadStatusResponse(allowed=True, reads_this_month=current_count, limit=FREE_TIER_LIMIT)

    if current_count >= FREE_TIER_LIMIT:
        return ReadStatusResponse(allowed=False, reads_this_month=current_count, limit=FREE_TIER_LIMIT)

    # Record the read
    supabase.table("transcript_reads").insert({
        "user_id": user_id,
        "transcript_id": body.transcript_id,
    }).execute()

    return ReadStatusResponse(
        allowed=True,
        reads_this_month=current_count + 1,
        limit=FREE_TIER_LIMIT,
    )
