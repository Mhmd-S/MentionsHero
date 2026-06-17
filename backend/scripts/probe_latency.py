"""Measure actual Gemini call latency right now — grounded vs ungrounded —
to see why every grounded extraction is timing out at 60s."""

import asyncio
import time

from google import genai

from backend.config import get_settings
from backend.services.metadata_extraction_service import (
    _build_extraction_prompt,
    _extraction_response_schema,
    _call_gemini,
    GEMINI_MODEL,
)

PROMPT = _build_extraction_prompt(
    title="President Trump Delivers Remarks on the Economy, Apr. 25, 2026",
    description="The President delivers remarks from the East Room of the White House.",
    transcript_excerpt="THE PRESIDENT: Thank you very much. It's great to be here in the East Room...",
    persona_name="Trump",
    det_type=None,
    det_signal=None,
)


async def timed(label: str, grounded: bool):
    client = genai.Client(api_key=get_settings().gemini_api_key)
    t0 = time.monotonic()
    parsed, usage, diag = await _call_gemini(
        client, PROMPT, _extraction_response_schema(), label=label, grounded=grounded,
    )
    dt = time.monotonic() - t0
    ok = parsed is not None and not diag.get("error")
    print(f"[{label:<10} grounded={grounded!s:<5}] {dt:6.1f}s  ok={ok}  "
          f"err={diag.get('error')}  finish={diag.get('finish_reason')}  "
          f"grounding={diag.get('grounding')}  usage={usage}")
    return dt


async def main():
    print(f"model={GEMINI_MODEL}")
    # Run a couple of each, sequentially, to measure clean per-call latency.
    await timed("ungrounded", grounded=False)
    await timed("grounded-1", grounded=True)
    await timed("grounded-2", grounded=True)


if __name__ == "__main__":
    asyncio.run(main())
