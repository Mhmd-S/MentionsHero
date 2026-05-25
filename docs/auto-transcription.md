# Auto-Transcription

Manual-trigger YouTube monitoring. Each **auto-source** links a YouTube channel or playlist to a persona; clicking **Run** on a source discovers new videos, applies an optional title-keyword filter, deduplicates against existing transcripts, and queues transcription jobs through the standard `process_job()` pipeline. There is no background scheduler.

A separate **Backfill** action exists for the initial population of a source — it pulls the source's full history (no `--playlist-end` cap for channels), still applies the title filter and dedup, and queues up to `backfill_limit` new videos. Intended to be run once per source.

## Database Tables

### `auto_sources`
Links a YouTube channel/playlist to a persona with transcription configuration.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| persona_id | uuid FK → personas CASCADE | |
| source_type | text | `'channel'` or `'playlist'` |
| youtube_url | text | YouTube channel/playlist URL |
| source_name | text | Cached name (fetched on creation) |
| folder_id | uuid FK → folders SET NULL | Target folder for transcripts |
| speaker_hint | text | Passed to Gemini for speaker identification |
| max_videos_per_check | int DEFAULT 5 | Safety cap on videos queued per regular **Run** |
| backfill_limit | int NULLABLE DEFAULT 500 | Cap for the one-shot **Backfill** action. `NULL` or `0` = unlimited. |
| title_filter | text | Optional comma-separated keywords (case-insensitive) |
| UNIQUE(persona_id, youtube_url) | | |

The legacy `check_interval_minutes` and `is_enabled` columns are no longer read or written by the application. They will be dropped in a future cleanup migration.

### `auto_source_videos`
Per-video record of every URL the source has seen. This is the **timeline**.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| auto_source_id | uuid FK → auto_sources CASCADE | |
| youtube_url | text | |
| video_title | text | |
| action | text | `transcribed`, `filtered`, `skipped` |
| job_id | uuid | Set when `action = 'transcribed'` |
| created_at | timestamptz | Used for timeline ordering |
| UNIQUE(auto_source_id, youtube_url) | | |

### `auto_runs` (legacy, unused)
Previous "run history" log. The application no longer writes to it. To be dropped in a future cleanup migration.

## API Endpoints

All endpoints require admin auth. Prefix: `/api/auto-transcription`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/timeline` | Global timeline of every video processed (joined with source, persona, job status, transcript id) |
| GET | `/sources` | List all sources |
| GET | `/sources/{id}` | Get a single source |
| POST | `/sources` | Create source |
| PATCH | `/sources/{id}` | Update source config |
| DELETE | `/sources/{id}` | Delete source (cascades to videos) |
| POST | `/sources/{id}/run` | **Run discovery + queueing for this source.** Synchronous: returns counts and per-video details once jobs are queued. Each transcription itself runs in the background. |
| POST | `/sources/{id}/backfill` | **One-shot full-history backfill.** Same return shape as `/run`. Ignores `max_videos_per_check`, removes yt-dlp's channel listing cap, and queues up to `backfill_limit` new videos. |

## Run Flow

Both Run and Backfill share the same pipeline (`_discover_and_queue` in the service) — they only differ in two caps.

1. Admin clicks **Run** (or **Backfill**) on a source in the UI
2. Backend fetches videos from YouTube via `get_channel_videos()` or `get_playlist_info()`
   - Run: channels are limited to yt-dlp's most recent 50 (`--playlist-end 50`)
   - Backfill: channels have **no** `--playlist-end` cap (every listable upload)
   - Playlists are always fully enumerated (yt-dlp has no inherent cap)
3. Apply `title_filter` (comma-separated keywords, case-insensitive) — non-matching videos are recorded as `filtered`
4. Deduplicate against `transcripts.youtube_url` and `auto_source_videos` rows with `action = 'transcribed'`
5. Cap remaining new videos:
   - Run: to `max_videos_per_check` (default 5)
   - Backfill: to `backfill_limit` (default 500; `0`/`NULL` = unlimited)
6. For each new video: `job_service.create_job()` then `process_job()` in a background task (gated by `auto_semaphore` so manual jobs aren't starved)
7. Each video upserted into `auto_source_videos` with its action and `job_id`
8. Endpoint returns `{ videos_found, videos_filtered, videos_existing, videos_queued, details }`

### Livestream handling

There's no live-vs-VOD branching in code; yt-dlp simply downloads whatever the source URL enumerates. Channel URLs default to the Home/Videos tab and **will not list past livestreams**. To ingest a channel's recorded livestreams (e.g. White House press briefings), add the source with the `/streams` tab suffix (e.g. `https://www.youtube.com/@WhiteHouse/streams`). The channel-URL validator already permits this suffix.

## Timeline

The frontend renders `GET /timeline` grouped by day (Today / Yesterday / Mon, May 1). Each entry shows status from the joined job (`pending` → `downloading` → `transcribing` → `completed` / `failed`). The timeline auto-refreshes every 5s while any in-flight job is visible.

## Concurrency

- Auto-transcription jobs use `auto_semaphore` (max 3 concurrent) so they don't starve manual user jobs
- Manual user jobs use `job_semaphore` (max 10)
- Both live in `backend/core/concurrency.py`

## Title Filter Examples

- PMQ: `PMQ, prime minister`
- Trump press briefings: `press briefing, press conference`
- Specific series: `weekly address`

## File Map

| File | Purpose |
|------|---------|
| `supabase/migrations/20260329_add_auto_transcription.sql` | Original schema (auto_runs table now legacy) |
| `supabase/migrations/20260523_add_backfill_limit.sql` | Adds `auto_sources.backfill_limit` |
| `backend/models/auto_transcription.py` | Pydantic models |
| `backend/services/auto_transcription_service.py` | CRUD + `run_source` + `backfill_source` + `_discover_and_queue` + `get_timeline` |
| `backend/routers/auto_transcription.py` | API endpoints |
| `backend/core/concurrency.py` | Shared semaphores |
| `app/composables/useAutoTranscription.ts` | Frontend API composable |
| `app/pages/admin/auto-transcription.vue` | Admin management page |
