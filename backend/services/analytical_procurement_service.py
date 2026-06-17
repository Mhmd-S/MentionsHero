"""Orchestrates scraper runs against the ``procurement_runs`` audit log.

A single entry point (:func:`run_scrape`, split into :func:`start_run` +
:func:`execute_run` so a real ``run_id`` can be returned before background
work begins) drives any registered scraper:

* creates the ``procurement_runs`` row,
* streams ``ScrapedItem``s in chunks, upserting in bulk,
* counts **true** inserts vs updates (fixes the old over-count),
* writes a live progress heartbeat (``current_item_index/name``) and polls
  ``cancel_requested`` between chunks — so scrape runs get the same Operations
  dashboard observability and cancel support that metadata runs already have.
"""

import asyncio
import logging
from datetime import datetime, timezone

from backend.core.database import get_analytical_table, get_supabase
from backend.services.scrapers import ScrapedItem, get_scraper

logger = logging.getLogger(__name__)

CHUNK_SIZE = 50  # items buffered before each bulk select+upsert / heartbeat


def _tbl(name: str):
    return get_analytical_table(name)


# ---------------------------------------------------------------------------
# Persona loading
# ---------------------------------------------------------------------------

def _load_persona_sync(persona_id: str) -> dict:
    resp = (
        get_supabase()
        .table("personas")
        .select("id, name, slug")
        .eq("id", persona_id)
        .single()
        .execute()
    )
    persona = resp.data or {}
    if not persona:
        raise ValueError(f"Persona '{persona_id}' not found")
    try:
        aliases = (
            get_supabase()
            .table("persona_aliases")
            .select("alias")
            .eq("persona_id", persona_id)
            .execute()
        )
        persona["aliases"] = [r["alias"] for r in (aliases.data or []) if r.get("alias")]
    except Exception:
        persona["aliases"] = []
    return persona


# ---------------------------------------------------------------------------
# DB write helpers (sync PostgREST → called via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _existing_keys(table: str, key_column: str, persona_id: str, keys: list[str]) -> set[str]:
    if not keys:
        return set()
    resp = (
        _tbl(table)
        .select(key_column)
        .eq("persona_id", persona_id)
        .in_(key_column, keys)
        .execute()
    )
    return {row[key_column] for row in (resp.data or [])}


def _bulk_upsert(table: str, key_column: str, rows: list[dict]) -> None:
    _tbl(table).upsert(rows, on_conflict=f"persona_id,{key_column}").execute()


