"""Truth Social post procurement service using DuckDuckGo search as proxy."""

import hashlib
import logging
from datetime import datetime, timezone, timedelta

from ddgs import DDGS

from backend.core.database import get_analytical_table

logger = logging.getLogger(__name__)


def _tbl(name: str):
    return get_analytical_table(name)


async def procure_truth_social_posts(
    persona_id: str,
    days_back: int = 3,
) -> dict:
    """Search for Trump Truth Social posts via DuckDuckGo and store them.

    Uses news coverage of Truth Social posts as a proxy since there is no
    official Truth Social API. Captures the posts that made headlines.
    """
    # Create procurement run record
    run_resp = _tbl("procurement_runs").insert({
        "source_type": "truth_social",
        "persona_id": persona_id,
        "status": "running",
    }).execute()
    run_id = run_resp.data[0]["id"]

    try:
        if days_back <= 1:
            timelimit = "d"
        elif days_back <= 7:
            timelimit = "w"
        else:
            timelimit = "m"

        ddgs = DDGS()

        # Search for Truth Social posts reported in the news
        queries = [
            "Trump Truth Social post",
            "Trump posted on Truth Social",
        ]

        all_results: list[dict] = []
        seen_urls: set[str] = set()

        for query in queries:
            try:
                results = list(ddgs.news(query, timelimit=timelimit, max_results=50))
                for r in results:
                    url = r.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(r)
            except Exception as e:
                logger.warning("Truth Social query '%s' failed: %s", query, e)

        items_found = len(all_results)
        items_new = 0
        items_skipped = 0
        details: list[dict] = []

        for item in all_results:
            url = item.get("url", "")
            if not url:
                items_skipped += 1
                continue

            # Generate a stable external_id from URL
            external_id = hashlib.sha256(url.encode()).hexdigest()[:32]

            posted_at = _parse_ddgs_date(item.get("date"))
            if not posted_at:
                posted_at = datetime.now(timezone.utc)

            # The "content" is the news snippet about the post
            content = item.get("body", item.get("title", ""))

            row = {
                "persona_id": persona_id,
                "external_id": external_id,
                "content": content[:5000],
                "post_url": url,
                "posted_at": posted_at.isoformat(),
                "source": "ddgs",
                "raw_payload": item,
            }

            try:
                _tbl("truth_social_posts").upsert(
                    row, on_conflict="persona_id,external_id"
                ).execute()
                items_new += 1
                details.append({"url": url, "action": "upserted"})
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
            "Truth Social procurement: found=%d, new=%d, skipped=%d",
            items_found, items_new, items_skipped,
        )

        return {
            "run_id": run_id,
            "items_found": items_found,
            "items_new": items_new,
            "items_skipped": items_skipped,
        }

    except Exception as e:
        logger.error("Truth Social procurement failed: %s", e, exc_info=True)
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


async def get_posts(
    persona_id: str,
    days: int = 7,
    limit: int = 100,
) -> list[dict]:
    """Get Truth Social posts from the database."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    response = (
        _tbl("truth_social_posts")
        .select("*")
        .eq("persona_id", persona_id)
        .gte("posted_at", cutoff)
        .order("posted_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


async def get_posts_for_window(
    persona_id: str,
    start: datetime,
    end: datetime,
) -> list[dict]:
    """Fetch posts within a time window."""
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_ddgs_date(date_str: str | None) -> datetime | None:
    """Parse date string from ddgs results."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except (ValueError, TypeError):
        pass
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except Exception:
        return None
