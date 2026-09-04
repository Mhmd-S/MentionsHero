"""Import the local `donald_trump_transcripts/*.txt` files into Supabase, and
publish every transcript.

The .txt files are the output of `generate_wh_transcripts.py` — the same
`[MM:SS] Speaker:` body the pipeline writes to `transcripts.transcript`, wrapped
in a metadata header. This script parses that header, inserts the rows the DB is
missing, and links speakers so the persona pages can find them.

Speaker links are not optional. `public_service._find_transcript_ids_by_aliases()`
joins personas to transcripts through `transcript_speakers`, so a transcript
inserted without them is invisible on `/personas/{slug}` no matter what
`is_public` says.

DRY RUN BY DEFAULT. Nothing is written without `--apply`.

    # See what would happen (no writes):
    ./backend/venv/bin/python backend/scripts/import_local_transcripts.py

    # Do it:
    ./backend/venv/bin/python backend/scripts/import_local_transcripts.py --apply

    # Only flip existing rows public, import nothing:
    ./backend/venv/bin/python backend/scripts/import_local_transcripts.py --apply --publish-only

    # Import, but leave everything unpublished:
    ./backend/venv/bin/python backend/scripts/import_local_transcripts.py --apply --no-publish
"""

import argparse
import asyncio
import re
import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import get_supabase
from backend.services.speaker_service import extract_and_save_transcript_speakers

SOURCE_DIR = Path(__file__).parent.parent.parent / "donald_trump_transcripts"

# The Donald Trump persona has NO rows in persona_aliases, which is why
# /personas/donald-trump shows nothing: the public router short-circuits on
# `if not persona.get("aliases")` before it ever looks at a transcript. Publishing
# and importing fix nothing on their own without these.
#
# Every string here is a speaker label that actually appears in the source files.
# Alias matching is `ilike(name, alias)` with no wildcards — an exact,
# case-insensitive equality — so "Trump" matches a speaker literally labelled
# "Trump" and never "Melania Trump".
TRUMP_ALIASES = [
    "Donald Trump",
    "President Trump",
    "Donald J. Trump",
    "President Donald Trump",
    "President Donald J. Trump",
    "Trump",
]

# The header block the generator writes, terminated by a second ==== rule.
RULE = re.compile(r"^={10,}\s*$")
FIELD = re.compile(r"^(Transcript|YouTube|Upload date):\s*(.*)$")