def _heartbeat(run_id: str, found: int, new: int, label: str) -> None:
    try:
        _tbl("procurement_runs").update({
            "items_found": found,
            "items_new": new,
            "items_skipped": found - new,
            "current_item_index": found,
            "current_item_name": (label or "")[:200],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()
    except Exception as e:
        logger.debug("heartbeat failed for run %s: %s", run_id, e)


def _is_cancel_requested(run_id: str) -> bool:
    try:
        resp = (
            _tbl("procurement_runs")
            .select("cancel_requested")
            .eq("id", run_id)
            .single()
            .execute()
        )
        return bool((resp.data or {}).get("cancel_requested"))
    except Exception:
        return False


async def _retry_to_thread(fn, *args, attempts: int = 3, base_delay: float = 1.0, label: str = "db"):
    """Run a sync DB call in a thread, retrying transient failures with
    exponential backoff. The upserts are idempotent (on_conflict), so a retry
    can never double-insert — making a failed chunk recoverable instead of
    fatal to the whole run."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await asyncio.to_thread(fn, *args)
        except Exception as e:  # noqa: BLE001 — transient network/DB; retry then re-raise
            last = e
            if i == attempts - 1:
                raise
            logger.warning("%s failed (attempt %d/%d), retrying: %s", label, i + 1, attempts, e)
            await asyncio.sleep(base_delay * (2 ** i))
    raise last  # pragma: no cover


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def start_run(
    source_type: str,
    persona_id: str,
    params: dict | None = None,
    retry_of: str | None = None,
    attempt: int = 1,
) -> str:
    """Validate the source, create a ``procurement_runs`` row and return its id.

    ``params`` (e.g. the scrape date window) is persisted so the run can be
    re-launched from the Operations dashboard; ``retry_of``/``attempt`` record
    the retry lineage. Raises ``ValueError`` for an unknown source_type so the
    caller can 400.
    """
    get_scraper(source_type)  # validates source_type early
    run_resp = _tbl("procurement_runs").insert({
        "source_type": source_type,
        "persona_id": persona_id,
        "status": "running",
        "params": params or {},
        "retry_of": retry_of,
        "attempt": attempt,
    }).execute()
    return run_resp.data[0]["id"]


async def execute_run(
    run_id: str,
    source_type: str,
    persona_id: str,
    start: datetime,
    end: datetime | None = None,
) -> dict:
    """Run the scraper for an already-created ``run_id`` to completion."""
    end = end or datetime.now(timezone.utc)
    scraper = get_scraper(source_type)

    items_found = 0
    items_new = 0
    items_dropped = 0  # items seen but not persisted (chunk failed after retries)
    cancelled = False
    buffer: list[ScrapedItem] = []
    # Non-fatal problems surfaced into procurement_runs.details so the dashboard
    # can show *what* went wrong even on a run that otherwise completes.
    errors: list[dict] = []

    async def _flush() -> None:
        nonlocal items_found, items_new, items_dropped
        if not buffer:
            return
        # Dedup within the chunk (PostgREST rejects two conflicting rows in one
        # upsert) — keep the latest occurrence of each key.
        by_key: dict[str, ScrapedItem] = {}
        for it in buffer:
            by_key[it.key_value] = it
        items = list(by_key.values())
        table = items[0].table
        key_column = items[0].key_column
        keys = [it.key_value for it in items]
        rows = []
        for it in items:
            row = dict(it.row)
            row["persona_id"] = persona_id
            rows.append(row)

        try:
            existing = await _retry_to_thread(
                _existing_keys, table, key_column, persona_id, keys, label="existing_keys"
            )
            new_count = sum(1 for k in keys if k not in existing)
            await _retry_to_thread(_bulk_upsert, table, key_column, rows, label="bulk_upsert")
        except Exception as e:  # noqa: BLE001 — chunk lost; record + keep going
            items_dropped += len(items)
            errors.append({
                "action": "chunk_failed",
                "error": f"{type(e).__name__}: {e}"[:500],
                "chunk_size": len(items),
                "label": (items[-1].label or "")[:120],
            })
            logger.error("scrape run %s: chunk of %d dropped: %s", run_id, len(items), e)
            buffer.clear()
            return

        items_found += len(items)
        items_new += new_count
        label = items[-1].label
        await asyncio.to_thread(_heartbeat, run_id, items_found, items_new, label)
        buffer.clear()

    try:
        persona = await asyncio.to_thread(_load_persona_sync, persona_id)

        async for item in scraper.scrape(
            persona=persona,
            start=start,
            end=end,
            is_cancelled=lambda: cancelled,
        ):
            buffer.append(item)
            if len(buffer) >= CHUNK_SIZE:
                await _flush()
                if await asyncio.to_thread(_is_cancel_requested, run_id):
                    cancelled = True
                    break

        if not cancelled:
            await _flush()

        status = "cancelled" if cancelled else "completed"
        # A run that finished but dropped chunks is still "completed" (we don't
        # fail the whole window for a transient blip) — but the dropped count +
        # per-chunk errors land in details so the dashboard flags it.
        _tbl("procurement_runs").update({
            "status": status,
            "items_found": items_found,
            "items_new": items_new,
            "items_skipped": items_found - items_new,
            "current_item_index": None,
            "current_item_name": None,
            "details": errors,
            "error_message": (
                f"{items_dropped} item(s) dropped after retries — see details"
                if items_dropped else None
            ),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()

        logger.info(
            "scrape run %s (%s): %s found=%d new=%d dropped=%d",
            run_id, source_type, status, items_found, items_new, items_dropped,
        )
        return {
            "run_id": run_id,
            "status": status,
            "items_found": items_found,
            "items_new": items_new,
            "items_skipped": items_found - items_new,
        }

    except Exception as e:
        logger.error("scrape run %s (%s) failed: %s", run_id, source_type, e, exc_info=True)
        # Record the structured failure (exception type + message + how far we
        # got) so the dashboard shows why it died, not just a red badge.
        errors.append({
            "action": "scrape_failed",
            "error": f"{type(e).__name__}: {e}"[:1000],
            "items_found_before_failure": items_found,
            "items_new_before_failure": items_new,
        })
        try:
            _tbl("procurement_runs").update({
                "status": "failed",
                "error_message": f"{type(e).__name__}: {e}"[:1000],
                "items_found": items_found,
                "items_new": items_new,
                "items_skipped": items_found - items_new,
                "details": errors,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", run_id).execute()
        except Exception:
            pass
        return {
            "run_id": run_id,
            "status": "failed",
            "items_found": items_found,
            "items_new": items_new,
            "items_skipped": 0,
        }


def scrape_params(start: datetime, end: datetime | None) -> dict:
    """Serialize a scrape window into the ``params`` blob stored on the run, so
    a Retry can replay the exact same window."""
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat() if end else None,
    }


async def run_scrape(
    source_type: str,
    persona_id: str,
    start: datetime,
    end: datetime | None = None,
    retry_of: str | None = None,
    attempt: int = 1,
) -> dict:
    """Create a run and execute it synchronously (scheduler + /scrape-sync)."""
    run_id = await start_run(
        source_type, persona_id,
        params=scrape_params(start, end),
        retry_of=retry_of, attempt=attempt,
    )
    return await execute_run(run_id, source_type, persona_id, start, end)
