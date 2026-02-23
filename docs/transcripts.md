# Transcript Generation

Transcribes YouTube videos with speaker diarization using Gemini 2.0 Flash. Supports single videos, batch URLs, and playlists.

## Data Flow

```
User enters YouTube URL(s)
  → POST /api/jobs (or /api/jobs/batch)
  → Background task: process_job()
    1. DOWNLOADING: yt-dlp extracts MP3 audio
    2. TRANSCRIBING: Gemini 2.0 Flash transcribes with speaker diarization
    3. SAVING: Insert transcript + extract speakers + trigger market reprocessing
  → SSE stream: GET /api/jobs/{job_id}/stream
  → Frontend polls progress via useJobProgress composable
  → On completion: navigate to /admin/transcripts/{transcript_id}
```

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

### Batch Processing
- `POST /api/jobs/batch` accepts multiple videos with a shared folder_id
- Each video becomes its own job with `playlist_id`, `playlist_name`, `playlist_index`
- Concurrent batch limit: `MAX_CONCURRENT = 10` (semaphore)

## Transcript Format

Gemini returns structured segments, formatted as text:

```
Caroline:
Good afternoon everyone, welcome to today's briefing.

Reporter:
Thank you. Can you comment on the latest developments?

SPEAKER_00:
Content from unnamed speaker.
```

Stored as plain text in `transcripts.transcript`. Speakers are also:
- Stored in `transcripts.speakers` JSONB (legacy, denormalized)
- Normalized into `speakers` + `transcript_speakers` tables with segment counts

## Gemini Integration

**File**: `backend/services/transcription_service.py`

- Audio < 20MB: sent inline to Gemini API
- Audio >= 20MB: uploaded via Gemini Files API first
- Response schema enforces `{ segments: [{ speaker, timestamp, content }] }`
- Retry logic: 3 attempts with exponential backoff (2^attempt seconds) for 429/502/503/504
- Speaker hint: optional user-provided context passed to Gemini prompt to improve speaker identification

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/jobs` | Create single transcription job |
| `POST` | `/api/jobs/batch` | Create batch jobs (playlist or multiple URLs) |
| `GET` | `/api/jobs` | List active jobs |
| `GET` | `/api/jobs/{job_id}/stream` | SSE progress stream (accepts `?token=`) |
| `POST` | `/api/jobs/{job_id}/cancel` | Cancel a running job |
| `GET` | `/api/transcripts` | List all transcripts |
| `GET` | `/api/transcripts/{id}` | Get transcript (supports `?search=` and `?speakers=` filtering) |
| `PATCH` | `/api/transcripts/{id}` | Update name or folder_id |
| `DELETE` | `/api/transcripts/{id}` | Delete transcript |

## File Map

| Layer | File | Purpose |
|-------|------|---------|
| Page | `app/pages/admin/index.vue` | URL input, video preview, job creation UI |
| Page | `app/pages/admin/transcripts/[id].vue` | Transcript viewer with search/speaker filtering |
| Page | `app/pages/admin/transcripts/index.vue` | Transcript listing grouped by date |
| Composable | `app/composables/useJobProgress.ts` | SSE streaming, progress state |
| Composable | `app/composables/useAuthFetch.ts` | Authenticated API calls |
| Router | `backend/routers/jobs.py` | Job endpoints + `process_job()` background task |
| Router | `backend/routers/transcripts.py` | Transcript CRUD endpoints |
| Service | `backend/services/transcription_service.py` | Gemini transcription logic |
| Service | `backend/services/download_service.py` | yt-dlp audio download |
| Service | `backend/services/transcript_service.py` | Transcript DB operations |
| Service | `backend/services/job_service.py` | Job state management, SSE events |
| Service | `backend/services/speaker_service.py` | Speaker extraction & storage |
| Service | `backend/services/youtube_service.py` | YouTube metadata via yt-dlp |
| Model | `backend/models/job.py` | Job status enum, request/response models |
| Model | `backend/models/transcript.py` | Transcript models with highlights |
| Model | `backend/models/speaker.py` | Speaker records |
| Util | `backend/utils/nlp.py` | `parse_transcript_segments()`, `extract_speakers()` |
| Util | `backend/utils/transcript_filter.py` | Highlighting, speaker frequency |

## Public Viewer

A read-only, unauthenticated transcript viewer at `/view/{transcript_id}` with display-time speaker name normalization.

### Speaker Normalization

Raw Gemini speaker labels (e.g., "SPEAKER_00", "Caroline", "Press Secretary") are resolved to canonical persona names at request time using persona aliases. The raw transcript text in the DB is never modified.

**Resolution logic** (in `persona_service.resolve_transcript_speakers()`):
- Bidirectional case-insensitive substring matching: `sl == alias or alias in sl or sl in alias`
- Same matching strategy as `find_affected_persona_ids()` in `kalshi_service.py`
- Unresolved speakers (no persona alias match) are shown with their raw label in neutral gray

**Data flow:**
```
GET /api/public/transcripts/{id}  (no auth)
  → fetch transcript from DB
  → parse_transcript() → segments
  → build_alias_to_persona_map() → {alias_lower: persona_name}
  → resolve_transcript_speakers() → {raw_label: display_name}
  → return PublicTranscriptResponse with normalized segments
