"""Build a golden labeled set for event_type from REAL transcripts (read-only).

Samples a persona's transcripts, stratified by the deterministic classifier's
verdict so all event types + generic (deferred) titles are represented, and
writes a JSONL draft to backend/tests/golden/event_type_golden.jsonl.

For titles the deterministic classifier resolves, `expected_event_type` is
pre-filled (these labels are trustworthy by construction). For generic titles
it is left "" for a human to fill after a quick look — those are exactly the
cases the grounded LLM must handle, and where hand labels add the most signal.

Run from repo root:
    python3 -m backend.scripts.build_golden_set --per-type 6 --generic 20
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.core.database import get_supabase
from backend.services.event_type_classifier import classify_event_type_deterministic

OUT = Path(__file__).resolve().parents[1] / "tests" / "golden" / "event_type_golden.jsonl"


def _resolve_persona(persona_id: str | None) -> tuple[str, list[str]]:
    supabase = get_supabase()
    if persona_id:
        row = supabase.table("personas").select("id, name").eq("id", persona_id).single().execute()
        pid, name = row.data["id"], row.data.get("name") or ""
    else:
        row = supabase.table("personas").select("id, name").ilike("name", "%trump%").limit(1).execute()
        if not row.data:
            raise SystemExit("no Trump persona; pass --persona-id")
        pid, name = row.data[0]["id"], row.data[0].get("name") or ""
    aliases = supabase.table("persona_aliases").select("alias").eq("persona_id", pid).execute()
    al = [a["alias"] for a in (aliases.data or []) if a.get("alias")]
    if name and name not in al:
        al.append(name)
    return pid, al


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--persona-id", default=None)
    ap.add_argument("--per-type", type=int, default=6, help="max examples per resolved event_type")
    ap.add_argument("--generic", type=int, default=20, help="how many deferred/generic titles to include")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    pid, aliases = _resolve_persona(args.persona_id)
    from backend.services.metadata_extraction_service import _persona_transcript_pool

    pool = _persona_transcript_pool(pid, aliases)
    random.shuffle(pool)
    print(f"pool={len(pool)}")

    by_type: dict[str, list[dict]] = defaultdict(list)
    generic: list[dict] = []
    for t in pool:
        title = t.get("name") or ""
        det, sig = classify_event_type_deterministic(title)
        rec = {
            "transcript_id": t["id"],
            "title": title,
            "transcript_excerpt": (t.get("transcript") or "")[:500],
            "det_event_type": det,
            "det_signal": sig,
            "expected_event_type": det or "",  # human fills the blanks for generic titles
        }
        if det:
            if len(by_type[det]) < args.per_type:
                by_type[det].append(rec)
        elif len(generic) < args.generic:
            generic.append(rec)

    rows = [r for recs in by_type.values() for r in recs] + generic
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"wrote {len(rows)} rows to {OUT}")
    print("coverage by deterministic type:")
    for et in sorted(by_type):
        print(f"  {et:18} {len(by_type[et])}")
    print(f"  {'(generic/deferred)':18} {len(generic)}  <- fill expected_event_type by hand")


if __name__ == "__main__":
    main()
