# Transcript Analysis Platform (Admin)

An admin tool for transcribing YouTube videos (primarily press briefings), managing personas/speakers, manually running auto-transcription on YouTube channels/playlists, and procuring analytical context (news, Truth Social posts, event tags). Admin-only — there is no public-facing site.

## Tech Stack

- **Frontend**: Nuxt 3 (Vue 3 + TypeScript) at the repo root (`app/`, `nuxt.config.ts`, `package.json`)
- **Backend**: FastAPI (Python 3) in `backend/`
- **Database**: Supabase (PostgreSQL)
- **Auth**: Supabase Auth (email/password). Admin role gated via `profiles.role = 'admin'`
- **Transcription**: Google Gemini (speaker diarization)
- **Audio Download**: yt-dlp
- **UI Components**: Nuxt UI (UButton, UBadge, UModal, UInput, USelectMenu, etc.)

## Project Structure

```
app/                            # Nuxt 3 frontend
  pages/
    login.vue                   # Sign in (only public route)
    admin/
      index.vue                 # New Transcript creation
      auto-transcription.vue    # Auto-transcription sources + global timeline (manual run only)
      transcripts/              # Transcript listing & detail
      personas/                 # Persona listing & detail
  composables/
    useAuth.ts                  # Session + role state (calls /api/auth/me)
    useAuthFetch.ts             # Authenticated fetch wrapper
    useAnalysis.ts              # Speaker list/search (used by personas)
    usePersonas.ts              # Persona CRUD API
    useFileTree.ts              # Folder/transcript management
    useAutoTranscription.ts     # Auto-transcription source management
    useJobProgress.ts           # SSE job streaming
    useHighlight.ts             # Transcript text highlighting
  components/
    FileTree/                   # Sidebar file tree
    SpeakerSelector.vue         # Multi-select speaker picker (used by personas)
    BatchUrlInput.vue, FolderPicker.vue, JobProgress.vue, JobsSidebar.vue,
    PlaylistSelector.vue, VideoPreview.vue
  layouts/
    admin.vue                   # Admin layout with sidebar (only layout)
  middleware/
    auth.global.ts              # Admin-only guard; only /login is open
  plugins/
    auth.client.ts              # Initializes useAuth on client boot
  utils/
    supabase.ts                 # Lightweight Supabase client wrapper

backend/                        # FastAPI backend
  main.py                       # App entry point, per-router auth
  config.py                     # Settings from .env (Supabase, Gemini, CORS)
  scheduler.py                  # APScheduler for analytical procurement (auto-transcription is manual-only)
  core/
    auth.py                     # require_admin, require_user_auth, optional_auth
    database.py                 # Supabase singleton, analysis_cache helpers (legacy table, unused)
    concurrency.py, process_tracker.py
  routers/
    auth.py                     # /api/auth/me — returns role for frontend gating
    jobs.py                     # /api/jobs/* — job creation, SSE, cancel (admin)
    transcripts.py              # /api/transcripts/* (admin)
    folders.py                  # /api/folders/* (admin)
    analysis.py                 # /api/analysis/speakers* (admin) — speaker list/search/migrate
    video.py, playlist.py, channel.py  # YouTube metadata helpers (admin)
    personas.py                 # /api/personas/* (admin)
    auto_transcription.py       # /api/auto-transcription/* (admin)
    analytical.py               # /api/analytical/* (admin)
  services/
    job_service.py, transcript_service.py, transcription_service.py,
    download_service.py, speaker_service.py, folder_service.py,
    persona_service.py, youtube_service.py, yt_dlp_utils.py,
    auto_transcription_service.py,
    analytical_news_service.py, analytical_truth_social_service.py,
    analytical_event_tag_service.py, analytical_context_service.py,
    analytical_procurement_service.py,   # orchestrates scraper runs
    scrapers/                            # base.py, truth_social.py, fox_news.py, __init__.py (registry)
  models/                       # Pydantic models for the surviving routers
    job.py, transcript.py, folder.py, analysis.py, auto_transcription.py,
    speaker.py, persona.py, video.py, analytical.py
  utils/
    nlp.py                      # parse_transcript_segments (speaker-only)
    transcript_filter.py        # Transcript parsing & highlighting

utils/
  db_refrence.sql               # Schema reference (read-only, not executable)

supabase/
  migrations/                   # SQL migration files (history kept; some tables are now unused)

docs/                           # Feature documentation (admin features only)
```

## Features & Documentation

