# Transcription Pipeline

## Purpose
Transcribes YouTube videos (single, playlist, or batch) into speaker-diarized text transcripts. Downloads audio via yt-dlp, transcribes with Gemini Flash, extracts speakers, and stores results in Supabase.

## User Flow
1. User pastes a YouTube URL on the home page
2. App auto-detects URL type (single video, playlist, or batch of URLs)
3. Video/playlist metadata previewed (thumbnail, title, duration)
4. User optionally selects a folder and provides a speaker hint
5. User clicks "Transcribe" — job(s) created
6. Real-time progress via SSE: downloading → transcribing → saving → completed
7. On completion, transcript appears in the transcript viewer

## Data Flow

```
index.vue
  → detectAndFetch() — determines URL type
  → fetchVideoInfo() → POST /api/video/info → youtube_service.get_video_info() → yt-dlp --dump-json
  → fetchPlaylistInfo() → POST /api/playlist/info → youtube_service.get_playlist_info() → yt-dlp --flat-playlist
  → startJob() → POST /api/jobs (single) or /api/jobs/batch (batch)

Backend process_job() (BackgroundTask):
  1. Fetch video info (upload date, title)
  2. Status → DOWNLOADING
  3. download_audio() → yt-dlp → MP3 file
  4. Check cancellation
  5. Status → TRANSCRIBING
  6. transcribe_audio() → Gemini Flash → speaker-diarized segments
  7. Cleanup audio file
  8. Check cancellation
  9. Status → SAVING
  10. INSERT transcript → Supabase
  11. extract_and_save_transcript_speakers() → speakers + transcript_speakers
  12. Reprocess market analysis for affected personas
  13. Status → COMPLETED

Frontend SSE (useJobProgress composable):
  EventSource → GET /api/jobs/{jobId}/stream?token={jwt}
  → Updates progress bar, status label, chunk info in real-time
  → Auto-closes on terminal state
```

## Key Files

### Frontend
| File | Purpose |
|------|---------|
| `app/pages/index.vue` | Main transcription page — URL input, mode detection, job creation |
| `app/components/VideoPreview.vue` | Displays video thumbnail, title, duration, channel |
| `app/components/BatchUrlInput.vue` | Multi-URL selection with search, select all/none |
| `app/components/PlaylistSelector.vue` | Two-column playlist browser with video selection |
| `app/components/FolderPicker.vue` | Hierarchical folder dropdown with create-new |
| `app/components/JobProgress.vue` | Progress bar with stage percentage, chunk info, error display |
| `app/composables/useJobProgress.ts` | SSE connection to job stream, computed status/progress properties |

### Backend
| File | Purpose |
|------|---------|
| `backend/routers/jobs.py` | Job CRUD, batch creation (max 50), SSE streams, process_job() |
| `backend/routers/video.py` | `POST /api/video/info` — single video metadata |
| `backend/routers/playlist.py` | `POST /api/playlist/info` — playlist metadata |
| `backend/services/job_service.py` | Job DB operations, SSE event management, cancellation |
| `backend/services/youtube_service.py` | yt-dlp wrappers for video/playlist info, URL validation |
| `backend/services/download_service.py` | Audio download via yt-dlp, cancellation support, cleanup |
| `backend/services/transcription_service.py` | Gemini transcription, file upload strategy, retry logic |
| `backend/services/yt_dlp_utils.py` | Shared yt-dlp base arguments (cookies, extractor args) |
| `backend/models/job.py` | JobStatus enum, Job, CreateJobRequest, BatchJobsRequest models |
| `backend/models/video.py` | VideoInfo, PlaylistInfo, PlaylistVideo models |

## Database Tables
- **jobs** — job queue with status progression and stage_progress JSONB
- **transcripts** — stored transcript text with folder and upload_date
- **speakers** — deduplicated speaker names (UNIQUE)
- **transcript_speakers** — junction with segment_count per speaker per transcript

## External Integrations
- **yt-dlp** — video metadata extraction (`--dump-json`) and audio download (`-x --audio-format mp3`)
- **Gemini Flash** (`gemini-3-flash-preview`) — speech-to-text with speaker diarization, structured JSON output. Files >20MB uploaded via Gemini Files API, smaller files sent inline.

## Key Implementation Details

**Batch processing:** Jobs created sequentially in DB, then processed in parallel via `asyncio.gather()` with `MAX_CONCURRENT=10` semaphore.

**Cancellation:** Cooperative — `cancel_requested` flag checked between stages. Download service monitors cancel event and terminates yt-dlp subprocess.

**SSE heartbeat:** 30-second timeout with `threading.Event` for instant wake on status change. Token passed as query param (EventSource limitation).

**Transcription format:** Gemini returns `{segments: [{speaker, timestamp, content}]}`. Formatted as `SPEAKER:\n[content]\n\n`.
