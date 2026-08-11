"""Re-transcribe auto-transcribed videos whose audio was truncated.

Background: before the `--live-from-start` fix in download_service.py, yt-dlp
downloaded fresh livestream VODs from the *live edge*, dropping the start of the
event. The resulting transcripts begin mid-event (re-timestamped from 00:00), so
they look complete but the first half is missing.

This re-downloads (now from the start), re-transcribes, and updates each
transcript **IN PLACE** — same `transcripts.id`, so event_tags /
auto_source_videos / transcript_speakers links survive. Speakers are re-extracted
(a clean delete+reinsert) and metadata is re-run with the auto-source's persona
(unless the existing event_tag was manually confirmed — those are left alone).

Modes:
  --list                 DB-only: list every auto transcript + its current audio
                         span (no yt-dlp, no changes). Quick scope view.
  --dry-run              Probe yt-dlp durations; report which look truncated.
  (default)              Re-transcribe the ones detected as truncated, in place.
  --all                  Re-transcribe every auto transcript (skip detection).
  --ids a,b,c            Re-transcribe these transcript ids only.
  --limit N              Cap how many are processed.
  --concurrency N        Parallel re-transcriptions (default 2; downloads are heavy).
  --cover-ratio R        Truncated if audio span < R * real duration (default 0.9).
  --min-gap S            ...and (duration - span) > S seconds (default 120).

NOTE: requires a working yt-dlp (downloads). Run it on the backend host, not a
bot-blocked shell. Example:
  backend/venv/bin/python -m backend.scripts.retranscribe_truncated_auto --dry-run
"""

import argparse
import asyncio
import logging
import os
import re

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)
logger = logging.getLogger("retranscribe")

from backend.core.database import get_supabase, get_analytical_table
from backend.services.download_service import download_audio, cleanup_audio_file
from backend.services.transcription_service import transcribe_audio
from backend.services.youtube_service import get_video_info
from backend.services import speaker_service
from backend.services.metadata_extraction_service import populate_for_transcript

DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")
_TS_RE = re.compile(r"\[(\d+):(\d{2})(?::(\d{2}))?\]")


def last_span_seconds(transcript: str) -> int:
    """Largest timestamp in the transcript → covered audio span in seconds.
    Handles both [MM:SS] (minutes may exceed 59) and [HH:MM:SS]."""
    best = 0
    for m in _TS_RE.finditer(transcript or ""):
        a, b, c = m.group(1), m.group(2), m.group(3)
        secs = (int(a) * 3600 + int(b) * 60 + int(c)) if c is not None else (int(a) * 60 + int(b))
        best = max(best, secs)
    return best


def _hms(s: int) -> str:
    return f"{s // 60}:{s % 60:02d}"


def load_candidates() -> list[dict]:
    """Every auto-transcribed video that produced a completed transcript, with
    its source persona/speaker_hint and existing event_tag provenance."""
    sb = get_supabase()
    asv = (
        sb.table("auto_source_videos")
        .select("youtube_url, job_id, auto_source_id")
        .eq("action", "transcribed")
        .execute()
    ).data or []
    asv = [a for a in asv if a.get("job_id")]

    src_ids = list({a["auto_source_id"] for a in asv})
    sources = {}
    for i in range(0, len(src_ids), 100):
        for s in (sb.table("auto_sources").select("id, persona_id, speaker_hint")
                  .in_("id", src_ids[i:i + 100]).execute().data or []):
            sources[s["id"]] = s

    job_ids = [a["job_id"] for a in asv]
    jobs = {}
    for i in range(0, len(job_ids), 100):
        for j in (sb.table("jobs").select("id, transcript_id, status")
                  .in_("id", job_ids[i:i + 100]).execute().data or []):
            jobs[j["id"]] = j

    tids = [j["transcript_id"] for j in jobs.values()
            if j.get("status") == "completed" and j.get("transcript_id")]
    tx = {}
    for i in range(0, len(tids), 100):
        for t in (sb.table("transcripts").select("id, name, youtube_url, transcript, upload_date")
                  .in_("id", tids[i:i + 100]).execute().data or []):
            tx[t["id"]] = t

    tag_src = {}
    for i in range(0, len(tids), 100):
        for e in (get_analytical_table("event_tags").select("transcript_id, classification_source")
                  .in_("transcript_id", tids[i:i + 100]).execute().data or []):
            tag_src[e["transcript_id"]] = e.get("classification_source")

    out = []
    seen = set()
    for a in asv:
        j = jobs.get(a["job_id"])
        if not j or j.get("status") != "completed" or not j.get("transcript_id"):
            continue
        tid = j["transcript_id"]
        if tid in seen or tid not in tx:
            continue
        seen.add(tid)
        src = sources.get(a["auto_source_id"], {})
        t = tx[tid]
        out.append({
            "transcript_id": tid,
            "name": t.get("name"),
            "youtube_url": t.get("youtube_url") or a["youtube_url"],
            "transcript": t.get("transcript") or "",
            "persona_id": src.get("persona_id"),
            "speaker_hint": src.get("speaker_hint"),
            "tag_source": tag_src.get(tid),
        })
    return out


