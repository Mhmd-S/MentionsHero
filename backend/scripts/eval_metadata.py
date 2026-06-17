"""OLD-vs-NEW evaluation of metadata extraction on REAL transcripts.

The existing `analytical.event_tags` rows were produced by the OLD pipeline
(DDG + two title-centric calls). This script samples real transcripts, treats
their existing event_tags as the OLD baseline, runs the NEW grounded extractor
on the same transcripts, and reports the deltas: event_type `other`-rate,
per-field fill-rate, an OLD→NEW event_type confusion table, per-transcript
wall-clock, and token cost. Writes a markdown report to
docs/metadata-eval-findings.md.

Read-mostly: it only WRITES fresh extractions into memory + the report; it does
NOT upsert into event_tags (so it's safe to run without disturbing prod data).

Run from repo root:
    python3 -m backend.scripts.eval_metadata --limit 30
    python3 -m backend.scripts.eval_metadata --persona-id <uuid> --limit 50
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.core.database import get_analytical_table, get_supabase
from backend.services.event_type_classifier import classify_event_type_deterministic
from backend.services.metadata_extraction_service import (
    BULK_CONCURRENCY,
    extract_metadata,
)

LOC_FIELDS = ("city", "state", "country", "venue")
OUTPUT_PATH = Path(__file__).resolve().parents[2] / "docs" / "metadata-eval-findings.md"


def _resolve_persona(persona_id: str | None) -> tuple[str, str, list[str]]:
    """Return (persona_id, name, aliases). Defaults to the first Trump persona."""
    supabase = get_supabase()
    if persona_id:
        row = supabase.table("personas").select("id, name").eq("id", persona_id).single().execute()
        if not row.data:
            raise SystemExit(f"persona {persona_id} not found")
        pid, name = row.data["id"], row.data.get("name") or ""
    else:
        row = supabase.table("personas").select("id, name").ilike("name", "%trump%").limit(1).execute()
        if not row.data:
            raise SystemExit("no Trump persona found; pass --persona-id")
        pid, name = row.data[0]["id"], row.data[0].get("name") or ""
    aliases_resp = supabase.table("persona_aliases").select("alias").eq("persona_id", pid).execute()
    aliases = [a["alias"] for a in (aliases_resp.data or []) if a.get("alias")]
    if name and name not in aliases:
        aliases.append(name)
    return pid, name, aliases


def _fill_rates(rows: list[dict], fields) -> dict[str, float]:
    n = len(rows) or 1
    return {f: sum(1 for r in rows if r.get(f)) / n for f in fields}


def _pct(x: float) -> str:
    return f"{100 * x:4.0f}%"


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona-id", default=None)
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    pid, pname, aliases = _resolve_persona(args.persona_id)
    print(f"persona: {pname} ({pid}); aliases={len(aliases)}")

    # Lazy import so the heavy pool helper's deps load only when needed.
    from backend.services.metadata_extraction_service import _persona_transcript_pool

    pool = _persona_transcript_pool(pid, aliases)
    if not pool:
        raise SystemExit("no transcripts in persona pool")
    random.shuffle(pool)
    sample = pool[: args.limit]
    ids = [t["id"] for t in sample]
    print(f"pool={len(pool)} sampling {len(sample)}")

    # OLD baseline = existing event_tags for the sampled transcripts.
    old_by_id: dict[str, dict] = {}
    existing = (
        get_analytical_table("event_tags")
        .select("transcript_id, event_type, city, state, country, venue, event_time, classification_source")
        .in_("transcript_id", ids)
        .execute()
    )
    for r in (existing.data or []):
        old_by_id[r["transcript_id"]] = r

    # NEW extraction (title from `name`, no description — grounding compensates).
    sem = asyncio.Semaphore(BULK_CONCURRENCY)
    new_by_id: dict[str, dict] = {}
    durations: dict[str, float] = {}

    async def _run(t: dict) -> None:
        async with sem:
            t0 = time.perf_counter()
            try:
                res = await extract_metadata(
                    title=t.get("name") or "",
                    description="",
                    transcript_text=t.get("transcript") or "",
                )
            except Exception as e:  # noqa: BLE001
                res = {"_llm_failed": True, "_errors": [{"error": str(e)}]}
            durations[t["id"]] = time.perf_counter() - t0
            new_by_id[t["id"]] = res
            print(f"  [{durations[t['id']]:4.1f}s] {(t.get('name') or '')[:60]:60} -> "
                  f"{res.get('event_type')} ({res.get('_event_type_source')}) | {res.get('venue')}")

    await asyncio.gather(*[_run(t) for t in sample])

    # ---- aggregate ----
    n = len(sample)
    old_rows = [old_by_id.get(i, {}) for i in ids]
    new_rows = [new_by_id.get(i, {}) for i in ids]
    old_present = sum(1 for i in ids if i in old_by_id)
    old_manual = sum(1 for r in old_rows if r.get("classification_source") == "manual")

    def other_rate(rows):
        typed = [r for r in rows if r.get("event_type")]
        if not typed:
            return 0.0
        return sum(1 for r in typed if r["event_type"] == "other") / len(typed)

    old_fill = _fill_rates(old_rows, LOC_FIELDS)
    new_fill = _fill_rates(new_rows, LOC_FIELDS)

    new_sources = Counter(r.get("_event_type_source") for r in new_rows)
    new_failed = sum(1 for r in new_rows if r.get("_llm_failed"))
    det_resolved = sum(1 for t in sample if classify_event_type_deterministic(t.get("name") or "")[0])

    secs = sorted(durations.values())
    mean_s = sum(secs) / len(secs) if secs else 0
    p95_s = secs[int(0.95 * (len(secs) - 1))] if secs else 0
    tot_prompt = sum((r.get("_tokens_used") or {}).get("prompt_tokens", 0) for r in new_rows)
    tot_compl = sum((r.get("_tokens_used") or {}).get("completion_tokens", 0) for r in new_rows)
    # Gemini Flash-class grounded pricing is per-request for search; token cost only here.
    cost = tot_prompt * 0.075e-6 + tot_compl * 0.30e-6

    # OLD->NEW event_type transitions (focus: OLD other / null -> NEW specific).
    transitions = Counter()
    rescued = []  # OLD other/missing -> NEW specific
    for t in sample:
        i = t["id"]
        o = (old_by_id.get(i) or {}).get("event_type") or "(none)"
        nw = (new_by_id.get(i) or {}).get("event_type") or "(none)"
        transitions[(o, nw)] += 1
        if o in ("other", "(none)") and nw not in ("other", "(none)"):
            rescued.append((t.get("name"), o, nw, (new_by_id.get(i) or {}).get("_event_type_source")))

    # ---- report ----
    now = datetime.now(timezone.utc).isoformat()
    L = [
        "# Metadata Extraction — OLD vs NEW Eval",
        "",
        f"_Generated {now} from `backend/scripts/eval_metadata.py` "
        f"(persona={pname}, sample={n}, seed={args.seed})._",
        "",
        "NEW = single grounded Gemini call (Google Search) + deterministic event_type "
        "guardrail. OLD = the existing `event_tags` rows (DDG + two title-centric calls).",
        "",
        "## Headline",
        "",
        "| Metric | OLD | NEW |",
        "|---|---|---|",
        f"| event_type = `other` rate | {_pct(other_rate(old_rows))} | {_pct(other_rate(new_rows))} |",
        f"| venue fill-rate | {_pct(old_fill['venue'])} | {_pct(new_fill['venue'])} |",
        f"| city fill-rate | {_pct(old_fill['city'])} | {_pct(new_fill['city'])} |",
        f"| state fill-rate | {_pct(old_fill['state'])} | {_pct(new_fill['state'])} |",
        f"| country fill-rate | {_pct(old_fill['country'])} | {_pct(new_fill['country'])} |",
        "",
        f"- OLD rows present for {old_present}/{n} sampled transcripts "
        f"({old_manual} manually-confirmed, excluded from 'dumb LLM' judgement).",
        f"- NEW event_type source: deterministic={new_sources.get('deterministic', 0)}, "
        f"llm={new_sources.get('llm', 0)}, none={new_sources.get(None, 0)}; "
        f"deterministic guardrail resolved {det_resolved}/{n} titles outright.",
        f"- NEW extraction failures (`_llm_failed`): {new_failed}/{n}.",
        "",
        "## Speed & cost (NEW)",
        "",
        f"- per-transcript wall-clock: mean {mean_s:.1f}s, p95 {p95_s:.1f}s "
        f"(single grounded call; OLD made a DDG round-trip + 2 calls).",
        f"- tokens: {tot_prompt:,} prompt + {tot_compl:,} completion ≈ ${cost:.4f} token cost "
        f"(+ per-request Google Search grounding billing, not counted here).",
        "",
        f"## event_type rescues (OLD `other`/missing → NEW specific): {len(rescued)}",
        "",
    ]
    for name, o, nw, src in rescued[:40]:
        L.append(f"- `{o}` → **`{nw}`** ({src}) — {name}")
    L += ["", "## OLD → NEW transition counts", "", "| OLD | NEW | n |", "|---|---|---|"]
    for (o, nw), c in transitions.most_common():
        L.append(f"| {o} | {nw} | {c} |")
    L.append("")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(L), encoding="utf-8")
    print(f"\nwrote {OUTPUT_PATH}")
    print(f"OLD other-rate {other_rate(old_rows):.0%} -> NEW {other_rate(new_rows):.0%} | "
          f"venue fill {old_fill['venue']:.0%} -> {new_fill['venue']:.0%} | "
          f"mean {mean_s:.1f}s | rescues {len(rescued)}")


if __name__ == "__main__":
    asyncio.run(main())
