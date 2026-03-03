"""Backfill script to populate upload_date for ALL transcripts missing it."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import get_supabase
from backend.services.youtube_service import get_video_info


async def backfill_upload_dates():
    """Backfill upload_date for all transcripts that have a youtube_url but no upload_date."""
    supabase = get_supabase()

    # Fetch all transcripts missing upload_date
    response = (
        supabase.table("transcripts")
        .select("id, youtube_url, name, upload_date")
        .is_("upload_date", "null")
        .neq("youtube_url", "")
        .execute()
    )
    transcripts = response.data or []

    print(f"Found {len(transcripts)} transcripts missing upload_date")

    if not transcripts:
        print("Nothing to do!")
        return

    updated = 0
    skipped = 0
    failed = 0

    for i, t in enumerate(transcripts, 1):
        youtube_url = t.get("youtube_url")
        if not youtube_url:
            print(f"  [{i}/{len(transcripts)}] Skipping {t['id']}: no YouTube URL")
            skipped += 1
            continue

        try:
            print(f"  [{i}/{len(transcripts)}] Fetching: {youtube_url}")
            video_info = await get_video_info(youtube_url)

            update_data = {}
            if video_info.upload_date:
                update_data["upload_date"] = video_info.upload_date
            # Also backfill name if missing
            if not t.get("name") and video_info.title:
                update_data["name"] = video_info.title

            if update_data:
                supabase.table("transcripts").update(update_data).eq("id", t["id"]).execute()
                print(f"    Updated: {t.get('name') or video_info.title} -> {video_info.upload_date}")
                updated += 1
            else:
                print(f"    No upload_date available from YouTube")
                skipped += 1

        except Exception as e:
            print(f"    Failed: {e}")
            failed += 1

        # Small delay to avoid rate limiting
        await asyncio.sleep(0.5)

    print(f"\nDone! Updated: {updated}, Skipped: {skipped}, Failed: {failed}")


if __name__ == "__main__":
    asyncio.run(backfill_upload_dates())
