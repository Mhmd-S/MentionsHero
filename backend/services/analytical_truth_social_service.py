"""Truth Social post read helpers.

Procurement now lives in ``analytical_procurement_service`` +
``scrapers/truth_social.py`` (real @realDonaldTrump posts via the Mastodon API).
This module only reads already-stored posts.
"""

import logging
from datetime import datetime, timezone, timedelta

from backend.core.database import get_analytical_table

logger = logging.getLogger(__name__)


def _tbl(name: str):
    return get_analytical_table(name)


async def get_posts(
    persona_id: str,
    days: int = 7,
    limit: int = 100,
    start: datetime | None = None,
    end: datetime | None = None,
) -> list[dict]:
    """Get Truth Social posts for a persona.

    With ``start``/``end`` an explicit window is used; otherwise a rolling
    ``days`` look-back. Always ordered newest-first and capped at ``limit``.
    """
    query = _tbl("truth_social_posts").select("*").eq("persona_id", persona_id)
    if start is not None:
        query = query.gte("posted_at", start.isoformat())
    else:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        query = query.gte("posted_at", cutoff)
    if end is not None:
        query = query.lte("posted_at", end.isoformat())
    response = query.order("posted_at", desc=True).limit(limit).execute()
    return response.data or []


async def get_posts_for_window(
    persona_id: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Fetch all posts within a time window (no limit) — used by the context service."""
    response = (
        _tbl("truth_social_posts")
        .select("*")
        .eq("persona_id", persona_id)
        .gte("posted_at", start.isoformat())
        .lte("posted_at", end.isoformat())
        .order("posted_at", desc=True)
        .execute()
    )
    return response.data or []
