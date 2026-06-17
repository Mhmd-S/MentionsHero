"""Replicate the bulk condition: fire N concurrent grounded Gemini calls and
measure each one's latency / failure. Single calls are fast (~4-11s) but the
bulk backfill (BULK_CONCURRENCY=6) times every call out at 60s — this isolates
whether concurrency is the cause (rate-limit / throttle)."""

import asyncio
import sys
import time

from google import genai

from backend.config import get_settings
from backend.services.metadata_extraction_service import (
    _build_extraction_prompt,
    _extraction_response_schema,
    _call_gemini,
    GEMINI_MODEL,
)


def prompt_for(i: int) -> str:
    return _build_extraction_prompt(
        title=f"President Trump Delivers Remarks, event {i}, Apr. 2026",
        description="Remarks from the East Room of the White House.",
        transcript_excerpt="THE PRESIDENT: Thank you very much...",
        persona_name="Trump",
        det_type=None,
        det_signal=None,
    )


async def one(client, i: int):
    t0 = time.monotonic()
    parsed, usage, diag = await _call_gemini(
        client, prompt_for(i), _extraction_response_schema(),
        label=f"g{i}", grounded=True,
    )
    dt = time.monotonic() - t0
    ok = parsed is not None and not diag.get("error")
    return i, dt, ok, diag.get("error")


async def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    client = genai.Client(api_key=get_settings().gemini_api_key)
    print(f"model={GEMINI_MODEL}  firing {n} concurrent grounded calls...")
    t0 = time.monotonic()
    results = await asyncio.gather(*[one(client, i) for i in range(n)])
    wall = time.monotonic() - t0
    ok = sum(1 for _, _, k, _ in results if k)
    print(f"\nwall={wall:.1f}s  ok={ok}/{n}")
    for i, dt, k, err in sorted(results):
        print(f"  call {i}: {dt:6.1f}s  ok={k}  err={err}")


if __name__ == "__main__":
    asyncio.run(main())
