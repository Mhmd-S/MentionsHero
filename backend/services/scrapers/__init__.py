"""Modular procurement scrapers.

Each analytical source implements :class:`BaseScraper` and is registered in
``SCRAPERS`` keyed by its ``source_type`` (which matches the
``analytical.procurement_runs.source_type`` CHECK). Adding a new outlet/source
is one new module + one entry here.
"""

from backend.services.scrapers.base import BaseScraper, ScrapedItem
from backend.services.scrapers.fox_news import FoxNewsScraper
from backend.services.scrapers.truth_social import TruthSocialScraper

SCRAPERS: dict[str, type[BaseScraper]] = {
    TruthSocialScraper.source_type: TruthSocialScraper,
    FoxNewsScraper.source_type: FoxNewsScraper,
}


def get_scraper(source_type: str) -> BaseScraper:
    """Instantiate the scraper for ``source_type`` (raises on unknown)."""
    cls = SCRAPERS.get(source_type)
    if cls is None:
        raise ValueError(
            f"Unknown source_type '{source_type}'. Known: {sorted(SCRAPERS)}"
        )
    return cls()


def known_source_types() -> list[str]:
    return sorted(SCRAPERS)


__all__ = [
    "BaseScraper",
    "ScrapedItem",
    "SCRAPERS",
    "get_scraper",
    "known_source_types",
    "TruthSocialScraper",
    "FoxNewsScraper",
]
