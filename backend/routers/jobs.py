"""Job management API routes."""

import asyncio
import json
import os
from typing import Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse

from backend.config import get_settings
from backend.core.database import get_supabase
from backend.core.exceptions import CancellationError
from backend.core.process_tracker import cancel_process
from backend.models.job import (
    Job,
    JobStatus,
    CreateJobRequest,
    CreateJobResponse,
    BatchJobsRequest,
    BatchJobsResponse,
    BulkCancelRequest,
    BulkCancelResponse,
    CancelResponse,
)
from backend.services import job_service, speaker_service, kalshi_service
from backend.utils.nlp import parse_transcript_segments
from backend.services.download_service import download_audio, cleanup_audio_file
from backend.services.transcription_service import transcribe_audio
from backend.services.youtube_service import validate_youtube_url, get_video_info

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# Concurrency control for batch processing
MAX_CONCURRENT = 10
_batch_semaphore = asyncio.Semaphore(MAX_CONCURRENT)


async def process_job(
    job_id: str,
    url: str,
    folder_id: str | None = None,
    speaker_hint: str | None = None
) -> None:
    """
    Process a transcription job in the background.

    Downloads audio, transcribes it, and saves to database.
    """
    cancel_event = asyncio.Event()
    audio_path: str | None = None
    upload_date: str | None = None
    downloads_dir = os.path.join(os.getcwd(), "downloads")

    try:
        # Check for cancellation before starting
        if await job_service.check_cancellation(job_id):
            raise CancellationError()

        # Fetch video info to get upload date and title
        video_title: str | None = None
        try:
            video_info = await get_video_info(url)
            upload_date = video_info.upload_date
            video_title = video_info.title
        except Exception:
            pass  # Continue without video info if fetch fails

        # Download audio
        await job_service.update_job_progress(
            job_id,
            JobStatus.DOWNLOADING,
            stage_progress={
                "substep": "Extracting audio",
                "substep_detail": "Using yt-dlp to download MP3"
            }
        )

        audio_path = await download_audio(
            url=url,
            downloads_dir=downloads_dir,
            job_id=job_id,
            cancel_event=cancel_event
        )

        # Check for cancellation before transcribing
        if await job_service.check_cancellation(job_id):
            raise CancellationError()

        # Transcribe audio
        await job_service.update_job_progress(
            job_id,
            JobStatus.TRANSCRIBING,
            stage_progress={
                "substep": "Transcribing with speaker identification",
                "substep_detail": "Gemini 2.0 Flash",
                "current_chunk": 1,
                "total_chunks": 1
            }
        )

        transcript = await transcribe_audio(
            audio_path=audio_path,
            cancel_event=cancel_event,
            speaker_hint=speaker_hint,
            video_title=video_title
        )

        # Clean up audio file
        if audio_path:
            await cleanup_audio_file(audio_path)
            audio_path = None

        # Check for cancellation before saving
        if await job_service.check_cancellation(job_id):
            raise CancellationError()

        # Save transcript
        await job_service.update_job_progress(
            job_id,
            JobStatus.SAVING,
            stage_progress={
                "substep": "Saving transcript",
                "substep_detail": "Storing in database"
            }
        )

        supabase = get_supabase()
        insert_data: dict[str, Any] = {
            "youtube_url": url,
            "transcript": transcript,
            "folder_id": folder_id
        }
        if upload_date:
            insert_data["upload_date"] = upload_date
        if video_title:
            insert_data["name"] = video_title
        response = supabase.table("transcripts").insert(insert_data).execute()

        # Insert returns representation by default; data is a list with one row
        row = response.data[0] if response.data else None
        transcript_id = row["id"] if row else None

        # Extract and save speakers for this transcript
        if transcript_id and transcript:
            try:
                await speaker_service.extract_and_save_transcript_speakers(
                    transcript_id, transcript
                )
            except Exception:
                pass  # Do not fail the job if speaker extraction fails

        # Auto-reprocess market analysis for personas whose aliases appear in this transcript
        if transcript_id and transcript:
            try:
                segments = parse_transcript_segments(transcript)
                speaker_names = list({s['speaker'] for s in segments if s.get('speaker')})
                affected_ids = await kalshi_service.find_affected_persona_ids(speaker_names)
                for pid in affected_ids:
                    await kalshi_service.reprocess_persona_markets(pid)
            except Exception:
                pass  # Never fail the job for market reprocessing

        # Mark job as completed
        await job_service.update_job_progress(
            job_id,
            JobStatus.COMPLETED,
            transcript_id=transcript_id
        )

    except CancellationError:
        # Clean up on cancellation
        if audio_path:
            await cleanup_audio_file(audio_path)
        await job_service.mark_job_cancelled(job_id)

    except Exception as e:
        # Clean up on error
        if audio_path:
            await cleanup_audio_file(audio_path)

        error_message = str(e)
        await job_service.update_job_progress(
            job_id,
            JobStatus.FAILED,
            error_message=error_message
        )


@router.get("")
async def list_jobs() -> dict[str, list[dict[str, Any]]]:
    """List all active jobs."""
    jobs = await job_service.get_active_jobs()
    return {"jobs": jobs}


@router.get("/list/stream")
async def stream_jobs_list():
    """Stream active jobs list updates via Server-Sent Events (no polling)."""
    list_event = job_service.get_list_event()
    wait_timeout = 30.0  # heartbeat so connection stays alive

    async def event_generator():
        # Send initial list immediately
        jobs = await job_service.get_active_jobs()
        yield f"data: {json.dumps({'jobs': jobs})}\n\n"

        while True:
            try:
                list_event.clear()
                await asyncio.wait_for(
                    asyncio.shield(asyncio.to_thread(list_event.wait)),
                    timeout=wait_timeout
                )
            except asyncio.TimeoutError:
                pass  # re-fetch and send (heartbeat)
            except asyncio.CancelledError:
                break
            except Exception:
                break
            jobs = await job_service.get_active_jobs()
            yield f"data: {json.dumps({'jobs': jobs})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("")
