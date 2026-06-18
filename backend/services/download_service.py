"""Download service for yt-dlp audio extraction."""

import asyncio
import logging
import os
from pathlib import Path

from backend.core.exceptions import CancellationError, DownloadError

logger = logging.getLogger(__name__)
from backend.core.process_tracker import track_process, untrack_process
from backend.services.yt_dlp_utils import get_yt_dlp_base_args


async def download_audio(
    url: str,
    downloads_dir: str,
    job_id: str | None = None,
    cancel_event: asyncio.Event | None = None
) -> str:
    """
    Download audio from a YouTube video using yt-dlp.

    Returns the path to the downloaded audio file.
    """
    # Ensure downloads directory exists
    Path(downloads_dir).mkdir(parents=True, exist_ok=True)

    logger.info("Downloading audio from %s", url)
    output_template = os.path.join(downloads_dir, "%(id)s.%(ext)s")

    yt_dlp_args = get_yt_dlp_base_args()
    yt_dlp_args.extend([
        # Livestream VODs (press briefings, rallies) are frequently picked up by
        # auto-transcription while YouTube is still serving the live/post-live
        # DASH manifest. Without this, yt-dlp downloads from the *live edge* and
        # silently drops the start of the event — the transcript then begins
        # mid-event (timestamped from 00:00 of the truncated audio) so it looks
        # complete but the first half is missing. Forcing from-start fetches all
        # fragments. No-op for normal, fully-processed VODs.
        '--live-from-start',
        '--format', 'bestaudio/best',
        '-x',
        '--audio-format', 'mp3',
        '--audio-quality', '5',
        '--postprocessor-args', '-ac 1',
        '-o', output_template,
        '--print', 'after_move:filepath',
        url
    ])

    proc = await asyncio.create_subprocess_exec(
        *yt_dlp_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    # Track the process for cancellation
    if job_id and cancel_event:
        track_process(job_id, proc, cancel_event)

    try:
        # Monitor for cancellation while waiting
        output_path = ""
        error_output = ""

        while True:
            # Check for cancellation
            if cancel_event and cancel_event.is_set():
                proc.terminate()
                raise CancellationError()

            # Check if process has finished
            if proc.returncode is not None:
                break

            # Try to read output with timeout
            try:
                stdout_data = await asyncio.wait_for(
                    proc.stdout.readline(),
                    timeout=0.5
                )
                if stdout_data:
                    line = stdout_data.decode().strip()
                    if line and not line.startswith('['):
                        output_path = line
            except asyncio.TimeoutError:
                pass

            # Small sleep to prevent busy loop
            await asyncio.sleep(0.1)

        # Get remaining output
        remaining_stdout, stderr = await proc.communicate()
        if remaining_stdout:
            for line in remaining_stdout.decode().strip().split('\n'):
                if line and not line.startswith('['):
                    output_path = line

        error_output = stderr.decode() if stderr else ""

        if proc.returncode == 0 and output_path:
            logger.info("Download complete: %s", output_path)
            return output_path
        elif proc.returncode == -15:  # SIGTERM
            raise CancellationError()
        else:
            raise DownloadError(f"Download failed: {error_output or 'Unknown error'}")

    finally:
        if job_id:
            untrack_process(job_id)


async def cleanup_audio_file(file_path: str) -> None:
    """Clean up a downloaded audio file."""
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
    except OSError:
        logger.warning("Failed to clean up audio file: %s", file_path, exc_info=True)
