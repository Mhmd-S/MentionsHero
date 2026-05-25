# Transcript Generation

Transcribes YouTube videos with speaker diarization using Gemini Flash. Supports single videos, batch URLs, playlists, and YouTube channels.

## Data Flow

```
User enters YouTube URL(s)
  → POST /api/jobs (or /api/jobs/batch)
  → Background task: process_job()
    1. DOWNLOADING: yt-dlp extracts MP3 audio
    2. TRANSCRIBING: Gemini Flash transcribes with speaker diarization
    3. SAVING: Insert transcript + extract speakers
    4. METADATA: extract event_tag bundle (location/venue/type/audience/event_time)
       + freeze news/Truth Social context_window snapshot — best-effort, never fails the parent job
  → SSE stream: GET /api/jobs/{job_id}/stream
  → Frontend polls progress via useJobProgress composable
  → On completion: navigate to /transcripts/{transcript_id} to review the auto-extracted metadata
```

## Per-transcript metadata bundle

After step 3 (saving), `_populate_transcript_metadata` in `jobs.py` runs:
- Calls `metadata_extraction_service.extract_metadata` — two Gemini Flash calls (location/audience + title-only event_type) plus a DDG search. Writes to `analytical.event_tags` with `classification_source='auto_llm'`.
- Computes `event_time` from yt-dlp's `release_timestamp` (when `was_live=True`) or upload `timestamp`.
- Triggers `compute_context_window` against the default persona (Trump) — freezes news + Truth Social counts from the 72 hours before the event.

The transcript detail page renders this via `TranscriptMetadataPanel.vue` (auto-imported component) with an Edit modal. All auto-extracted values are SUGGESTIONS — saving via the modal flips `classification_source` to `manual`. See `docs/analytical.md` for the full taxonomy.

## Job Lifecycle

Jobs move through these statuses: `pending` → `downloading` → `transcribing` → `saving` → `completed` (or `failed`/`cancelled`).

Each status update pushes `stage_progress` via SSE:
```json
{
  "substep": "Extracting audio",
  "substep_detail": "Using yt-dlp to download MP3",
  "current_chunk": 1,
  "total_chunks": 3
}
```

### Cancellation
- Frontend calls `POST /api/jobs/{job_id}/cancel` → sets `cancel_requested = true` in DB
- `process_job()` checks `cancel_event` (asyncio.Event) at each stage boundary
- On cancel: cleans up audio file, marks job as `cancelled`

### Crash recovery (orphaned jobs)
- An unclean shutdown leaves jobs in non-terminal states (`pending`, `downloading`, `transcribing`, `saving`) — the `process_job()` task died but the DB row was never moved to a terminal state.
- Recovery is **manual**, triggered by the **Resume stuck jobs** button on the Auto-Transcription page (next to the timeline Refresh button). It hits `POST /api/jobs/resume-orphaned` which calls `resume_orphaned_jobs()` — queries `jobs` for non-terminal rows, resets each to `pending`, and re-dispatches `process_job()` in a background task. Auto-transcription orphans recover their `folder_id` / `speaker_hint` via a lookup against `auto_source_videos → auto_sources`, and route through `auto_semaphore`. Manual orphans run through `job_semaphore`.
- Idempotent — only non-terminal jobs are touched, so calling it on a healthy system is a no-op.
- Caveat: resumed jobs restart from `downloading` (no mid-stage checkpointing), so an in-flight `transcribing` job re-downloads the audio and re-runs Gemini.

### Batch Processing
- `POST /api/jobs/batch` accepts multiple videos with a shared folder_id
- Each video becomes its own job with `playlist_id`, `playlist_name`, `playlist_index`
- Concurrent batch limit: `MAX_CONCURRENT = 10` (semaphore)

### Channel Support
- YouTube channel URLs (`youtube.com/@handle`, `youtube.com/channel/...`, `youtube.com/c/...`, `youtube.com/user/...`) are detected automatically
- Tab suffixes are supported: `/streams`, `/videos`, `/shorts` (e.g., `youtube.com/@handle/streams` lists stream VODs)
- `POST /api/channel/info` fetches the most recent 50 videos from a channel using yt-dlp `--flat-playlist --playlist-end 50`
- Frontend reuses the PlaylistSelector component to display channel videos with search and multi-select
- Selected channel videos are submitted via the same batch job endpoint (`POST /api/jobs/batch`)

## Transcript Format

Gemini returns structured segments, formatted as text:

```
[00:00] Caroline:
Good afternoon everyone, welcome to today's briefing.

[01:23] Reporter:
Thank you. Can you comment on the latest developments?

[02:45] SPEAKER_00:
Content from unnamed speaker.
```

Each speaker segment includes a `[MM:SS]` timestamp. Timestamps can be toggled on/off in both admin and public transcript viewers.

Stored as plain text in `transcripts.transcript`. Speakers are also:
- Stored in `transcripts.speakers` JSONB (legacy, denormalized)
- Normalized into `speakers` + `transcript_speakers` tables with segment counts

## Audio Download

**File**: `backend/services/download_service.py`