```

### Public API Endpoint

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/api/public/transcripts/{id}` | None | Returns normalized transcript with resolved speaker names |

Response includes: `segments[]` (with `speaker`, `speaker_raw`, `resolved`, `content`), `speaker_map`, `speakers` (ordered by first appearance), `segment_counts`.

### Read Metering (Free Tier)

Public transcript viewing is metered for client users. Each unique transcript read counts against a monthly limit.

**How it works:**
1. On mount, the viewer calls `POST /api/public/reads/record` with the transcript ID + Bearer token (if logged in)
2. Backend checks `transcript_reads` table: if `UNIQUE(user_id, transcript_id)` row exists, it's a re-read (doesn't count)
3. Counts unique reads this calendar month against `FREE_TIER_LIMIT = 5`
4. Returns `{ allowed, reads_this_month, limit }`

**Frontend behavior:**
- `allowed: true` → show full transcript
- `allowed: false` + no session → prompt to sign in/sign up
- `allowed: false` + session → show paywall with usage count
- Anonymous users (no token) → `allowed: false` with sign-up prompt

**API endpoint:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/public/reads/record` | Optional Bearer | Record a read, returns metering status |

Request body: `{ "transcript_id": "uuid" }`
Response: `{ "allowed": true, "reads_this_month": 3, "limit": 5 }`

### Frontend

- **Page:** `app/pages/view/[id].vue` — uses `public` layout (no sidebar), includes read metering gate
- **Layout:** `app/layouts/public.vue` — minimal wrapper, no auth
- **Auth exemption:** `/view/` prefix is skipped in `app/middleware/auth.global.ts`
- **Features:** Speaker color badges, client-side search/highlight, speaker filter, segment counts sidebar, read metering paywall

### File Map (Public Viewer)

| Layer | File | Purpose |
|-------|------|---------|
| Page | `app/pages/view/[id].vue` | Public transcript viewer with metering gate |
| Layout | `app/layouts/public.vue` | Minimal public layout |
| Composable | `app/composables/useReads.ts` | `checkAndRecordRead()`, `FREE_TIER_LIMIT` |
| Router | `backend/routers/public.py` | Unauthenticated `/api/public/transcripts/{id}` + `/api/public/reads/record` |
| Service | `backend/services/persona_service.py` | `build_alias_to_persona_map()`, `resolve_transcript_speakers()` |
| Model | `backend/models/transcript.py` | `PublicSegment`, `PublicTranscriptResponse`, `RecordReadRequest`, `ReadStatusResponse` |

## Database Tables

**transcripts**
- `id` (uuid PK), `youtube_url` (text), `transcript` (text), `name` (text), `folder_id` (uuid FK → folders), `speakers` (jsonb), `upload_date` (text YYYYMMDD), `created_at`

**jobs**
- `id` (uuid PK), `youtube_url`, `status` (text enum), `stage_progress` (jsonb), `error_message`, `transcript_id` (uuid FK → transcripts SET NULL), `cancel_requested` (bool), `video_title`, `playlist_id`, `playlist_name`, `playlist_index`, `created_at`, `updated_at`

**speakers**
- `id` (uuid PK), `name` (text UNIQUE), `created_at`

**transcript_speakers**
- `id` (uuid PK), `transcript_id` (uuid FK), `speaker_id` (uuid FK), `segment_count` (int), `created_at`

**transcript_reads**
- `id` (uuid PK), `user_id` (uuid NOT NULL), `transcript_id` (uuid FK → transcripts CASCADE), `read_at` (timestamptz)
- UNIQUE(user_id, transcript_id) — re-reads don't count against the monthly limit
- Index: `idx_transcript_reads_user_month` on (user_id, read_at DESC)
