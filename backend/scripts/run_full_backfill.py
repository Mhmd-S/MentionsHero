"""Babysat full metadata backfill for the Trump persona.

force=False → processes the full transcript pool but SKIPS any admin-confirmed
(classification_source='manual') rows, so we never clobber confirmed metadata.
INFO logging is on so the background log shows the run_id, per-item progress,
and any retry / cooldown activity.
"""

import asyncio
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
# Quiet the noisy HTTP client; we only want the backfill's own progress lines.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)

from backend.services import metadata_extraction_service as m

PID = "3c1fe5c4-ff15-474b-9420-b0cb0176a94b"  # Trump persona


async def main():
    print(">>> full backfill starting (force=False)", flush=True)
    res = await m.bulk_backfill_metadata(persona_id=PID, force=False)
    print(f">>> DONE: {res}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