- Uses yt-dlp to extract audio as MP3
- Audio quality: `--audio-quality 5` (medium, optimized for speech transcription)
- Mono audio: `--postprocessor-args "-ac 1"` (speech doesn't need stereo)
- Supports cancellation via asyncio.Event (terminates subprocess)

## Gemini Integration

**File**: `backend/services/transcription_service.py`

- Audio < 20MB: sent inline to Gemini API
- Audio >= 20MB: uploaded via Gemini Files API first
- Response schema enforces `{ segments: [{ speaker, timestamp, content }] }`
- Timestamps: Gemini generates `MM:SS` timestamps per segment, included in saved transcript as `[MM:SS] Speaker:` prefix
- Retry logic: 3 attempts with exponential backoff (2^attempt seconds) for 429/502/503/504
- Video title context: the YouTube video title (fetched via yt-dlp) is passed to the Gemini prompt to help with topic understanding, speaker identification, and domain-specific terminology
- Speaker hint: optional user-provided context passed to Gemini prompt to improve speaker identification
- Progress callback: reports substep updates ("Uploading audio to Gemini...", "Waiting for Gemini transcription...", "Processing transcript...") via SSE to the frontend

## Job Service (Async)

**File**: `backend/services/job_service.py`

- All Supabase calls run in `asyncio.run_in_executor()` to avoid blocking the event loop
- SSE events use `threading.Event` for cross-thread notification
- This ensures SSE status updates are delivered promptly to the frontend

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/jobs` | Create single transcription job |
| `POST` | `/api/jobs/batch` | Create batch jobs (playlist, channel, or multiple URLs) |
| `GET` | `/api/jobs` | List active jobs |
| `GET` | `/api/jobs/{job_id}/stream` | SSE progress stream (accepts `?token=`) |
| `POST` | `/api/jobs/{job_id}/cancel` | Cancel a running job |
| `POST` | `/api/channel/info` | Get recent videos from a YouTube channel |
| `GET` | `/api/transcripts` | List all transcripts |
| `GET` | `/api/transcripts/{id}` | Get transcript (supports `?search=` and `?speakers=` filtering) |
| `PATCH` | `/api/transcripts/{id}` | Update name or folder_id |
| `DELETE` | `/api/transcripts/{id}` | Delete transcript |

## File Map

| Layer | File | Purpose |
|-------|------|---------|
| Page | `app/pages/index.vue` | URL input, video preview, job creation UI |
| Page | `app/pages/transcripts/[id].vue` | Transcript viewer with search/speaker filtering |
| Page | `app/pages/transcripts/index.vue` | Transcript listing grouped by date |
| Composable | `app/composables/useJobProgress.ts` | SSE streaming, progress state |
| Composable | `app/composables/useAuthFetch.ts` | Authenticated API calls |
| Router | `backend/routers/jobs.py` | Job endpoints + `process_job()` background task |
| Router | `backend/routers/transcripts.py` | Transcript CRUD endpoints |
| Service | `backend/services/transcription_service.py` | Gemini transcription logic |
| Service | `backend/services/download_service.py` | yt-dlp audio download |
| Service | `backend/services/transcript_service.py` | Transcript DB operations |
| Service | `backend/services/job_service.py` | Job state management, SSE events |
| Service | `backend/services/speaker_service.py` | Speaker extraction & storage |
| Router | `backend/routers/channel.py` | Channel info endpoint |
| Service | `backend/services/youtube_service.py` | YouTube/playlist/channel metadata via yt-dlp |
| Model | `backend/models/job.py` | Job status enum, request/response models |
| Model | `backend/models/transcript.py` | Transcript models with highlights |
| Model | `backend/models/speaker.py` | Speaker records |
| Util | `backend/utils/nlp.py` | `parse_transcript_segments()`, `extract_speakers()` |
| Util | `backend/utils/transcript_filter.py` | Highlighting, speaker frequency |

## Logging

All transcript generation services use Python's `logging` module at INFO level. Logging is configured in `backend/logging_config.py` and initialized at app startup in `backend/main.py`.

Key log points:
- **Job lifecycle**: job creation, stage transitions (downloading/transcribing/saving), completion, cancellation, and failures
- **Download**: start and completion of audio downloads
- **Transcription**: start and completion, retry warnings on transient API errors (429/5xx)
- **Speaker extraction**: number of speakers extracted per transcript
- **Non-fatal failures**: video info fetch, speaker extraction, and market reprocessing failures logged at WARNING level with stack traces

All output goes to console (stdout/stderr) via uvicorn.

## Database Tables

**transcripts**
- `id` (uuid PK), `youtube_url` (text), `transcript` (text), `name` (text), `folder_id` (uuid FK → folders), `speakers` (jsonb), `upload_date` (text YYYYMMDD), `created_at`

**jobs**
- `id` (uuid PK), `youtube_url`, `status` (text enum), `stage_progress` (jsonb), `error_message`, `transcript_id` (uuid FK → transcripts SET NULL), `cancel_requested` (bool), `video_title`, `playlist_id`, `playlist_name`, `playlist_index`, `created_at`, `updated_at`

**speakers**
- `id` (uuid PK), `name` (text UNIQUE), `created_at`

**transcript_speakers**
- `id` (uuid PK), `transcript_id` (uuid FK), `speaker_id` (uuid FK), `segment_count` (int), `created_at`
