"""CLI wrapper around metadata_extraction_service.bulk_backfill_metadata.

Identical behavior to the `POST /api/analytical/metadata/backfill/{persona_id}`
endpoint — same service function under the hood. Use the CLI for one-off ops;
prefer the endpoint (and the persona-page button) for routine runs.

Usage:
  python3 -m backend.scripts.backfill_metadata                   # default persona (Trump)
  python3 -m backend.scripts.backfill_metadata --persona-id <uuid>
  python3 -m backend.scripts.backfill_metadata --limit 5         # smoke test
  python3 -m backend.scripts.backfill_metadata --force           # include manual rows

Records progress in `analytical.procurement_runs` (source_type=metadata_backfill).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.core.database import get_supabase
from backend.services.metadata_extraction_service import bulk_backfill_metadata

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _default_persona_id() -> str | None:
    """Look up the Trump persona by name (mirrors backend default)."""
    supabase = get_supabase()
    resp = (
        supabase.table("personas")
        .select("id, name")
        .ilike("name", "%trump%")
        .limit(1)
        .execute()
    )
    return resp.data[0]["id"] if resp.data else None


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--persona-id", default=None,
                        help="Persona UUID. Defaults to the Trump persona.")
    parser.add_argument("--force", action="store_true",
                        help="Re-run extraction even on rows with classification_source='manual'")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only process the first N candidates (for smoke testing)")
    args = parser.parse_args()

    persona_id = args.persona_id or _default_persona_id()
    if not persona_id:
        print("No persona ID provided and no Trump persona found in DB", file=sys.stderr)
        sys.exit(1)

    print(f"Backfilling persona {persona_id} (force={args.force}, limit={args.limit})...\n")
    result = await bulk_backfill_metadata(
        persona_id=persona_id, force=args.force, limit=args.limit,
    )
    print(
        f"\nDone. run_id={result['run_id']} "
        f"candidates={result['candidates']} "
        f"succeeded={result['succeeded']} "
        f"failed={result['failed']}"
    )


if __name__ == "__main__":
    asyncio.run(main())
