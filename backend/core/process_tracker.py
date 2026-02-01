"""Process tracking for job cancellation."""

import asyncio
from typing import Any


class TrackedProcess:
    """A tracked subprocess with cancellation support."""

    def __init__(self, process: asyncio.subprocess.Process, cancel_event: asyncio.Event):
        self.process = process
        self.cancel_event = cancel_event


# Global dictionary to track active processes
_processes: dict[str, TrackedProcess] = {}


def track_process(
    job_id: str,
    process: asyncio.subprocess.Process,
    cancel_event: asyncio.Event
) -> None:
    """Track a subprocess for potential cancellation."""
    _processes[job_id] = TrackedProcess(process, cancel_event)


def cancel_process(job_id: str) -> bool:
    """
    Cancel a tracked process.

    Returns True if the process was found and cancelled.
    """
    tracked = _processes.get(job_id)
    if not tracked:
        return False

    # Signal cancellation
    tracked.cancel_event.set()

    # Kill the process if it's still running
    try:
        if tracked.process.returncode is None:
            tracked.process.terminate()
    except ProcessLookupError:
        pass  # Process already terminated

    del _processes[job_id]
    return True


def untrack_process(job_id: str) -> None:
    """Remove a process from tracking."""
    _processes.pop(job_id, None)


def is_process_tracked(job_id: str) -> bool:
    """Check if a process is being tracked."""
    return job_id in _processes


def get_tracked_processes() -> list[str]:
    """Get list of tracked job IDs."""
    return list(_processes.keys())
