"""Print a one-line live snapshot of the most recent metadata_backfill run."""

from datetime import datetime, timezone

from backend.core.database import get_analytical_table


def _age(iso: str | None) -> str:
    if not iso:
        return "?"
    s = iso.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return "?"
    return f"{(datetime.now(timezone.utc) - dt).total_seconds():.0f}s"


def main():
    rows = (
        get_analytical_table("procurement_runs")
        .select("*")
        .eq("source_type", "metadata_backfill")
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    ).data or []
    if not rows:
        print("no metadata_backfill run found")
        return
    r = rows[0]
    done = r.get("items_new", 0) + r.get("items_skipped", 0)
    total = r.get("items_found", 0)
    print(
        f"status={r['status']} progress={done}/{total} "
        f"ok={r.get('items_new',0)} failed={r.get('items_skipped',0)} "
        f"cur=[{r.get('current_item_index')}] {str(r.get('current_item_name'))[:45]!r} "
        f"tok={r.get('prompt_tokens',0)+r.get('completion_tokens',0)} "
        f"heartbeat={_age(r.get('updated_at'))}ago run={r['id'][:8]}"
    )


if __name__ == "__main__":
    main()
