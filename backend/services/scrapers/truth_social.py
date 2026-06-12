"""Truth Social scraper — real @realDonaldTrump posts via the public Mastodon API.

Truth Social is a Mastodon fork. The account-statuses endpoint is publicly
readable; the only gate is Cloudflare TLS fingerprinting, which ``curl_cffi``'s
Chrome impersonation defeats — so **no account/credentials are required**
(verified credential-free). We page the timeline newest-first via the Mastodon
``max_id`` cursor and stop once we cross the requested ``start`` bound.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from backend.services.scrapers.base import BaseScraper, ScrapedItem

logger = logging.getLogger(__name__)


class TruthSocialScraper(BaseScraper):
    source_type = "truth_social"
    kind = "truth_social"

    API_BASE = "https://truthsocial.com/api/v1"
    USER_AGENT = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    )
    IMPERSONATE = "chrome"
    PAGE_LIMIT = 20          # the server silently caps page size at ~20
    REQUEST_DELAY = 1.0      # seconds between pages — Cloudflare rate-limit safety
    MAX_PAGES = 2000         # hard backstop (~40k posts) so a bug can't loop forever

    # Persona → Truth Social handle. Extend as more personas get accounts.
    DEFAULT_HANDLE = "realDonaldTrump"
    HANDLE_BY_KEYWORD = {"trump": "realDonaldTrump"}

    # ------------------------------------------------------------------
    def _resolve_handle(self, persona: dict) -> str:
        name = (persona.get("name") or "").lower()
        slug = (persona.get("slug") or "").lower()
        for keyword, handle in self.HANDLE_BY_KEYWORD.items():
            if keyword in name or keyword in slug:
                return handle
        return self.DEFAULT_HANDLE

    def _session(self):
        from curl_cffi import requests  # lazy: heavy native import
        return requests.Session()

    def _get(self, session, path: str, params: dict | None = None):
        resp = session.get(
            self.API_BASE + path,
            params=params,
            impersonate=self.IMPERSONATE,
            headers={"User-Agent": self.USER_AGENT},
            timeout=30,
        )
        try:
            return resp.json()
        except json.JSONDecodeError:
            body = resp.text or ""
            if "Just a moment" in body or "challenge-platform" in body:
                raise RuntimeError(
                    "Truth Social returned a Cloudflare challenge instead of JSON "
                    "(source IP likely flagged — retry later or via a different network)."
                )
            raise RuntimeError(f"Truth Social returned non-JSON ({resp.status_code}).")

    def _lookup_account_id(self, session, handle: str) -> str | None:
        data = self._get(session, "/accounts/lookup", {"acct": handle})
        return (data or {}).get("id")

    # ------------------------------------------------------------------
    async def scrape(
        self,
        *,
        persona: dict,
        start: datetime,
        end: datetime,
        is_cancelled: Callable[[], bool],
    ) -> AsyncIterator[ScrapedItem]:
        handle = self._resolve_handle(persona)
        session = self._session()
        account_id = await asyncio.to_thread(self._lookup_account_id, session, handle)
        if not account_id:
            raise RuntimeError(f"Truth Social account not found for handle '{handle}'.")

        logger.info("Truth Social scrape: @%s (id=%s) %s → %s", handle, account_id, start, end)

        max_id: str | None = None
        for _ in range(self.MAX_PAGES):
            if is_cancelled():
                return

            params: dict = {"limit": self.PAGE_LIMIT}
            if max_id:
                params["max_id"] = max_id
            page = await asyncio.to_thread(
                self._get, session, f"/accounts/{account_id}/statuses", params
            )
            if not page or not isinstance(page, list):
                return

            page.sort(key=lambda p: int(p["id"]), reverse=True)  # newest first
            max_id = page[-1]["id"]  # next page = older than the oldest here

            for post in page:
                posted_at = _parse_iso(post.get("created_at"))
                if posted_at is None:
                    continue
                if posted_at <= start:
                    return  # reverse-chronological: nothing older matters
                if posted_at > end:
                    continue  # newer than the window — keep paging back
                yield self._to_item(post, posted_at)

            if len(page) < self.PAGE_LIMIT:
                return  # last page
            await asyncio.sleep(self.REQUEST_DELAY)

    # ------------------------------------------------------------------
    def _to_item(self, post: dict, posted_at: datetime) -> ScrapedItem:
        reblog = post.get("reblog")
        is_retruth = bool(reblog)
        content = _html_to_text(post.get("content") or "")
        if is_retruth and not content:
            content = _html_to_text((reblog or {}).get("content") or "")

        media_urls = [
            m.get("url")
            for m in (post.get("media_attachments") or [])
            if m.get("url")
        ]
        engagement = {
            "replies": post.get("replies_count"),
            "reblogs": post.get("reblogs_count"),
            "favourites": post.get("favourites_count"),
            "upvotes": post.get("upvotes_count"),
            "downvotes": post.get("downvotes_count"),
        }
        post_id = str(post["id"])
        row = {
            "external_id": post_id,
            "content": content[:5000],
            "post_url": post.get("url"),
            "posted_at": posted_at.isoformat(),
            "source": "truthsocial",
            "media_urls": media_urls,
            "engagement": engagement,
            "is_retruth": is_retruth,
            "raw_payload": post,
        }
        label = (content[:80].strip() or post.get("url") or post_id)
        return ScrapedItem(
            table="truth_social_posts",
            key_column="external_id",
            key_value=post_id,
            row=row,
            timestamp=posted_at,
            label=("🔁 " + label if is_retruth else label),
        )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
