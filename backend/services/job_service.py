"""Job service for database operations."""

from datetime import datetime, timezone
from typing import Any

from backend.core.database import get_supabase
from backend.models.job import JobStatus, StageProgress


async def create_job(
    youtube_url: str,
    video_title: str | None = None,
    playlist_id: str | None = None,
    playlist_name: str | None = None,
    playlist_index: int | None = None
) -> dict[str, Any]:
    """Create a new job in the database."""
    supabase = get_supabase()

    response = supabase.table("jobs").insert({
        "youtube_url": youtube_url,
        "status": JobStatus.PENDING.value,
        "stage_progress": {},
        "video_title": video_title,
        "playlist_id": playlist_id,
        "playlist_name": playlist_name,
        "playlist_index": playlist_index
    }).execute()

    return response.data[0]


async def get_job(job_id: str) -> dict[str, Any] | None:
    """Get a job by ID."""
    supabase = get_supabase()

    response = supabase.table("jobs").select("*").eq("id", job_id).single().execute()
    return response.data


async def get_active_jobs() -> list[dict[str, Any]]:
    """Get all non-terminal jobs."""
    supabase = get_supabase()

    terminal_statuses = f"({JobStatus.COMPLETED.value},{JobStatus.FAILED.value},{JobStatus.CANCELLED.value})"
    response = (
        supabase.table("jobs")
        .select("*")
        .filter("status", "not.in", terminal_statuses)
        .order("created_at", desc=True)
        .execute()
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

    supabase.table("jobs").update(update_data).eq("id", job_id).execute()


async def check_cancellation(job_id: str) -> bool:
    """Check if cancellation has been requested for a job."""
    supabase = get_supabase()

    response = (
        supabase.table("jobs")
        .select("cancel_requested")
        .eq("id", job_id)
        .single()
        .execute()
    )

    if response.data:
        return response.data.get("cancel_requested", False)
    return False


async def mark_job_cancelled(job_id: str) -> None:
    """Mark a job as cancelled."""
    supabase = get_supabase()

    supabase.table("jobs").update({
        "status": JobStatus.CANCELLED.value,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", job_id).execute()


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
    supabase.table("jobs").update({
        "cancel_requested": True
    }).eq("id", job_id).execute()

    return True


async def force_cancel_job(job_id: str) -> bool:
    """Force cancel a job regardless of its current state."""
    supabase = get_supabase()

    supabase.table("jobs").update({
        "status": JobStatus.CANCELLED.value,
        "cancel_requested": True,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("id", job_id).execute()

    return True


async def bulk_cancel_playlist_jobs(playlist_id: str) -> int:
    """
    Cancel all pending/active jobs for a playlist.

    Returns the number of jobs cancelled.
    """
    supabase = get_supabase()

    terminal_statuses = f"({JobStatus.COMPLETED.value},{JobStatus.FAILED.value},{JobStatus.CANCELLED.value})"

    # Get all pending/active jobs for this playlist
    jobs_response = (
        supabase.table("jobs")
        .select("id, status")
        .eq("playlist_id", playlist_id)
        .filter("status", "not.in", terminal_statuses)
        .execute()
    )

    jobs = jobs_response.data or []
    if not jobs:
        return 0

    # Mark all as cancelled
    supabase.table("jobs").update({
        "cancel_requested": True,
        "status": JobStatus.CANCELLED.value,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("playlist_id", playlist_id).filter(
        "status", "not.in", terminal_statuses
    ).execute()

    return len(jobs)
