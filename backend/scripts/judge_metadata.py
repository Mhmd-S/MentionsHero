"""LLM-as-judge consistency check for extracted venue/location.

Venue/city have no cheap ground truth, so this samples real transcripts, runs
the NEW grounded extractor, then asks a SEPARATE grounded Gemini judge whether
the extracted location/venue is supported by the transcript + a fresh web
search. Aggregates a supported / unsupported / insufficient-evidence rate.

Run from repo root:
    python3 -m backend.scripts.judge_metadata --limit 20
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from google import genai
from google.genai import types

from backend.config import get_settings
from backend.core.database import get_supabase
from backend.services.metadata_extraction_service import (
    BULK_CONCURRENCY,
    GEMINI_MODEL,
    extract_metadata,
)

_VERDICTS = ["supported", "unsupported", "insufficient_evidence"]


def _judge_schema() -> types.Schema:
    return types.Schema(
        type=types.Type.OBJECT,
        properties={
            "venue_verdict": types.Schema(type=types.Type.STRING, enum=_VERDICTS),
            "location_verdict": types.Schema(type=types.Type.STRING, enum=_VERDICTS),
            "reason": types.Schema(type=types.Type.STRING),
        },
        required=["venue_verdict", "location_verdict", "reason"],
    )


def _judge_prompt(title, city, state, venue, excerpt) -> str:
    return f"""You are an impartial fact-checker. Using Google Search and the transcript excerpt, \
decide whether the EXTRACTED location/venue for this event is supported.

EVENT TITLE: {title}
EXTRACTED city/state: {city} / {state}
EXTRACTED venue: {venue}

TRANSCRIPT EXCERPT:
{excerpt[:1200]}

For venue_verdict and location_verdict return one of: supported (evidence agrees),
unsupported (evidence contradicts), insufficient_evidence (can't tell). Give a one-line reason."""


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona-id", default=None)
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    supabase = get_supabase()
    if args.persona_id:
        prow = supabase.table("personas").select("id, name").eq("id", args.persona_id).single().execute().data
    else:
        prow = (supabase.table("personas").select("id, name").ilike("name", "%trump%").limit(1).execute().data or [None])[0]
    if not prow:
        raise SystemExit("no persona; pass --persona-id")
    pid, pname = prow["id"], prow.get("name") or ""
    aliases = [a["alias"] for a in (supabase.table("persona_aliases").select("alias").eq("persona_id", pid).execute().data or []) if a.get("alias")]
    if pname and pname not in aliases:
        aliases.append(pname)

    from backend.services.metadata_extraction_service import _persona_transcript_pool
    pool = _persona_transcript_pool(pid, aliases)
    random.shuffle(pool)
    sample = pool[: args.limit]
    print(f"judging {len(sample)} of {len(pool)}")

    client = genai.Client(api_key=get_settings().gemini_api_key)
    sem = asyncio.Semaphore(BULK_CONCURRENCY)
    venue_v, loc_v = Counter(), Counter()
    loop = asyncio.get_event_loop()

    async def _one(t: dict) -> None:
        async with sem:
            title = t.get("name") or ""
            excerpt = t.get("transcript") or ""
            ext = await extract_metadata(title=title, description="", transcript_text=excerpt)
            if not ext.get("venue") and not ext.get("city"):
                venue_v["insufficient_evidence"] += 1
                loc_v["insufficient_evidence"] += 1
                print(f"  (no extraction) {title[:55]}")
                return
            cfg = types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                response_mime_type="application/json",
                response_schema=_judge_schema(),
                temperature=0.0,
                thinking_config=types.ThinkingConfig(thinking_level=types.ThinkingLevel.MINIMAL),
            )
            prompt = _judge_prompt(title, ext.get("city"), ext.get("state"), ext.get("venue"), excerpt)
            try:
                resp = await loop.run_in_executor(None, lambda: client.models.generate_content(
                    model=GEMINI_MODEL, contents=[types.Part.from_text(text=prompt)], config=cfg))
                v = json.loads((resp.text or "{}").strip())
            except Exception as e:  # noqa: BLE001
                print(f"  judge failed: {e}")
                return
            venue_v[v.get("venue_verdict", "insufficient_evidence")] += 1
            loc_v[v.get("location_verdict", "insufficient_evidence")] += 1
            print(f"  venue={v.get('venue_verdict'):20} loc={v.get('location_verdict'):20} | "
                  f"{ext.get('venue')} @ {ext.get('city')} | {title[:40]}")

    await asyncio.gather(*[_one(t) for t in sample])

    def rate(c: Counter, key: str) -> str:
        tot = sum(c.values()) or 1
        return f"{c.get(key,0)}/{tot} ({100*c.get(key,0)/tot:.0f}%)"

    print("\n=== JUDGE SUMMARY ===")
    print(f"venue  supported={rate(venue_v,'supported')}  unsupported={rate(venue_v,'unsupported')}  insufficient={rate(venue_v,'insufficient_evidence')}")
    print(f"loc    supported={rate(loc_v,'supported')}  unsupported={rate(loc_v,'unsupported')}  insufficient={rate(loc_v,'insufficient_evidence')}")


if __name__ == "__main__":
    asyncio.run(main())