async def retranscribe_one(c: dict, sem: asyncio.Semaphore) -> dict:
    """Re-download (from start) + re-transcribe + update in place."""
    tid = c["transcript_id"]
    async with sem:
        audio_path = None
        old_span = last_span_seconds(c["transcript"])
        try:
            info = await get_video_info(c["youtube_url"])
            audio_path = await download_audio(url=c["youtube_url"], downloads_dir=DOWNLOADS_DIR)
            transcript = await transcribe_audio(
                audio_path=audio_path,
                speaker_hint=c.get("speaker_hint"),
                video_title=info.title or c.get("name"),
            )
            await cleanup_audio_file(audio_path)
            audio_path = None

            update = {"transcript": transcript}
            if info.title:
                update["name"] = info.title
            if info.upload_date:
                update["upload_date"] = info.upload_date
            get_supabase().table("transcripts").update(update).eq("id", tid).execute()

            await speaker_service.extract_and_save_transcript_speakers(tid, transcript)

            # Re-run metadata, but never clobber an admin-confirmed (manual) tag.
            if c.get("tag_source") == "manual":
                meta = "skipped (manual tag)"
            elif c.get("persona_id"):
                await populate_for_transcript(
                    transcript_id=tid,
                    title=info.title or c.get("name") or "",
                    description=info.description or "",
                    transcript_text=transcript,
                    was_live=info.was_live,
                    release_timestamp=info.release_timestamp,
                    timestamp=info.timestamp,
                    persona_id=c["persona_id"],
                )
                meta = "re-extracted"
            else:
                meta = "skipped (no persona)"

            new_span = last_span_seconds(transcript)
            logger.info("OK %s | span %s -> %s | meta %s | %s",
                        tid[:8], _hms(old_span), _hms(new_span), meta, str(c.get("name"))[:45])
            return {"transcript_id": tid, "status": "retranscribed", "old": old_span, "new": new_span}
        except Exception as e:
            if audio_path:
                await cleanup_audio_file(audio_path)
            logger.warning("FAIL %s | %s | %s", tid[:8], str(e)[:120], str(c.get("name"))[:45])
            return {"transcript_id": tid, "status": "failed", "error": str(e)}


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--ids", default="")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--cover-ratio", type=float, default=0.9)
    ap.add_argument("--min-gap", type=int, default=120)
    args = ap.parse_args()

    candidates = load_candidates()
    logger.info("auto transcripts with a completed transcript: %d", len(candidates))

    if args.ids:
        want = {x.strip() for x in args.ids.split(",") if x.strip()}
        candidates = [c for c in candidates if c["transcript_id"] in want]

    if args.list:
        for c in sorted(candidates, key=lambda x: last_span_seconds(x["transcript"])):
            logger.info("span=%s tag=%s %s | %s", _hms(last_span_seconds(c["transcript"])),
                        c.get("tag_source"), c["transcript_id"][:8], str(c.get("name"))[:55])
        return

    # Detection (needs yt-dlp). --all / --ids skip it.
    if args.all or args.ids:
        targets = candidates
    else:
        targets = []
        for c in candidates:
            try:
                info = await get_video_info(c["youtube_url"])
            except Exception as e:
                logger.warning("probe-skip %s (%s)", c["transcript_id"][:8], str(e)[:80])
                continue
            span = last_span_seconds(c["transcript"])
            dur = int(info.duration or 0)
            truncated = bool(info.was_live) and dur > 0 and span < dur * args.cover_ratio and (dur - span) > args.min_gap
            if truncated:
                logger.info("TRUNCATED %s span=%s real=%s | %s",
                            c["transcript_id"][:8], _hms(span), _hms(dur), str(c.get("name"))[:45])
                targets.append(c)
        logger.info("detected truncated: %d / %d probed", len(targets), len(candidates))

    if args.limit:
        targets = targets[:args.limit]

    if args.dry_run:
        logger.info("[dry-run] would re-transcribe %d transcript(s)", len(targets))
        return

    sem = asyncio.Semaphore(args.concurrency)
    results = await asyncio.gather(*[retranscribe_one(c, sem) for c in targets])
    ok = sum(1 for r in results if r["status"] == "retranscribed")
    fail = sum(1 for r in results if r["status"] == "failed")
    logger.info("DONE re-transcribed=%d failed=%d", ok, fail)


if __name__ == "__main__":
    asyncio.run(main())
