"""Context window computation service.

Aggregates news items and Truth Social posts from the time window
preceding a speech to create a snapshot of the 'atmosphere'.
"""

import logging
from datetime import datetime, timezone, timedelta

from backend.core.database import get_analytical_table, get_supabase
from backend.services.analytical_news_service import get_news_for_window
from backend.services.analytical_truth_social_service import get_posts_for_window

logger = logging.getLogger(__name__)


def _tbl(name: str):
    return get_analytical_table(name)


async def compute_context_window(
    transcript_id: str,
    persona_id: str,
    hours_before: int = 72,
) -> dict | None:
    """Compute the pre-speech atmosphere for a transcript.

    Aggregates news items and Truth Social posts from the window
    before the speech and stores the snapshot.
    """
    supabase = get_supabase()

    # Get transcript to determine window_end from upload_date (public schema)
    transcript = (
        supabase.table("transcripts")
        .select("id, upload_date, name")
        .eq("id", transcript_id)
        .single()
        .execute()
    )
    if not transcript.data:
        logger.error("Transcript %s not found", transcript_id)
        return None

    # Parse upload_date (YYYYMMDD format) into datetime
    upload_date_str = transcript.data.get("upload_date")
    if not upload_date_str:
        logger.warning("Transcript %s has no upload_date", transcript_id)
        return None

    try:
        window_end = datetime.strptime(upload_date_str, "%Y%m%d").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        try:
            window_end = datetime.fromisoformat(upload_date_str)
            if window_end.tzinfo is None:
                window_end = window_end.replace(tzinfo=timezone.utc)
        except ValueError:
            logger.warning("Cannot parse upload_date '%s'", upload_date_str)
            return None

    window_start = window_end - timedelta(hours=hours_before)

    # Fetch data within the window
    news_items = await get_news_for_window(persona_id, window_start, window_end)
    ts_posts = await get_posts_for_window(persona_id, window_start, window_end)

    # Aggregate metrics
    news_sentiment_avg = None
    sentiments = [
        n["sentiment_score"] for n in news_items
        if n.get("sentiment_score") is not None
    ]
    if sentiments:
        news_sentiment_avg = sum(sentiments) / len(sentiments)

    # Extract top news topics (flatten all topic arrays)
    all_topics: list[str] = []
    for n in news_items:
        topics = n.get("topics")
        if isinstance(topics, list):
            all_topics.extend(topics)

    # Count topic frequency and take top 10
    topic_counts: dict[str, int] = {}
    for t in all_topics:
        topic_counts[t] = topic_counts.get(t, 0) + 1
    top_news_topics = sorted(topic_counts, key=topic_counts.get, reverse=True)[:10]

    # Upsert context window
    window_data = {
        "transcript_id": transcript_id,
        "persona_id": persona_id,
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "truth_social_post_count": len(ts_posts),
        "news_item_count": len(news_items),
        "news_sentiment_avg": news_sentiment_avg,
        "top_news_topics": top_news_topics,
        "truth_social_topics": [],  # Future: extract topics from TS posts
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }

    response = _tbl("context_windows").upsert(
        window_data, on_conflict="transcript_id,persona_id"
    ).execute()

    result = response.data[0] if response.data else None

    logger.info(
        "Context window for transcript %s: %d news items, %d TS posts in %dh window",
        transcript_id, len(news_items), len(ts_posts), hours_before,
    )

    return result


async def get_context_window(
    transcript_id: str,
    persona_id: str,
) -> dict | None:
    """Get a computed context window."""
    response = (
        _tbl("context_windows")
        .select("*")
        .eq("transcript_id", transcript_id)
        .eq("persona_id", persona_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


async def bulk_compute_windows(persona_id: str) -> dict:
    """Compute context windows for all transcripts of a persona."""
    supabase = get_supabase()

    # Get all transcripts with upload dates (public schema)
    transcripts_resp = (
        supabase.table("transcripts")
        .select("id, upload_date, name")
        .not_.is_("upload_date", "null")
        .order("upload_date", desc=True)
        .execute()
    )
    all_transcripts = transcripts_resp.data or []

    # Get already-computed windows for this persona (analytical schema)
    existing_resp = (
        _tbl("context_windows")
        .select("transcript_id")
        .eq("persona_id", persona_id)
        .execute()
    )
    existing_ids = {w["transcript_id"] for w in (existing_resp.data or [])}

    # Filter to uncomputed
    to_compute = [t for t in all_transcripts if t["id"] not in existing_ids]

    computed = 0
    skipped = 0
    failed = 0

    for transcript in to_compute:
        try:
            result = await compute_context_window(transcript["id"], persona_id)
            if result:
                computed += 1
            else:
                skipped += 1
        except Exception as e:
            logger.error(
                "Context window failed for transcript %s: %s",
                transcript["id"], e,
            )
            failed += 1

    logger.info(
        "Bulk context windows: computed=%d, skipped=%d, failed=%d",
        computed, skipped, failed,
    )

    return {
        "computed": computed,
        "skipped": skipped,
        "failed": failed,
    }
