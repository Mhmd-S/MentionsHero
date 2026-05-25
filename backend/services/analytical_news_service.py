"""News procurement service using DuckDuckGo search."""

import logging
from datetime import datetime, timezone, timedelta

from ddgs import DDGS

from backend.core.database import get_analytical_table

logger = logging.getLogger(__name__)


def _tbl(name: str):
    return get_analytical_table(name)


async def procure_news(
    persona_id: str,
    query: str = "Trump",
    days_back: int = 7,
) -> dict:
    """Fetch Trump news via DuckDuckGo and upsert into analytical.news_items.

    Returns dict with run_id, items_found, items_new, items_skipped.
    """
    # Create procurement run record
    run_resp = _tbl("procurement_runs").insert({
        "source_type": "news_ddgs",
        "persona_id": persona_id,
        "status": "running",
    }).execute()
    run_id = run_resp.data[0]["id"]

    try:
        # Map days_back to ddgs timelimit format
        if days_back <= 1:
            timelimit = "d"
        elif days_back <= 7:
            timelimit = "w"
        else:
            timelimit = "m"

        # Fetch news from DuckDuckGo
        ddgs = DDGS()
        results = list(ddgs.news(query, timelimit=timelimit, max_results=100))

        items_found = len(results)
        items_new = 0
        items_skipped = 0
        details: list[dict] = []

        for item in results:
            url = item.get("url", "")
            if not url:
                items_skipped += 1
                continue

            # Parse published date
            published_at = _parse_ddgs_date(item.get("date"))
            if not published_at:
                published_at = datetime.now(timezone.utc)

            # Extract source domain from URL
            source_domain = _extract_domain(url)

            row = {
                "persona_id": persona_id,
                "title": item.get("title", "")[:500],
                "body": item.get("body", "")[:2000],
                "url": url,
                "source_name": item.get("source", source_domain),
                "source_domain": source_domain,
                "published_at": published_at.isoformat(),
                "procurement_source": "ddgs",
                "raw_payload": item,
            }

            try:
                _tbl("news_items").upsert(
                    row, on_conflict="persona_id,url"
                ).execute()
                items_new += 1
                details.append({"url": url, "title": row["title"], "action": "upserted"})
            except Exception as e:
                items_skipped += 1
                details.append({"url": url, "action": "error", "error": str(e)})

        # Complete the run
        _tbl("procurement_runs").update({
            "status": "completed",
            "items_found": items_found,
            "items_new": items_new,
            "items_skipped": items_skipped,
            "details": details,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()

        logger.info(
            "News procurement: found=%d, new=%d, skipped=%d",
            items_found, items_new, items_skipped,
        )

        return {
            "run_id": run_id,
            "items_found": items_found,
            "items_new": items_new,
            "items_skipped": items_skipped,
        }

    except Exception as e:
        logger.error("News procurement failed: %s", e, exc_info=True)
        _tbl("procurement_runs").update({
            "status": "failed",
            "error_message": str(e),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
        return {
            "run_id": run_id,
            "items_found": 0,
            "items_new": 0,
            "items_skipped": 0,
        }


async def get_news_items(
    persona_id: str,
    days: int = 7,
    limit: int = 100,
) -> list[dict]:
    """Get news items from the database."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    response = (
        _tbl("news_items")
        .select("*")
        .eq("persona_id", persona_id)
        .gte("published_at", cutoff)
        .order("published_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


async def get_news_for_window(
    persona_id: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Fetch news items within a time window (for context window computation)."""
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ddgs_date(date_str: str | None) -> datetime | None:
    """Parse date string from ddgs results."""
    if not date_str:
        return None
    try:
        # ddgs returns ISO-ish dates like "2026-03-29T12:00:00+00:00"
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        pass
    try:
        # Fallback: common format "Mon, 29 Mar 2026 12:00:00 GMT"
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def _extract_domain(url: str) -> str | None:
    """Extract domain from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.removeprefix("www.")
    except Exception:
        return None
