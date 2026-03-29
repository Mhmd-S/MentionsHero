"""Background scheduler for auto-transcription checks."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def start_scheduler() -> None:
    """Start the scheduler and load all enabled auto-sources."""
    from backend.config import get_settings
    settings = get_settings()
    if not settings.auto_transcription_enabled:
        logger.info("Auto-transcription scheduler disabled by config")
        return

    from backend.services.auto_transcription_service import (
        get_all_enabled_sources,
        mark_stale_runs_as_failed,
    )

    try:
        # Clean up stale runs from previous crashes
        await mark_stale_runs_as_failed()

        scheduler = get_scheduler()

        sources = await get_all_enabled_sources()
        for source in sources:
            _schedule_source(scheduler, source)

        scheduler.start()
        logger.info("Auto-transcription scheduler started with %d sources", len(sources))
    except Exception as e:
        logger.warning("Auto-transcription scheduler failed to start: %s (migration may not have run yet)", e)


def _schedule_source(scheduler: AsyncIOScheduler, source: dict) -> None:
    """Add or replace a scheduled job for an auto-source."""
    job_id = f"auto_source_{source['id']}"

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    from backend.services.auto_transcription_service import check_source_for_new_videos

    scheduler.add_job(
        check_source_for_new_videos,
        trigger=IntervalTrigger(minutes=source["check_interval_minutes"]),
        id=job_id,
        args=[source["id"]],
        replace_existing=True,
        max_instances=1,
    )
    logger.debug("Scheduled source %s every %d min", source["id"], source["check_interval_minutes"])


async def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Auto-transcription scheduler stopped")


def reschedule_source(source: dict) -> None:
    """Called when an auto-source is created, updated, or toggled."""
    scheduler = get_scheduler()
    if not scheduler.running:
        return

    if source.get("is_enabled"):
        _schedule_source(scheduler, source)
    else:
        remove_source(source["id"])


def remove_source(source_id: str) -> None:
    """Remove a scheduled job for an auto-source."""
    scheduler = get_scheduler()
    if not scheduler.running:
        return
    job_id = f"auto_source_{source_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.debug("Removed schedule for source %s", source_id)
