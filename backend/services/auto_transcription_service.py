"""Auto-transcription service for periodic YouTube monitoring."""

import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta

from backend.core.concurrency import auto_semaphore
from backend.core.database import get_supabase
from backend.services import job_service
from backend.services.youtube_service import get_channel_videos, get_playlist_info

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CRUD for auto_sources
# ---------------------------------------------------------------------------

async def get_all_sources() -> list[dict]:
    """List all auto-sources with persona name and last run info."""
    supabase = get_supabase()
    response = (
        supabase.table("auto_sources")
        .select("*, personas(name)")
        .order("created_at", desc=True)
        .execute()
    )
    sources = response.data or []

    # Fetch last run for each source
    source_ids = [s["id"] for s in sources]
    if source_ids:
        runs_response = (
            supabase.rpc(
                "get_latest_auto_runs",
                {"source_ids": source_ids},
            ).execute()
        )
        # Fallback: fetch individually if RPC doesn't exist
        last_runs: dict[str, dict] = {}
        if runs_response.data:
            for run in runs_response.data:
                last_runs[run["auto_source_id"]] = run
        else:
            # Manual fallback — get most recent run per source
            for sid in source_ids:
                run_resp = (
                    supabase.table("auto_runs")
                    .select("status, started_at")
                    .eq("auto_source_id", sid)
                    .order("started_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if run_resp.data:
                    last_runs[sid] = run_resp.data[0]

    result = []
    for s in sources:
        persona = s.pop("personas", None)
        s["persona_name"] = persona["name"] if persona else None
        lr = last_runs.get(s["id"]) if source_ids else None
        s["last_run_at"] = lr["started_at"] if lr else None
        s["last_run_status"] = lr["status"] if lr else None
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


async def get_all_enabled_sources() -> list[dict]:
    """Get all enabled auto-sources (for scheduler startup)."""
    supabase = get_supabase()
    response = (
        supabase.table("auto_sources")
        .select("*")
        .eq("is_enabled", True)
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

    # Validate title_filter regex if provided
    if data.get("title_filter"):
        try:
            re.compile(data["title_filter"])
        except re.error as e:
            raise ValueError(f"Invalid title_filter regex: {e}")

    supabase = get_supabase()
    insert_data = {
        "persona_id": data["persona_id"],
        "source_type": data["source_type"],
        "youtube_url": data["youtube_url"],
        "source_name": source_name,
        "folder_id": data.get("folder_id"),
        "speaker_hint": data.get("speaker_hint"),
        "check_interval_minutes": data.get("check_interval_minutes", 360),
        "max_videos_per_check": data.get("max_videos_per_check", 5),
        "title_filter": data.get("title_filter"),
    }
    response = supabase.table("auto_sources").insert(insert_data).execute()
    return response.data[0]


async def update_source(source_id: str, data: dict) -> dict | None:
    """Update an auto-source."""
    # Validate title_filter regex if provided
    if data.get("title_filter"):
        try:
            re.compile(data["title_filter"])
        except re.error as e:
            raise ValueError(f"Invalid title_filter regex: {e}")

    update_data = {
        k: v for k, v in data.items()
        if v is not None
    }
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
    """Delete an auto-source (cascades to runs and videos)."""
    supabase = get_supabase()
    response = (
        supabase.table("auto_sources")
        .delete()
        .eq("id", source_id)
        .execute()
    )
    return bool(response.data)


# ---------------------------------------------------------------------------
# Run history
# ---------------------------------------------------------------------------

async def get_runs_for_source(source_id: str, limit: int = 20) -> list[dict]:
    """Get recent runs for a specific source."""
    supabase = get_supabase()
    response = (
        supabase.table("auto_runs")
        .select("*")
        .eq("auto_source_id", source_id)
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


async def get_recent_runs(limit: int = 50) -> list[dict]:
    """Get recent runs across all sources."""
    supabase = get_supabase()
    response = (
        supabase.table("auto_runs")
        .select("*, auto_sources(source_name, personas(name))")
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    runs = response.data or []
    for run in runs:
        source = run.pop("auto_sources", None)
        run["source_name"] = source["source_name"] if source else None
        persona = source.get("personas") if source else None
        run["persona_name"] = persona["name"] if persona else None
    return runs


# ---------------------------------------------------------------------------
# Stale run cleanup (called on startup)
# ---------------------------------------------------------------------------

async def mark_stale_runs_as_failed() -> int:
    """Mark any runs stuck in 'running' for >1 hour as failed."""
    supabase = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    response = (
        supabase.table("auto_runs")
        .update({
            "status": "failed",
            "error_message": "Stale run cleaned up on startup",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("status", "running")
        .lt("started_at", cutoff)
        .execute()
    )
    count = len(response.data) if response.data else 0
    if count:
        logger.info("Cleaned up %d stale auto-runs", count)
    return count


# ---------------------------------------------------------------------------
# Core: check a source for new videos
# ---------------------------------------------------------------------------

async def check_source_for_new_videos(source_id: str) -> dict | None:
    """Check a single auto-source for new videos and create transcription jobs."""
    source = await get_source(source_id)
    if not source or not source.get("is_enabled"):
        return None

    # Multi-instance dedup: skip if a recent run exists
    supabase = get_supabase()
    half_interval = max(source["check_interval_minutes"] // 2, 5)
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=half_interval)).isoformat()
    recent = (
        supabase.table("auto_runs")
        .select("id")
        .eq("auto_source_id", source_id)
        .in_("status", ["running", "completed"])
        .gte("started_at", cutoff)
        .limit(1)
        .execute()
    )
    if recent.data:
        logger.info("Source %s was recently checked, skipping", source_id)
        return None

    # Create run record
    run_resp = (
        supabase.table("auto_runs")
        .insert({"auto_source_id": source_id, "status": "running"})
        .execute()
    )
    run = run_resp.data[0]
    run_id = run["id"]

    try:
        # Fetch videos from YouTube
        if source["source_type"] == "channel":
            result = await get_channel_videos(source["youtube_url"])
        else:
            result = await get_playlist_info(source["youtube_url"])

        all_videos = result.videos
        videos_found = len(all_videos)
        videos_skipped = 0
        details: list[dict] = []

        # Apply title filter
        if source.get("title_filter"):
            pattern = re.compile(source["title_filter"], re.IGNORECASE)
            filtered = []
            for v in all_videos:
                if pattern.search(v.title):
                    filtered.append(v)
                else:
                    videos_skipped += 1
                    details.append({
                        "url": v.url, "title": v.title, "action": "filtered"
                    })
                    # Record filtered video
                    try:
                        supabase.table("auto_source_videos").upsert({
                            "auto_source_id": source_id,
                            "youtube_url": v.url,
                            "video_title": v.title,
                            "action": "filtered",
                        }, on_conflict="auto_source_id,youtube_url").execute()
                    except Exception:
                        pass
            all_videos = filtered

        # Dedup: check which URLs already exist in transcripts or auto_source_videos
        video_urls = [v.url for v in all_videos]
        existing_urls: set[str] = set()

        if video_urls:
            # Check transcripts table
            tx_resp = (
                supabase.table("transcripts")
                .select("youtube_url")
                .in_("youtube_url", video_urls)
                .execute()
            )
            for row in tx_resp.data or []:
                existing_urls.add(row["youtube_url"])

            # Check auto_source_videos table
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
                details.append({
                    "url": v.url, "title": v.title, "action": "exists"
                })

        # Cap to max_videos_per_check
        to_process = new_videos[:source["max_videos_per_check"]]

        # Queue transcription jobs
        videos_queued = 0
        for video in to_process:
            try:
                job = await job_service.create_job(
                    youtube_url=video.url,
                    video_title=video.title,
                )

                # Import here to avoid circular imports
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

                # Record in auto_source_videos
                supabase.table("auto_source_videos").upsert({
                    "auto_source_id": source_id,
                    "youtube_url": video.url,
                    "video_title": video.title,
                    "action": "transcribed",
                    "job_id": job["id"],
                }, on_conflict="auto_source_id,youtube_url").execute()

                details.append({
                    "url": video.url, "title": video.title, "action": "queued"
                })
                videos_queued += 1

            except Exception as e:
                logger.error(
                    "Source %s: failed to queue job for %s: %s",
                    source_id, video.url, e
                )
                details.append({
                    "url": video.url, "title": video.title,
                    "action": "error", "error": str(e)
                })

        # Update run record
        supabase.table("auto_runs").update({
            "status": "completed",
            "videos_found": videos_found,
            "videos_new": len(new_videos),
            "videos_queued": videos_queued,
            "videos_skipped": videos_skipped,
            "details": details,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()

        logger.info(
            "Source %s: found=%d, new=%d, queued=%d, skipped=%d",
            source_id, videos_found, len(new_videos), videos_queued, videos_skipped
        )

        return {
            "run_id": run_id,
            "videos_found": videos_found,
            "videos_new": len(new_videos),
            "videos_queued": videos_queued,
            "videos_skipped": videos_skipped,
        }

    except Exception as e:
        logger.error("Source %s: check failed: %s", source_id, e, exc_info=True)
        supabase.table("auto_runs").update({
            "status": "failed",
            "error_message": str(e),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
        return None
