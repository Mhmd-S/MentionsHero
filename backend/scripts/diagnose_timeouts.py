"""One-off: tally action outcomes across recent procurement_runs to see which
timeouts dominate (yt-dlp vs Gemini) and how long runs take."""

import sys
from collections import Counter

from backend.core.database import get_analytical_table


def main():
    runs = (
        get_analytical_table("procurement_runs")
        .select("*")
        .order("started_at", desc=True)
        .limit(15)
        .execute()
    ).data or []

    print(f"{'source_type':<18} {'status':<10} {'found':>6} {'new':>5} {'skip':>5} {'dur_s':>7}  started")
    print("-" * 90)
    for r in runs:
        dur = "—"
        if r.get("started_at") and r.get("completed_at"):
            from datetime import datetime
            def p(s):
                s = s.replace("Z", "+00:00")
                return datetime.fromisoformat(s)
            dur = f"{(p(r['completed_at']) - p(r['started_at'])).total_seconds():.0f}"
        print(f"{r['source_type']:<18} {r['status']:<10} {r.get('items_found',0):>6} "
              f"{r.get('items_new',0):>5} {r.get('items_skipped',0):>5} {dur:>7}  {r.get('started_at','')[:19]}")

    # Deep-dive the most recent metadata_backfill run's details.
    meta = next((r for r in runs if r["source_type"] == "metadata_backfill"), None)
    if not meta:
        print("\nNo metadata_backfill run found.")
        return
    details = meta.get("details") or []
    print(f"\n=== latest metadata_backfill run {meta['id']} ({meta['status']}) ===")
    print(f"details entries: {len(details)}")
    actions = Counter(d.get("action") for d in details)
    for action, n in actions.most_common():
        print(f"  {action:<20} {n}")

    # Show a few sample errors per failing action.
    print("\n--- sample errors ---")
    seen = Counter()
    for d in details:
        a = d.get("action")
        if a in ("extracted", "tagged"):
            continue
        if seen[a] >= 3:
            continue
        seen[a] += 1
        err = d.get("error") or (d.get("errors") or [{}])[0].get("error") or ""
        print(f"  [{a}] {d.get('name','')[:50]} :: {str(err)[:160]}")


if __name__ == "__main__":
    sys.exit(main())