def parse_file(path: Path) -> dict[str, Any] | None:
    """Split one .txt into its header fields and the transcript body."""
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.split("\n")

    if not lines or not RULE.match(lines[0].strip()):
        return None

    meta: dict[str, str] = {}
    body_start = None
    for i, line in enumerate(lines[1:], start=1):
        if RULE.match(line.strip()):
            body_start = i + 1
            break
        match = FIELD.match(line.strip())
        if match:
            meta[match.group(1)] = match.group(2).strip()

    if body_start is None:
        return None

    body = "\n".join(lines[body_start:]).strip()
    url = meta.get("YouTube", "").strip()
    if not url or not body:
        return None

    # The DB stores yt-dlp's YYYYMMDD, not the ISO date in the header.
    upload_date = None
    raw_date = meta.get("Upload date", "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date):
        upload_date = raw_date.replace("-", "")
    elif re.fullmatch(r"\d{8}", raw_date):
        upload_date = raw_date

    return {
        "youtube_url": url,
        "name": meta.get("Transcript") or path.stem,
        "transcript": body,
        "upload_date": upload_date,
        "source_file": path.name,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="actually write (default: dry run)")
    parser.add_argument("--publish-only", action="store_true", help="skip the import, only set is_public")
    parser.add_argument("--no-publish", action="store_true", help="import without setting is_public")
    parser.add_argument("--folder-id", default=None, help="folder to file imported transcripts under")
    parser.add_argument("--no-aliases", action="store_true", help="skip seeding the Donald Trump aliases")
    parser.add_argument(
        "--relink-only",
        action="store_true",
        help="only rebuild speaker links for transcripts that have none",
    )
    args = parser.parse_args()

    # --relink-only is a repair pass: touch nothing but transcript_speakers.
    if args.relink_only:
        args.publish_only = True
        args.no_publish = True
        args.no_aliases = True

    publish = not args.no_publish
    supabase = get_supabase()

    if not args.apply:
        print("DRY RUN — nothing will be written. Re-run with --apply.\n")

    # ── Persona aliases ──────────────────────────────────────────────
    aliases_added = 0
    if not args.no_aliases:
        persona = (
            supabase.table("personas")
            .select("id, name")
            .eq("slug", "donald-trump")
            .limit(1)
            .execute()
        )
        if not persona.data:
            print("WARNING: no persona with slug 'donald-trump'; skipping aliases")
        else:
            persona_id = persona.data[0]["id"]
            have = {
                a["alias"].lower()
                for a in (
                    supabase.table("persona_aliases")
                    .select("alias")
                    .eq("persona_id", persona_id)
                    .execute()
                    .data
                    or []
                )
            }
            missing = [a for a in TRUMP_ALIASES if a.lower() not in have]
            print(f"Persona 'Donald Trump': {len(have)} aliases, adding {len(missing)}")
            for alias in missing:
                if not args.apply:
                    print(f"  + alias {alias!r}")
                    aliases_added += 1
                    continue
                try:
                    supabase.table("persona_aliases").insert(
                        {"persona_id": persona_id, "alias": alias}
                    ).execute()
                    aliases_added += 1
                except Exception as exc:
                    print(f"  ERROR adding alias {alias!r}: {exc}")

    # ── Existing rows ────────────────────────────────────────────────
    existing = supabase.table("transcripts").select("id, youtube_url, is_public").execute()
    rows = existing.data or []
    known_urls = {r["youtube_url"] for r in rows if r.get("youtube_url")}
    unpublished = [r for r in rows if not r.get("is_public")]
    print(f"DB: {len(rows)} transcripts, {len(unpublished)} not public")

    # ── Import ───────────────────────────────────────────────────────
    imported = 0
    if not args.publish_only:
        if not SOURCE_DIR.is_dir():
            print(f"ERROR: {SOURCE_DIR} does not exist")
            return 1

        files = sorted(SOURCE_DIR.glob("*.txt"))
        parsed, unparseable = [], []
        for path in files:
            record = parse_file(path)
            (parsed if record else unparseable).append(record or path.name)

        new = [r for r in parsed if r["youtube_url"] not in known_urls]
        # Two files can point at the same video; keep the first.
        deduped, seen = [], set()
        for record in new:
            if record["youtube_url"] in seen:
                continue
            seen.add(record["youtube_url"])
            deduped.append(record)

        print(
            f"Files: {len(files)} found, {len(parsed)} parsed, "
            f"{len(unparseable)} unreadable, {len(parsed) - len(new)} already in DB, "
            f"{len(deduped)} to import"
        )
        for name in unparseable[:5]:
            print(f"  unreadable: {name}")

        for record in deduped:
            payload = {
                "youtube_url": record["youtube_url"],
                "name": record["name"],
                "transcript": record["transcript"],
                "upload_date": record["upload_date"],
                "is_public": publish,
            }
            if args.folder_id:
                payload["folder_id"] = args.folder_id

            if not args.apply:
                print(f"  + {record['name'][:70]} ({record['upload_date']})")
                imported += 1
                continue

            try:
                inserted = supabase.table("transcripts").insert(payload).execute()
                if not inserted.data:
                    print(f"  FAILED insert: {record['source_file']}")
                    continue
                transcript_id = inserted.data[0]["id"]
                speakers = await extract_and_save_transcript_speakers(
                    transcript_id, record["transcript"]
                )
                print(f"  + {record['name'][:60]} — {len(speakers)} speakers")
                imported += 1
            except Exception as exc:
                print(f"  ERROR on {record['source_file']}: {exc}")

    # ── Publish ──────────────────────────────────────────────────────
    published = 0
    if publish and unpublished:
        if args.apply:
            for row in unpublished:
                try:
                    supabase.table("transcripts").update({"is_public": True}).eq(
                        "id", row["id"]
                    ).execute()
                    published += 1
                except Exception as exc:
                    print(f"  ERROR publishing {row['id']}: {exc}")
        else:
            published = len(unpublished)

    # ── Backfill missing speaker links ───────────────────────────────
    # A transcript with no rows in transcript_speakers is invisible on every
    # persona page regardless of is_public, so this is not cosmetic.
    linked = 0
    links = supabase.table("transcript_speakers").select("transcript_id").execute()
    have_links = {r["transcript_id"] for r in (links.data or [])}
    all_rows = (
        supabase.table("transcripts").select("id, name").execute().data or []
        if args.relink_only
        else rows
    )
    missing = [r["id"] for r in all_rows if r["id"] not in have_links]
    print(f"Transcripts with no speaker links: {len(missing)}")

    if not args.apply:
        for r in all_rows:
            if r["id"] in missing:
                print(f"  ~ would relink {r.get('name', r['id'])[:65]}")
    else:
        for transcript_id in missing:
            full = (
                supabase.table("transcripts")
                .select("transcript")
                .eq("id", transcript_id)
                .limit(1)
                .execute()
            )
            if not full.data:
                continue
            speakers = await extract_and_save_transcript_speakers(
                transcript_id, full.data[0]["transcript"]
            )
            if speakers:
                linked += 1

    verb = "would" if not args.apply else ""
    print(
        f"\nDone. {verb} added {aliases_added} aliases, {verb} imported {imported}, "
        f"{verb} published {published}, backfilled speaker links on {linked}."
    )
    if not args.apply:
        print("Re-run with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
