"""Base types for modular procurement scrapers.

Each analytical data source (Truth Social posts, Fox News articles, …) is one
``BaseScraper`` implementation that yields normalized ``ScrapedItem`` objects for
a requested ``[start, end]`` window. The orchestrator
(``analytical_procurement_service``) owns the ``procurement_runs`` lifecycle —
upserts, dedup counting, progress heartbeat and cancellation — so scrapers stay
small and only concern themselves with fetching + normalizing.

Adding a new source = one new module here + one line in ``__init__.SCRAPERS``.
"""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ScrapedItem:
    """One normalized record ready to upsert into an analytical table.

    ``key_column``/``key_value`` identify the row uniquely *within a persona*
    (the analytical tables are deduped on ``(persona_id, <key_column>)``). The
    orchestrator injects ``persona_id`` and builds the ``on_conflict`` clause
    from ``key_column``, so the scraper never touches the DB.
    """

    table: str               # "truth_social_posts" | "news_items"
    key_column: str          # unique column within a persona: "external_id" | "url"
    key_value: str           # value of key_column for this item
    row: dict                # full row to upsert (persona_id added by the runner)
    timestamp: datetime      # posted_at / published_at — ordering + progress
    label: str = ""          # short human label for the live progress cursor


class BaseScraper(abc.ABC):
    """A procurement source.

    Implementations set ``source_type`` (matching the
    ``analytical.procurement_runs.source_type`` CHECK) and implement
    :meth:`scrape` as an async generator.
    """

    source_type: str = ""    # e.g. "truth_social", "news_fox"
    kind: str = ""           # "truth_social" | "news" (informational)

    @abc.abstractmethod
    def scrape(
        self,
        *,
        persona: dict,
        start: datetime,
        end: datetime,
        is_cancelled: Callable[[], bool],
    ) -> AsyncIterator[ScrapedItem]:
        """Yield items posted/published within ``[start, end]`` (UTC-aware).

        Should call ``is_cancelled()`` periodically and stop promptly when it
        returns ``True``. Implementations are async generators.
        """
        raise NotImplementedError