| Feature | Doc File | Description |
|---------|----------|-------------|
| Transcript Generation | `docs/transcripts.md` | YouTube → yt-dlp → Gemini → DB pipeline with SSE progress |
| Personas | `docs/personas.md` | Speaker identity management with aliases |
| Sidebar & Directory | `docs/sidebar.md` | FileTree component, folder hierarchy, drag-and-drop |
| Auto-Transcription | `docs/auto-transcription.md` | Manual-trigger YouTube channel/playlist transcription with global timeline |
| Analytical Procurement | `docs/analytical.md` | News, Truth Social, event context procurement |

## Mandatory: Update Documentation on Feature Changes

When you edit code that belongs to a feature, you MUST also update the corresponding doc in `docs/`:
- Transcripts → `docs/transcripts.md`
- Personas → `docs/personas.md`
- Sidebar/FileTree/folders → `docs/sidebar.md`
- Auto-transcription → `docs/auto-transcription.md`
- Analytical procurement → `docs/analytical.md`
- Database schema changes → update the relevant feature doc AND the Database section below
- New features → create a new `docs/<feature>.md` and add it to the table above

## Database Overview

### Active Tables

| Table | Purpose |
|-------|---------|
| `transcripts` | Full transcript text, youtube_url, name, folder_id, upload_date |
| `profiles` | User profiles. `role` ('admin'/'client') gates access; admins are the only users that can use the app |
| `jobs` | Job progress tracking (status, stage_progress, cancel_requested) |
| `folders` | Hierarchical folders (self-referencing parent_id) |
| `speakers` | Normalized speaker names (unique) |
| `transcript_speakers` | Junction: transcript ↔ speaker with segment_count |
| `personas` | Speaker identities (name, description, slug, image_url) |
| `persona_aliases` | Aliases for a persona (FK → personas CASCADE) |
| `auto_sources` | YouTube channel/playlist → persona links |
| `auto_source_videos` | Per-source video tracking; powers the global timeline |

### Analytical Tables (`analytical` schema)

| Table | Purpose |
|-------|---------|
| `analytical.news_items` | Real news articles about a persona (currently Fox News via dated sitemap). Has `source_domain`/`source_name`; indexed for outlet + date-range filtering. |
| `analytical.truth_social_posts` | Real @realDonaldTrump posts via the public Truth Social (Mastodon) API. `external_id` = stable post id; has `is_retruth`, `media_urls`, `engagement`. |
| `analytical.event_tags` | Per-transcript metadata bundle. Surfaced fields: event_type (16-value taxonomy), city/state/country/venue, event_time (timestamptz), classification_source. Populated by `metadata_extraction_service` (Gemini + DDG, with retry) on transcript creation; admin confirms via UI. NOTE: `audience_type`, `event_time_local`, `confidence`, `interviewer`, `network`, `is_teleprompter`, `notes` remain as columns but are no longer extracted or exposed by the API/UI (droppable in a future cleanup). |
| `analytical.procurement_runs` | Audit + live-status log for every analytical job. Source types include `truth_social`, `news_fox`, `event_tag_auto`, `metadata_backfill`. Scrape runs now populate `current_item_index/name` + counts (cancel via `cancel_requested`); metadata runs also populate `prompt_tokens/completion_tokens`, so the `/admin/operations` dashboard shows live progress + Gemini cost. Failures land in `error_message` + the `details` JSONB (per-item `action`/`error`), surfaced as expandable rows in the dashboard. `params`/`retry_of`/`attempt` back the **Retry** action (`POST /procurement-runs/{id}/retry` re-runs a terminal run with its original params as a new linked run). |
| `analytical.context_windows` | Pre-speech atmosphere snapshots |

### Legacy / Unused Tables

The `subscriptions`, `kalshi_*`, `market_*`, `poly_*`, `analysis_cache`, `auto_runs`, and `notebooks` tables (plus paywall/SEO columns on transcripts/personas, plus `auto_sources.check_interval_minutes` / `auto_sources.is_enabled`) remain in the database from earlier features that have been removed. No code reads or writes them. They can be dropped with a future cleanup migration when convenient.

### Key Relationships

```
folders (parent_id) → folders               # Recursive hierarchy
transcripts.folder_id → folders
transcript_speakers → transcripts + speakers
persona_aliases → personas (CASCADE)
auto_sources.persona_id → personas (CASCADE)
auto_sources.folder_id → folders (SET NULL)
auto_source_videos.auto_source_id → auto_sources (CASCADE)
analytical_news_items.persona_id → personas (CASCADE)
analytical_truth_social_posts.persona_id → personas (CASCADE)
analytical_event_tags.transcript_id → transcripts (CASCADE)
analytical_context_windows → transcripts (CASCADE) + personas (CASCADE)
analytical_procurement_runs.persona_id → personas (CASCADE)
```

