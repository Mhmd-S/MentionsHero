"""Fox News scraper — articles via Fox's dated HTML sitemap.

Fox exposes a complete day-by-day sitemap (no auth, no key, robots-permitted):
``/html-sitemap/{year}/{month_name}/{day}`` lists every article published that
day across all sections. We crawl each day in the window, keyword-filter links
to the persona (across all sections, not just /politics/), then fetch each
article and extract its body with ``trafilatura``.

This is the only free route that reliably reaches back to January — GDELT's
article-list mode only covers the last ~3 months. New outlets can be added as
sibling scrapers without touching this one.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator, Callable
from datetime import date, datetime, timedelta, timezone

from bs4 import BeautifulSoup

from backend.services.scrapers.base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)

_MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]

# Real Fox article permalinks look like /<section>/<slug-with-hyphens>.
# Excludes /category/ index pages and /html-sitemap/ navigation.
_SECTIONS = (
    "politics|us|world|opinion|media|entertainment|sports|health|science|tech|"
    "lifestyle|travel|food-drink|family|auto|real-estate|video"
)
_ARTICLE_RE = re.compile(
    r"^https?://www\.foxnews\.com/(?:" + _SECTIONS + r")/[a-z0-9][a-z0-9\-]+$"
)


class FoxNewsScraper(BaseScraper):
    source_type = "news_fox"
    kind = "news"

    BASE = "https://www.foxnews.com"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    )
    REQUEST_DELAY = 0.4      # seconds between article fetches — be polite

    # ------------------------------------------------------------------
    def _persona_keywords(self, persona: dict) -> list[str]:
        keywords: set[str] = set()
        name = (persona.get("name") or "").strip()
        if name:
            keywords.add(name.lower())
            for token in name.split():
                if len(token) > 2:
                    keywords.add(token.lower())
        for alias in persona.get("aliases", []) or []:
            alias = str(alias).strip().lower()
            if alias:
                keywords.add(alias)
        return [k for k in keywords if k]

    # ------------------------------------------------------------------
    async def scrape(
        self,
        *,
        persona: dict,
        start: datetime,
        end: datetime,
        is_cancelled: Callable[[], bool],
    ) -> AsyncIterator[ScrapedItem]:
        import httpx

        keywords = self._persona_keywords(persona)
        if not keywords:
            raise RuntimeError("Persona has no name/aliases to filter Fox articles by.")

        logger.info(
            "Fox scrape: %s → %s, keywords=%s",
            start.date(), end.date(), keywords,
        )

        async with httpx.AsyncClient(
            headers={"User-Agent": self.USER_AGENT},
            follow_redirects=True,
            timeout=30,
        ) as client:
            for day in _iter_days(start.date(), end.date()):
                if is_cancelled():
                    return

                day_url = f"{self.BASE}/html-sitemap/{day.year}/{_MONTHS[day.month - 1]}/{day.day}"
                links = await self._day_links(client, day_url)

                seen: set[str] = set()
                for url, anchor in links:
                    if url in seen:
                        continue
                    haystack = (url + " " + anchor).lower()
                    if not any(k in haystack for k in keywords):
                        continue
                    seen.add(url)

                    if is_cancelled():
                        return
                    item = await self._article_item(client, url, anchor, day)
                    if item is not None:
                        yield item
                    await asyncio.sleep(self.REQUEST_DELAY)

    # ------------------------------------------------------------------
    async def _day_links(self, client, day_url: str) -> list[tuple[str, str]]:
        try:
            resp = await client.get(day_url)
        except Exception as e:
            logger.warning("Fox sitemap fetch failed (%s): %s", day_url, e)
            return []
        if resp.status_code != 200:
            logger.debug("Fox sitemap %s → %s", day_url, resp.status_code)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        out: list[tuple[str, str]] = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            url = href if href.startswith("http") else self.BASE + href
            if "/category/" in url or "/html-sitemap" in url:
                continue
            if _ARTICLE_RE.match(url):
                out.append((url, a.get_text(" ", strip=True)))
        return out

    async def _article_item(
        self, client, url: str, anchor: str, day: date
    ) -> ScrapedItem | None:
        import trafilatura

        try:
            resp = await client.get(url)
        except Exception as e:
            logger.debug("Fox article fetch failed (%s): %s", url, e)
            return None
        if resp.status_code != 200:
            return None

        html = resp.text
        body = trafilatura.extract(html, include_comments=False, favor_recall=True) or ""
        title = anchor
        published_at = datetime(day.year, day.month, day.day, 12, 0, tzinfo=timezone.utc)
        try:
            meta = trafilatura.extract_metadata(html)
            if meta is not None:
                if getattr(meta, "title", None):
                    title = meta.title
                parsed_date = _parse_meta_date(getattr(meta, "date", None))
                if parsed_date is not None:
                    published_at = parsed_date
        except Exception:
            pass

        row = {
            "title": (title or "")[:500],
            "body": body[:5000],
            "url": url,
            "source_name": "Fox News",
            "source_domain": "foxnews.com",
            "published_at": published_at.isoformat(),
            "procurement_source": "fox_sitemap",
            "topics": [],
            "raw_payload": {"anchor_text": anchor, "sitemap_day": day.isoformat()},
        }
        return ScrapedItem(
            table="news_items",
            key_column="url",
            key_value=url,
            row=row,
            timestamp=published_at,
            label=(title or url)[:80],
        )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _iter_days(start: date, end: date):
    """Yield each date in [start, end] inclusive (oldest → newest)."""
    if end < start:
        return
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def _parse_meta_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        try:
            dt = datetime.strptime(value[:10], "%Y-%m-%d")
        except (ValueError, TypeError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(hour=12, tzinfo=timezone.utc)
    return dt
