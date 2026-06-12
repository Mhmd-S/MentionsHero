"""News item read helpers.

Procurement now lives in ``analytical_procurement_service`` +
``scrapers/fox_news.py`` (real Fox articles via the dated sitemap). This module
only reads already-stored items, with optional date-range + outlet filtering.
"""

import logging
from datetime import datetime, timezone, timedelta

from backend.core.database import get_analytical_table

logger = logging.getLogger(__name__)


def _tbl(name: str):
    return get_analytical_table(name)


async def get_news_items(
    persona_id: str,
    days: int = 7,
    limit: int = 100,
    start: datetime | None = None,
    end: datetime | None = None,
    source: str | None = None,
) -> list[dict]:
    """Get news items for a persona.

    With ``start``/``end`` an explicit window is used; otherwise a rolling
    ``days`` look-back. ``source`` filters by outlet (matched against
    ``source_domain``/``source_name``). Newest-first, capped at ``limit``.
    """
    query = _tbl("news_items").select("*").eq("persona_id", persona_id)
    if start is not None:
        query = query.gte("published_at", start.isoformat())
    else:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = query.gte("published_at", cutoff)
    if end is not None:
        query = query.lte("published_at", end.isoformat())
    if source:
        # Match either the domain or the display name (e.g. "foxnews.com" / "Fox News").
        query = query.or_(
            f"source_domain.ilike.%{source}%,source_name.ilike.%{source}%"
        )
    response = query.order("published_at", desc=True).limit(limit).execute()
    return response.data or []


async def get_news_for_window(
    persona_id: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Fetch all news items within a time window (no limit) — used by the context service."""
    response = (
        _tbl("news_items")
        .select("*")
        .eq("persona_id", persona_id)
        .gte("published_at", start.isoformat())
        .lte("published_at", end.isoformat())
        .order("published_at", desc=True)
        .execute()
    )
    return response.data or []