## API Overview

All `/api/*` routes except `/api/auth/me` require admin role. `/api/auth/me` requires any authenticated user and returns `{ role }` so the frontend can gate UI.

| Prefix | Router | Auth | Purpose |
|--------|--------|------|---------|
| `/api/auth` | `auth.py` | User | `GET /me` returns the caller's role |
| `/api/jobs` | `jobs.py` | Admin | Create jobs, SSE streaming, cancel |
| `/api/transcripts` | `transcripts.py` | Admin | List, get, update, delete transcripts |
| `/api/folders` | `folders.py` | Admin | Folder CRUD |
| `/api/analysis` | `analysis.py` | Admin | Speaker list/search/migrate |
| `/api/video` | `video.py` | Admin | YouTube video metadata |
| `/api/playlist` | `playlist.py` | Admin | YouTube playlist metadata |
| `/api/channel` | `channel.py` | Admin | YouTube channel video listing |
| `/api/personas` | `personas.py` | Admin | Persona CRUD, alias management |
| `/api/auto-transcription` | `auto_transcription.py` | Admin | Auto-transcription sources, manual `/run`, global `/timeline` |
| `/api/analytical` | `analytical.py` | Admin | `POST /scrape` (date-ranged Truth Social / Fox News), News/Truth-Social reads (range + outlet filter), event tags, context, procurement-runs control (list w/ status filter, cancel, **retry**, reset-stale, delete) |

## Key Conventions & Gotchas

- **Python 3 binary**: Use `python3`, not `python`
- **FastAPI route ordering**: Static routes MUST be defined BEFORE parameterized routes
- **Supabase client**: Use `from backend.core.database import supabase` — singleton client
- **Auth**:
  - Frontend role-gating: `useAuth().role` is hydrated from `GET /api/auth/me` on login
  - Backend admin gate: every admin router uses `Depends(require_admin)` (declared in `main.py`)
  - SSE streams accept `?token=` query param
  - The middleware (`app/middleware/auth.global.ts`) lets `/login` through and requires `role === 'admin'` everywhere else
- **Root route**: `/` redirects to `/admin` via Nuxt route rule
- **Admin pages**: All admin pages live under `app/pages/admin/` and use `definePageMeta({ layout: 'admin' })`
- **Nuxt UI**: Use Nuxt UI components, not raw HTML elements
- **Composables pattern**: All API calls go through composables in `app/composables/`
- **Speaker regex**: Pattern `^([A-Z0-9][\w\s\-'._()]{1,60}?):\s*(.*)$` — supports "Name:", "SPEAKER_00:", etc.
- **Auto-transcription is manual-only**: there is no scheduler for auto-sources. `POST /api/auto-transcription/sources/{id}/run` is synchronous (returns counts once jobs are queued); transcription itself runs in background tasks gated by `auto_semaphore` (max 3) so it doesn't starve manual jobs
- **Analytical procurement scheduler**: APScheduler `AsyncIOScheduler` starts via FastAPI lifespan in `main.py`. Jobs scrape a rolling 2-day window for the Trump persona (Fox news every 6h, Truth Social every 12h) via `analytical_procurement_service.run_scrape`. Disable with `ANALYTICAL_PROCUREMENT_ENABLED=false`. The one-off Jan→now backfill is triggered manually from `/admin/analytical`.
- **Real scrapers (modular)**: `backend/services/scrapers/` holds one `BaseScraper` per source (`truth_social.py` = Mastodon API via `curl_cffi`, credential-free; `fox_news.py` = dated sitemap + `trafilatura`), registered in `scrapers/__init__.SCRAPERS`. `analytical_procurement_service.run_scrape(source_type, persona_id, start, end)` owns the run lifecycle. New deps: `curl_cffi`, `trafilatura`, `beautifulsoup4`, `lxml`. NOTE: the backend runs on the **framework Python** (`/Library/Frameworks/Python.framework/Versions/3.13/bin/python3`), not `.venv`.
- **Mandatory CLAUDE.md updates**: Any code change that affects project structure, conventions, API endpoints, database schema, key files, or development workflow MUST be reflected here

## Development

```bash
# Frontend (port 3000)
pnpm dev

# Backend (port 8001)
python3 -m uvicorn backend.main:app --reload --port 8001

# Or use the convenience script
./start_dev.sh
```

### Environment Variables (.env)

```
SUPABASE_URL=...
SUPABASE_SERVICE_KEY=...
GEMINI_API_KEY=...
```
