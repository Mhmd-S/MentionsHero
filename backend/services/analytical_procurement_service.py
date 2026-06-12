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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def start_run(source_type: str, persona_id: str) -> str:
    """Validate the source, create a ``procurement_runs`` row and return its id.

    Raises ``ValueError`` for an unknown source_type so the caller can 400.
    """
    get_scraper(source_type)  # validates source_type early
    run_resp = _tbl("procurement_runs").insert({
        "source_type": source_type,
        "persona_id": persona_id,
        "status": "running",
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
    cancelled = False
    buffer: list[ScrapedItem] = []

    async def _flush() -> None:
        nonlocal items_found, items_new
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

        existing = await asyncio.to_thread(
            _existing_keys, table, key_column, persona_id, keys
        )
        new_count = sum(1 for k in keys if k not in existing)
        await asyncio.to_thread(_bulk_upsert, table, key_column, rows)

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
        _tbl("procurement_runs").update({
            "status": status,
            "items_found": items_found,
            "items_new": items_new,
            "items_skipped": items_found - items_new,
            "current_item_index": None,
            "current_item_name": None,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", run_id).execute()

        logger.info(
            "scrape run %s (%s): %s found=%d new=%d",
            run_id, source_type, status, items_found, items_new,
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
        try:
            _tbl("procurement_runs").update({
                "status": "failed",
                "error_message": str(e)[:1000],
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


async def run_scrape(
    source_type: str,
    persona_id: str,
    start: datetime,
    end: datetime | None = None,
) -> dict:
    """Create a run and execute it synchronously (scheduler + /scrape-sync)."""
    run_id = await start_run(source_type, persona_id)
    return await execute_run(run_id, source_type, persona_id, start, end)
