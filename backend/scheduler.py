"""Background scheduler for analytical data procurement."""

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
    """Start the scheduler for analytical procurement jobs.

    Auto-transcription is manual-only — no background scheduling.
    """
    from backend.config import get_settings
    settings = get_settings()

    scheduler = get_scheduler()

    if settings.analytical_procurement_enabled:
        _schedule_analytical_procurement(scheduler)

    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")


async def stop_scheduler() -> None:
    """Gracefully shut down the scheduler."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def _schedule_analytical_procurement(scheduler: AsyncIOScheduler) -> None:
    """Add scheduled jobs that keep the real sources current.

    Each run scrapes a short rolling window (last 2 days) for the Trump persona —
    the one-off Jan→now backfill is triggered manually from the Analytical page.
    """
    from datetime import datetime, timezone, timedelta

    from backend.services.analytical_procurement_service import run_scrape

    ROLLING_WINDOW_DAYS = 2

    async def _scrape_task(source_type: str) -> None:
        persona_id = await _get_trump_persona_id()
        if persona_id:
            start = datetime.now(timezone.utc) - timedelta(days=ROLLING_WINDOW_DAYS)
            await run_scrape(source_type, persona_id, start)

    async def _news_task() -> None:
        await _scrape_task("news_fox")

    async def _truth_social_task() -> None:
        await _scrape_task("truth_social")

    scheduler.add_job(
        _news_task,
        trigger=IntervalTrigger(hours=6),
        id="analytical_news_procurement",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.add_job(
        _truth_social_task,
        trigger=IntervalTrigger(hours=12),
        id="analytical_truth_social_procurement",
        replace_existing=True,
        max_instances=1,
    )
    logger.info("Analytical procurement jobs scheduled (Fox news: 6h, Truth Social: 12h)")


async def _get_trump_persona_id() -> str | None:
    """Look up Trump's persona ID from the database."""
    try:
        from backend.core.database import get_supabase
        supabase = get_supabase()
        response = (
            supabase.table("personas")
            .select("id")
            .ilike("name", "%trump%")
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]["id"]
    except Exception as e:
        logger.warning("Failed to look up Trump persona: %s", e)
    return None