async def create_job(
    request: CreateJobRequest,
    background_tasks: BackgroundTasks
) -> CreateJobResponse:
    """Create a new transcription job."""
    if not request.url:
        raise HTTPException(status_code=400, detail="YouTube URL is required")

    if not validate_youtube_url(request.url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    # Create job in database
    job = await job_service.create_job(
        youtube_url=request.url,
        video_title=request.video_title
    )

    # Trigger processing in background
    background_tasks.add_task(
        process_job,
        job["id"],
        request.url,
        request.folder_id,
        request.speaker_hint
    )

    return CreateJobResponse(jobId=job["id"], status=JobStatus(job["status"]))


@router.post("/batch")
async def create_batch_jobs(
    request: BatchJobsRequest,
    background_tasks: BackgroundTasks
) -> BatchJobsResponse:
    """Create multiple transcription jobs for a batch of videos."""
    if not request.videos or len(request.videos) == 0:
        raise HTTPException(status_code=400, detail="At least one video is required")

    if len(request.videos) > 50:
        raise HTTPException(status_code=400, detail="Maximum 50 videos per batch")

    # Validate all URLs
    for video in request.videos:
        if not video.url or not validate_youtube_url(video.url):
            raise HTTPException(status_code=400, detail=f"Invalid YouTube URL: {video.url}")

    job_ids: list[str] = []

    # Create all jobs in the database
    for i, video in enumerate(request.videos):
        job = await job_service.create_job(
            youtube_url=video.url,
            video_title=video.title,
            playlist_id=request.playlist_id,
            playlist_name=request.playlist_name,
            playlist_index=i if request.playlist_id else None
        )
        job_ids.append(job["id"])

    # Process jobs in parallel with limited concurrency
    async def process_one(i: int) -> None:
        async with _batch_semaphore:
            await process_job(
                job_ids[i],
                request.videos[i].url,
                request.folder_id,
                request.speaker_hint
            )

    async def process_batch() -> None:
        await asyncio.gather(*[process_one(i) for i in range(len(job_ids))])

    background_tasks.add_task(process_batch)

    return BatchJobsResponse(jobIds=job_ids, total=len(job_ids))


@router.post("/bulk-cancel")
async def bulk_cancel_jobs(request: BulkCancelRequest) -> BulkCancelResponse:
    """Cancel all pending/active jobs for a playlist."""
    if not request.playlist_id:
        raise HTTPException(status_code=400, detail="Playlist ID is required")

    # Get jobs before cancelling to kill their processes
    supabase = get_supabase()
    terminal_statuses = f"({JobStatus.COMPLETED.value},{JobStatus.FAILED.value},{JobStatus.CANCELLED.value})"

    jobs_response = (
        supabase.table("jobs")
        .select("id, status")
        .eq("playlist_id", request.playlist_id)
        .filter("status", "not.in", terminal_statuses)
        .execute()
    )

    jobs = jobs_response.data or []

    # Kill running processes
    for job in jobs:
        cancel_process(job["id"])

    # Cancel in database
    cancelled_count = await job_service.bulk_cancel_playlist_jobs(request.playlist_id)

    return BulkCancelResponse(cancelled=cancelled_count)


@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str) -> CancelResponse:
    """Request cancellation of a job."""
    # Get current job status
    job = await job_service.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    terminal_statuses = [
        JobStatus.COMPLETED.value,
        JobStatus.FAILED.value,
        JobStatus.CANCELLED.value
    ]
    if job.get("status") in terminal_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status: {job.get('status')}"
        )

    # Request cancellation
    await job_service.request_cancellation(job_id)

    # Try to kill the running process
    cancel_process(job_id)

    return CancelResponse(success=True, message="Cancellation requested")


@router.post("/{job_id}/force-cancel")
async def force_cancel_job(job_id: str) -> CancelResponse:
    """Force cancel a job regardless of its current state."""
    # Kill any running process
    cancel_process(job_id)

    # Force cancel in database
    await job_service.force_cancel_job(job_id)

    return CancelResponse(success=True, message="Job force cancelled")


@router.get("/{job_id}/stream")
async def stream_job(job_id: str):
    """Stream job status updates via Server-Sent Events (event-driven, no polling)."""
    job_event = job_service.get_job_event(job_id)
    wait_timeout = 30.0  # heartbeat so connection stays alive

    async def event_generator():
        last_status = ""
        last_progress = ""

        while True:
            try:
                job = await job_service.get_job(job_id)

                if not job:
                    yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
                    break

                # Only send update if something changed
                current_progress = json.dumps(job.get("stage_progress", {}))
                if job.get("status") != last_status or current_progress != last_progress:
                    last_status = job.get("status")
                    last_progress = current_progress
                    yield f"data: {json.dumps(job)}\n\n"

                # Stop if job is in terminal state
                if job.get("status") in [
                    JobStatus.COMPLETED.value,
                    JobStatus.FAILED.value,
                    JobStatus.CANCELLED.value
                ]:
                    break

                job_event.clear()
                await asyncio.wait_for(
                    asyncio.shield(asyncio.to_thread(job_event.wait)),
                    timeout=wait_timeout
                )

            except asyncio.TimeoutError:
                pass  # re-fetch and send if changed (heartbeat)
            except Exception:
                yield f"data: {json.dumps({'error': 'Failed to fetch job status'})}\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
