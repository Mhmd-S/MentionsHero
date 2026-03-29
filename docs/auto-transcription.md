# Auto-Transcription

Automatic periodic monitoring of YouTube channels/playlists for new videos, with automatic transcription into the existing pipeline.

## Overview

Each **auto-source** links a YouTube channel or playlist to a persona. A background scheduler (APScheduler) checks sources at configurable intervals, discovers new videos, applies optional title filtering, deduplicates against existing transcripts, and queues transcription jobs through the standard `process_job()` pipeline.

## Database Tables

### `auto_sources`
Links a YouTube channel/playlist to a persona with transcription configuration.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| persona_id | uuid FK → personas CASCADE | |
| source_type | text | `'channel'` or `'playlist'` |
| youtube_url | text UNIQUE | YouTube channel/playlist URL |
| source_name | text | Cached name (fetched on creation) |
| folder_id | uuid FK → folders SET NULL | Target folder for transcripts |
| speaker_hint | text | Passed to Gemini for speaker identification |
| check_interval_minutes | int DEFAULT 360 | How often to check (minutes) |
| max_videos_per_check | int DEFAULT 5 | Max new videos to transcribe per check |
| is_enabled | bool DEFAULT true | Toggle scheduling on/off |
| title_filter | text | Optional regex to filter video titles |

### `auto_runs`
History log of each automated check run.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| auto_source_id | uuid FK → auto_sources CASCADE | |
| status | text | `running`, `completed`, `failed` |
| videos_found/new/queued/skipped | int | Counters |
| error_message | text | On failure |
| details | jsonb | Array of `{url, title, action}` per video |
| started_at, completed_at | timestamptz | |

### `auto_source_videos`
Tracks which videos have been processed per source (dedup + audit).

| Column | Type | Notes |
|--------|------|-------|
| auto_source_id | uuid FK | |
| youtube_url | text | |
| action | text | `transcribed`, `filtered`, `skipped` |
| job_id | uuid | If transcribed |
| UNIQUE(auto_source_id, youtube_url) | | |

## API Endpoints

All endpoints require admin auth. Prefix: `/api/auto-transcription`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/sources` | List all sources (with persona name, last run) |
| GET | `/sources/{id}` | Get single source |
| POST | `/sources` | Create source |
| PATCH | `/sources/{id}` | Update source config |
| DELETE | `/sources/{id}` | Delete source |
| POST | `/sources/{id}/check` | Manually trigger a check |
| GET | `/sources/{id}/runs` | Run history for source |
| GET | `/runs` | Recent runs across all sources |

## Check Flow

1. Scheduler fires for a source (or admin triggers manual check)
2. Multi-instance dedup: skip if a recent run exists within `check_interval / 2`
3. Fetch videos from YouTube via `get_channel_videos()` or `get_playlist_info()`
4. Apply `title_filter` regex (if set) to filter video titles
5. Deduplicate against `transcripts.youtube_url` and `auto_source_videos.youtube_url`
6. Cap new videos to `max_videos_per_check`
7. For each new video: create job via `job_service.create_job()`, then `process_job()` in background
8. Record results in `auto_runs` and `auto_source_videos`

## Scheduler

- Uses APScheduler `AsyncIOScheduler` with `IntervalTrigger` per source
- State reconstructed from DB on startup (no persistent job store needed)
- `max_instances=1` prevents overlapping checks for the same source
- Stale runs (status='running' for >1 hour) cleaned up on startup
- Disabled via `AUTO_TRANSCRIPTION_ENABLED=false` env var

## Concurrency

- Auto-transcription jobs use a separate semaphore (`auto_semaphore`, max 3) to avoid starving manual jobs
- Manual jobs use the existing `job_semaphore` (max 10)
- Both are defined in `backend/core/concurrency.py`

## Multi-Instance Safety

With `min_machines_running = 2` on Fly.io, both machines run the scheduler. Before each check, the service queries `auto_runs` for a recent run on the same source. If one exists within `check_interval / 2`, it skips. This prevents duplicate processing without external coordination.

## Title Filter Examples

- PMQ: `(?i)prime minister.*question|PMQ`
- Trump Press Briefing: `(?i)press briefing|press conference`
- Specific series: `(?i)weekly address`

## File Map

| File | Purpose |
|------|---------|
| `supabase/migrations/20260329_add_auto_transcription.sql` | Database migration |
| `backend/models/auto_transcription.py` | Pydantic models |
| `backend/services/auto_transcription_service.py` | Core business logic (CRUD + check) |
| `backend/scheduler.py` | APScheduler integration |
| `backend/routers/auto_transcription.py` | API endpoints |
| `backend/core/concurrency.py` | Shared semaphores |
| `app/composables/useAutoTranscription.ts` | Frontend API composable |
| `app/pages/admin/auto-transcription.vue` | Admin management page |
