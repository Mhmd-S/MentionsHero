"""Auto-transcription service: manual-trigger YouTube monitoring."""

import asyncio
import logging
from datetime import datetime, timezone

from backend.core.concurrency import auto_semaphore
from backend.core.database import get_supabase
from backend.services import job_service
from backend.services.youtube_service import get_channel_videos, get_playlist_info

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CRUD for auto_sources
# ---------------------------------------------------------------------------

async def get_all_sources() -> list[dict]:
    """List all auto-sources with persona name."""
    supabase = get_supabase()
    response = (
        supabase.table("auto_sources")
        .select("*, personas(name)")
        .order("created_at", desc=True)
        .execute()
    )
    sources = response.data or []
    result = []
    for s in sources:
        persona = s.pop("personas", None)
        s["persona_name"] = persona["name"] if persona else None
        result.append(s)
    return result


async def get_source(source_id: str) -> dict | None:
    """Get a single auto-source by ID."""
    supabase = get_supabase()
    response = (
        supabase.table("auto_sources")
        .select("*, personas(name)")
        .eq("id", source_id)
        .single()
        .execute()
    )
    if not response.data:
        return None
    s = response.data
    persona = s.pop("personas", None)
    s["persona_name"] = persona["name"] if persona else None
    return s


async def get_sources_for_persona(persona_id: str) -> list[dict]:
    """Get auto-sources for a specific persona."""
    supabase = get_supabase()
    response = (
        supabase.table("auto_sources")
        .select("*")
        .eq("persona_id", persona_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


async def create_source(data: dict) -> dict:
    """Create a new auto-source. Fetches source_name from YouTube."""
    source_name = None
    try:
        if data["source_type"] == "channel":
            info = await get_channel_videos(data["youtube_url"])
            source_name = info.title
        else:
            info = await get_playlist_info(data["youtube_url"])
            source_name = info.title
    except Exception:
        logger.warning("Failed to fetch source name for %s", data["youtube_url"])

    supabase = get_supabase()
    insert_data = {
        "persona_id": data["persona_id"],
        "source_type": data["source_type"],
        "youtube_url": data["youtube_url"],
        "source_name": source_name,
        "folder_id": data.get("folder_id"),
        "speaker_hint": data.get("speaker_hint"),
        "max_videos_per_check": data.get("max_videos_per_check", 5),
        "backfill_limit": data.get("backfill_limit", 500),
        "title_filter": data.get("title_filter"),
    }
    from postgrest.exceptions import APIError
    try:
        response = supabase.table("auto_sources").insert(insert_data).execute()
    except APIError as e:
        if "23505" in str(e) or "unique" in str(e).lower():
            raise ValueError("This persona already has a source for this YouTube URL")
        raise
    return response.data[0]


async def update_source(source_id: str, data: dict) -> dict | None:
    """Update an auto-source."""
    update_data = {k: v for k, v in data.items() if v is not None}
    if not update_data:
        return await get_source(source_id)

    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()

    supabase = get_supabase()
    response = (
        supabase.table("auto_sources")
        .update(update_data)
        .eq("id", source_id)
        .execute()
    )
    if not response.data:
        return None
    return response.data[0]


async def delete_source(source_id: str) -> bool:
    """Delete an auto-source (cascades to videos)."""
    supabase = get_supabase()
    response = (
        supabase.table("auto_sources")
        .delete()
        .eq("id", source_id)
        .execute()
    )
    return bool(response.data)


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

async def get_timeline(limit: int = 200) -> list[dict]:
    """Global timeline of every video processed across all sources, newest first.

    Joins auto_source_videos with auto_sources (source_name, persona name) and
    enriches each entry with the linked job's status (when one exists) plus the
    transcript id (when the URL was eventually transcribed).
    """
    supabase = get_supabase()
    response = (
        supabase.table("auto_source_videos")
        .select("*, auto_sources(source_name, persona_id, personas(name))")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = response.data or []
    if not rows:
        return []

    job_ids = [r["job_id"] for r in rows if r.get("job_id")]
    jobs_by_id: dict[str, dict] = {}
    if job_ids:
        jobs_resp = (
            supabase.table("jobs")
            .select("id, status, error_message")
            .in_("id", job_ids)
            .execute()
        )
        for j in jobs_resp.data or []:
            jobs_by_id[j["id"]] = j

    youtube_urls = list({r["youtube_url"] for r in rows})
    transcripts_by_url: dict[str, str] = {}
    if youtube_urls:
        tx_resp = (
            supabase.table("transcripts")
            .select("id, youtube_url")
            .in_("youtube_url", youtube_urls)
            .execute()
        )
        for t in tx_resp.data or []:
            transcripts_by_url[t["youtube_url"]] = t["id"]

    result: list[dict] = []
    for r in rows:
        source = r.pop("auto_sources", None) or {}
        persona = source.get("personas") or {}
        job = jobs_by_id.get(r.get("job_id")) if r.get("job_id") else None
        result.append({
            "id": r["id"],
            "auto_source_id": r["auto_source_id"],
            "source_name": source.get("source_name"),
            "persona_id": source.get("persona_id"),
            "persona_name": persona.get("name"),
            "youtube_url": r["youtube_url"],
            "video_title": r.get("video_title"),
            "action": r["action"],
            "job_id": r.get("job_id"),
            "job_status": job["status"] if job else None,
            "job_error": job.get("error_message") if job else None,
            "transcript_id": transcripts_by_url.get(r["youtube_url"]),
            "created_at": r["created_at"],
        })
    return result


# ---------------------------------------------------------------------------
# Manual run: discover videos and queue transcription jobs
# ---------------------------------------------------------------------------

async def run_source(source_id: str) -> dict:
    """Discover new videos for a source, queue transcription jobs, return counts.

    Synchronous (caller awaits): performs the YouTube fetch + filtering +
    dedup + job creation inline. Each transcription itself runs in the
    background via `process_job`. Returns a result the UI can show directly.
    """
    source = await get_source(source_id)
    if not source:
        raise ValueError("Source not found")

    return await _discover_and_queue(
        source,
        playlist_end=50,
        queue_cap=source.get("max_videos_per_check") or 5,
    )


async def backfill_source(source_id: str) -> dict:
    """One-shot backfill: pull every video yt-dlp can list for the source
    (no `--playlist-end` cap for channels; playlists are already unbounded),
    apply title-filter and dedup, then queue up to `backfill_limit` new jobs.

    A `backfill_limit` of None or 0 means no cap on what's queued. The
    auto_semaphore (max 3 concurrent) still throttles execution so manual
    jobs are not starved.
    """
    source = await get_source(source_id)
    if not source:
        raise ValueError("Source not found")

    raw_limit = source.get("backfill_limit")
    queue_cap = None if not raw_limit else int(raw_limit)
    return await _discover_and_queue(source, playlist_end=None, queue_cap=queue_cap)


async def _discover_and_queue(
    source: dict,
    *,
    playlist_end: int | None,
    queue_cap: int | None,
) -> dict:
    """Shared discovery → filter → dedup → queue pipeline used by both
    `run_source` (capped) and `backfill_source` (full history).

    `playlist_end` is forwarded to yt-dlp for channel sources; None = no cap.
    `queue_cap` is the maximum number of new videos to queue this call;
    None = queue everything.
    """
    source_id = source["id"]
    supabase = get_supabase()

    # Fetch videos from YouTube
    if source["source_type"] == "channel":
        result = await get_channel_videos(source["youtube_url"], playlist_end=playlist_end)
    else:
        result = await get_playlist_info(source["youtube_url"])

    all_videos = result.videos
    videos_found = len(all_videos)
    videos_filtered = 0
    details: list[dict] = []

    # Title-keyword filter (comma-separated, case-insensitive)
    if source.get("title_filter"):
        keywords = [k.strip().lower() for k in source["title_filter"].split(",") if k.strip()]
        kept = []
        for v in all_videos:
            title_lower = v.title.lower()
            if any(kw in title_lower for kw in keywords):
                kept.append(v)
            else:
                videos_filtered += 1
                details.append({"url": v.url, "title": v.title, "action": "filtered"})
                try:
                    supabase.table("auto_source_videos").upsert({
                        "auto_source_id": source_id,
                        "youtube_url": v.url,
                        "video_title": v.title,
                        "action": "filtered",
                    }, on_conflict="auto_source_id,youtube_url").execute()
                except Exception:
                    pass
        all_videos = kept

    # Dedup against transcripts and prior runs
    video_urls = [v.url for v in all_videos]
    existing_urls: set[str] = set()
    if video_urls:
        tx_resp = (
            supabase.table("transcripts")
            .select("youtube_url")
            .in_("youtube_url", video_urls)
            .execute()
        )
        for row in tx_resp.data or []:
            existing_urls.add(row["youtube_url"])

        asv_resp = (
            supabase.table("auto_source_videos")
            .select("youtube_url")
            .eq("auto_source_id", source_id)
            .in_("youtube_url", video_urls)
            .eq("action", "transcribed")
            .execute()
        )
        for row in asv_resp.data or []:
            existing_urls.add(row["youtube_url"])

    new_videos = [v for v in all_videos if v.url not in existing_urls]
    for v in all_videos:
        if v.url in existing_urls:
            details.append({"url": v.url, "title": v.title, "action": "exists"})

    to_process = new_videos if queue_cap is None else new_videos[:queue_cap]

    videos_queued = 0
    for video in to_process:
        try:
            job = await job_service.create_job(
                youtube_url=video.url,
                video_title=video.title,
            )

            from backend.routers.jobs import process_job

            async def _run_with_semaphore(
                j_id: str, j_url: str, j_folder: str | None, j_hint: str | None
            ) -> None:
                async with auto_semaphore:
                    await process_job(j_id, j_url, j_folder, j_hint)

            asyncio.create_task(
                _run_with_semaphore(
                    job["id"],
                    video.url,
                    source.get("folder_id"),
                    source.get("speaker_hint"),
                )
            )

            supabase.table("auto_source_videos").upsert({
                "auto_source_id": source_id,
                "youtube_url": video.url,
                "video_title": video.title,
                "action": "transcribed",
                "job_id": job["id"],
            }, on_conflict="auto_source_id,youtube_url").execute()

            details.append({"url": video.url, "title": video.title, "action": "queued"})
            videos_queued += 1

        except Exception as e:
            logger.error(
                "Source %s: failed to queue job for %s: %s",
                source_id, video.url, e
            )
            details.append({
                "url": video.url, "title": video.title,
                "action": "error", "error": str(e),
            })

    logger.info(
        "Source %s manual run: found=%d, filtered=%d, queued=%d, exists=%d",
        source_id, videos_found, videos_filtered, videos_queued,
        len(all_videos) - len(new_videos),
    )

    return {
        "videos_found": videos_found,
        "videos_filtered": videos_filtered,
        "videos_existing": len(all_videos) - len(new_videos),
        "videos_queued": videos_queued,
        "details": details,
    }
