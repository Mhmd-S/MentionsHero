"""Backfill script to populate transcripts with YouTube video title and upload date."""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import get_supabase
from backend.services.youtube_service import get_video_info


async def backfill_pmq_transcripts():
    """Backfill transcripts in PMQ folder with video title and upload date."""
    supabase = get_supabase()

    # Find PMQ folder
    folders_response = supabase.table("folders").select("id, name").execute()
    folders = folders_response.data or []

    pmq_folder = next((f for f in folders if f["name"].upper() == "PMQ"), None)
    if not pmq_folder:
        print("PMQ folder not found!")
        return

    print(f"Found PMQ folder: {pmq_folder['id']}")

    # Get all transcripts in PMQ folder
    transcripts_response = (
        supabase.table("transcripts")
        .select("id, youtube_url, name, upload_date")
        .eq("folder_id", pmq_folder["id"])
        .execute()
    )
    transcripts = transcripts_response.data or []

    print(f"Found {len(transcripts)} transcripts in PMQ folder")

    updated = 0
    skipped = 0
    failed = 0

    for t in transcripts:
        youtube_url = t.get("youtube_url")
        if not youtube_url:
            print(f"  Skipping {t['id']}: no YouTube URL")
            skipped += 1
            continue

        try:
            print(f"  Fetching info for: {youtube_url}")
            video_info = await get_video_info(youtube_url)

            update_data = {}
            if video_info.title:
                update_data["name"] = video_info.title
            if video_info.upload_date:
                update_data["upload_date"] = video_info.upload_date

            if update_data:
                supabase.table("transcripts").update(update_data).eq("id", t["id"]).execute()
                print(f"    Updated: {video_info.title} ({video_info.upload_date})")
                updated += 1
            else:
                print(f"    No data to update")
                skipped += 1

        except Exception as e:
            print(f"    Failed: {e}")
            failed += 1

        # Small delay to avoid rate limiting
        await asyncio.sleep(0.5)

    print(f"\nDone! Updated: {updated}, Skipped: {skipped}, Failed: {failed}")


if __name__ == "__main__":
    asyncio.run(backfill_pmq_transcripts())
