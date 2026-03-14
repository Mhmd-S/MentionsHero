"""Job service for database operations."""

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

from backend.core.database import get_supabase
from backend.models.job import JobStatus, StageProgress

logger = logging.getLogger(__name__)

# Single-worker executor to serialize Supabase calls (httpx client is not thread-safe)
_db_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="job-db")

# Thread-safe events for SSE: wait() in thread pool, set() from async main thread
_jobs_list_event: threading.Event | None = None
_job_events: dict[str, threading.Event] = {}


def _get_list_event() -> threading.Event:
    global _jobs_list_event
    if _jobs_list_event is None:
        _jobs_list_event = threading.Event()
    return _jobs_list_event


def _get_job_event(job_id: str) -> threading.Event:
    if job_id not in _job_events:
        _job_events[job_id] = threading.Event()
    return _job_events[job_id]


def notify_jobs_list_changed() -> None:
    """Call when any job is created/updated/cancelled so list stream can push."""
    _get_list_event().set()


def notify_job_changed(job_id: str) -> None:
    """Call when a specific job is updated so its stream can push."""
    _get_job_event(job_id).set()


def get_list_event() -> threading.Event:
    """Event to wait on in the jobs list SSE loop (use in asyncio.to_thread)."""
    return _get_list_event()


def get_job_event(job_id: str) -> threading.Event:
    """Event to wait on in a per-job SSE loop (use in asyncio.to_thread)."""
    return _get_job_event(job_id)


async def create_job(
    youtube_url: str,
    video_title: str | None = None,
    playlist_id: str | None = None,
    playlist_name: str | None = None,
    playlist_index: int | None = None
) -> dict[str, Any]:
    """Create a new job in the database."""
    supabase = get_supabase()

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        _db_executor,
        lambda: supabase.table("jobs").insert({
            "youtube_url": youtube_url,
            "status": JobStatus.PENDING.value,
            "stage_progress": {},
            "video_title": video_title,
            "playlist_id": playlist_id,
            "playlist_name": playlist_name,
            "playlist_index": playlist_index
        }).execute()
    )

    notify_jobs_list_changed()
    return response.data[0]


async def get_job(job_id: str) -> dict[str, Any] | None:
    """Get a job by ID."""
    supabase = get_supabase()

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        _db_executor,
        lambda: supabase.table("jobs").select("*").eq("id", job_id).single().execute()
    )
    return response.data


async def get_active_jobs() -> list[dict[str, Any]]:
    """Get all non-terminal jobs."""
    supabase = get_supabase()

    terminal_statuses = f"({JobStatus.COMPLETED.value},{JobStatus.FAILED.value},{JobStatus.CANCELLED.value})"

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        _db_executor,
        lambda: (
            supabase.table("jobs")
            .select("*")
            .filter("status", "not.in", terminal_statuses)
            .order("created_at", desc=True)
            .execute()
        )
    )

    return response.data or []


async def update_job_progress(
    job_id: str,
    status: JobStatus,
    stage_progress: dict[str, Any] | None = None,
    error_message: str | None = None,
    transcript_id: str | None = None
) -> None:
    """Update job progress in the database."""
    supabase = get_supabase()

    update_data: dict[str, Any] = {
        "status": status.value,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    if stage_progress is not None:
        update_data["stage_progress"] = stage_progress

    if error_message is not None:
        update_data["error_message"] = error_message

    if transcript_id is not None:
        update_data["transcript_id"] = transcript_id

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        _db_executor,
        lambda: supabase.table("jobs").update(update_data).eq("id", job_id).execute()
    )
    logger.info("Job %s: status -> %s", job_id, status.value)
    notify_job_changed(job_id)
    notify_jobs_list_changed()


async def check_cancellation(job_id: str) -> bool:
    """Check if cancellation has been requested for a job."""
    supabase = get_supabase()

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(
        _db_executor,
        lambda: (
            supabase.table("jobs")
            .select("cancel_requested")
            .eq("id", job_id)
            .single()
            .execute()
        )
    )

    if response.data:
        return response.data.get("cancel_requested", False)
    return False


async def mark_job_cancelled(job_id: str) -> None:
    """Mark a job as cancelled."""
    supabase = get_supabase()

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        _db_executor,
        lambda: supabase.table("jobs").update({
            "status": JobStatus.CANCELLED.value,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", job_id).execute()
    )
    notify_job_changed(job_id)
    notify_jobs_list_changed()


async def request_cancellation(job_id: str) -> bool:
    """
    Request cancellation for a job.

    Returns True if the job exists and is in a non-terminal state.
    """
    supabase = get_supabase()

    # Get current job status
    job = await get_job(job_id)
    if not job:
        return False

    terminal_statuses = [
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value
    ]
    if job.get("status") in terminal_statuses:
        return False

    # Set cancel_requested flag
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        _db_executor,
        lambda: supabase.table("jobs").update({
            "cancel_requested": True
        }).eq("id", job_id).execute()
    )
    notify_job_changed(job_id)
    notify_jobs_list_changed()

    return True


async def force_cancel_job(job_id: str) -> bool:
    """Force cancel a job regardless of its current state."""
    supabase = get_supabase()

    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        _db_executor,
        lambda: supabase.table("jobs").update({
            "status": JobStatus.CANCELLED.value,
            "cancel_requested": True,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("id", job_id).execute()
    )
    notify_job_changed(job_id)
    notify_jobs_list_changed()

    return True


async def bulk_cancel_playlist_jobs(playlist_id: str) -> int:
    """
    Cancel all pending/active jobs for a playlist.

    Returns the number of jobs cancelled.
    """
    supabase = get_supabase()

    terminal_statuses = f"({JobStatus.COMPLETED.value},{JobStatus.FAILED.value},{JobStatus.CANCELLED.value})"

    loop = asyncio.get_running_loop()

    # Get all pending/active jobs for this playlist
    jobs_response = await loop.run_in_executor(
        _db_executor,
        lambda: (
            supabase.table("jobs")
            .select("id, status")
            .eq("playlist_id", playlist_id)
            .filter("status", "not.in", terminal_statuses)
            .execute()
        )
    )

    jobs = jobs_response.data or []
    if not jobs:
        return 0

    # Mark all as cancelled
    await loop.run_in_executor(
        _db_executor,
        lambda: supabase.table("jobs").update({
            "cancel_requested": True,
            "status": JobStatus.CANCELLED.value,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }).eq("playlist_id", playlist_id).filter(
            "status", "not.in", terminal_statuses
        ).execute()
    )

    for job in jobs:
        notify_job_changed(job["id"])
    notify_jobs_list_changed()

    return len(jobs)
