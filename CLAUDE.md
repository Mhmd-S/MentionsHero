# Transcript Analysis Platform

A tool for transcribing YouTube videos (primarily press briefings), analyzing term frequency across transcripts, and tracking Polymarket prediction markets tied to speaker mentions.

## Tech Stack

- **Frontend**: Nuxt 3 (Vue 3 + TypeScript) in `app/`
- **Backend**: FastAPI (Python 3) in `backend/`
- **Database**: Supabase (PostgreSQL)
- **Transcription**: Google Gemini 2.0 Flash (speaker diarization)
- **Audio Download**: yt-dlp
- **UI Components**: Nuxt UI (UButton, UBadge, UModal, UInput, USelectMenu, etc.)
- **ML Training**: MLX LoRA fine-tuning on Apple Silicon (per-persona)

## Project Structure

```
app/                          # Nuxt 3 frontend
  pages/                      # Route pages
    index.vue                 # New Transcript creation
    login.vue                 # Authentication
    term-search.vue           # Term Search
    transcripts/              # Transcript listing & detail
    personas/                 # Persona listing & detail
    events/                   # Polymarket events listing & detail
  composables/                # API interaction layer
    useAuthFetch.ts           # Authenticated fetch wrapper
    useJobProgress.ts         # SSE job streaming
    useAnalysis.ts            # Term search & analysis API
    usePersonas.ts            # Persona CRUD API
    usePolymarket.ts          # Polymarket API
    useFileTree.ts            # Folder/transcript management
    useAuth.ts                # Authentication state
  components/                 # Reusable components
    FileTree/                 # Sidebar file tree (FileTree.vue, FileTreeFolder.vue, FileTreeItem.vue)
    TermSearch.vue            # Term search interface
    SpeakerSelector.vue       # Multi-select speaker picker
  layouts/
    default.vue               # Main layout with fixed sidebar
  middleware/
    auth.global.ts            # Global auth guard

backend/                      # FastAPI backend
  main.py                     # App entry point, router registration
  config.py                   # Settings from .env (Supabase, Gemini, CORS)
  core/
    auth.py                   # Supabase JWT auth
    database.py               # Supabase client, caching helpers
    process_tracker.py        # Subprocess termination tracking
  routers/                    # API route handlers
    jobs.py                   # /api/jobs/* - Job creation, SSE streaming
    transcripts.py            # /api/transcripts/* - Transcript CRUD
    folders.py                # /api/folders/* - Folder CRUD
    analysis.py               # /api/analysis/* - Term search, n-grams, speakers
    video.py                  # /api/video/* - YouTube metadata
    playlist.py               # /api/playlist/* - Playlist metadata
    polymarket.py             # /api/polymarket/* - Series, events, markets
    personas.py               # /api/personas/* - Persona CRUD, aliases
  services/                   # Business logic
    job_service.py            # Job lifecycle, SSE events
    transcript_service.py     # Transcript DB operations
    transcription_service.py  # Gemini transcription
    download_service.py       # yt-dlp audio download
    speaker_service.py        # Speaker extraction & storage
    folder_service.py         # Folder hierarchy operations
    persona_service.py        # Persona DB operations
    polymarket_service.py     # Gamma API client, market analysis (largest file ~1300 lines)
    youtube_service.py        # YouTube metadata via yt-dlp
  models/                     # Pydantic request/response models
    job.py, transcript.py, folder.py, analysis.py,
    speaker.py, persona.py, polymarket.py, video.py
  utils/
    nlp.py                    # Term frequency, n-grams, text cleaning, context search
    transcript_filter.py      # Transcript parsing, highlighting, speaker extraction

utils/
  db_refrence.sql             # Database schema reference (read-only, not executable)

supabase/
  migrations/                 # SQL migration files

docs/                         # Feature documentation (see below)
```

## Features & Documentation

Each feature has detailed documentation in `docs/`. Read the relevant file before modifying feature code.

| Feature | Doc File | Description |
|---------|----------|-------------|
| Transcript Generation | `docs/transcripts.md` | YouTube → yt-dlp → Gemini → DB pipeline with SSE progress |
| Term Search | `docs/term-search.md` | Frequency analysis, context search, n-grams across transcripts |
| Personas | `docs/personas.md` | Speaker identity management with aliases, Polymarket links |
| Events (Polymarket) | `docs/events.md` | Series → Events → Markets hierarchy, Gamma API, market analysis |
| Sidebar & Directory | `docs/sidebar.md` | FileTree component, folder hierarchy, drag-and-drop |

## Mandatory: Update Documentation on Feature Changes

When you edit code that belongs to a feature, you MUST also update the corresponding documentation file in `docs/`. This is not optional.

- Transcript generation changes → update `docs/transcripts.md`
- Term search changes → update `docs/term-search.md`
- Persona changes → update `docs/personas.md`
- Events/Polymarket changes → update `docs/events.md`
- Sidebar/FileTree/folder changes → update `docs/sidebar.md`
- Database schema changes → update the relevant feature doc AND the Database section below
- New features → create a new `docs/<feature>.md` and add it to the table above

What to update:
- New/changed endpoints, functions, or data flow
- New/changed database tables or columns
- New/changed file paths
- Removed functionality (delete from docs, don't leave stale references)

## Database Overview

### Core Tables

| Table | Purpose |
|-------|---------|
| `transcripts` | Full transcript text, youtube_url, name, folder_id, upload_date |
| `jobs` | Job progress tracking (status, stage_progress, cancel_requested) |
| `folders` | Hierarchical folders (self-referencing parent_id) |
| `speakers` | Normalized speaker names (unique) |
| `transcript_speakers` | Junction: transcript ↔ speaker with segment_count |
| `analysis_cache` | Cached analysis results with TTL (cache_key, result JSONB, expires_at) |

### Persona Tables

| Table | Purpose |
|-------|---------|
| `personas` | Speaker identities (name, description) |
| `persona_aliases` | Aliases for a persona (unique alias text, FK → personas CASCADE) |

### Polymarket Tables

| Table | Purpose |
|-------|---------|
| `polymarket_series` | Series wrapper (polymarket_id, slug, title, active, closed) |
| `polymarket_events` | Events within a series (slug, title, start/end dates) |
| `polymarket_markets` | Markets within events (question, outcome_prices, resolved_outcome) |
| `persona_polymarket_series` | Junction: persona ↔ series with optional folder_id scoping |
| `market_search_configs` | Auto-extracted search terms from market questions |
| `market_term_results` | Per-persona, per-term analysis results (mentions, trend, context) |
| `persona_polymarket_events` | Legacy junction table (backward compat, prefer series) |

### Key Relationships

```
folders (parent_id) → folders           # Recursive hierarchy
transcripts.folder_id → folders
transcript_speakers → transcripts + speakers
persona_aliases → personas (CASCADE)
polymarket_events.series_id → polymarket_series
polymarket_markets.event_id → polymarket_events (CASCADE)
persona_polymarket_series → personas + polymarket_series + folders
market_search_configs.market_id → polymarket_markets (CASCADE)
market_term_results → polymarket_markets + personas
```

## API Overview

All routes require Supabase JWT auth (`Authorization: Bearer <token>`).

| Prefix | Router | Purpose |
|--------|--------|---------|
| `/api/jobs` | `jobs.py` | Create jobs, SSE streaming, cancel |
| `/api/transcripts` | `transcripts.py` | List, get, update, delete transcripts |
| `/api/folders` | `folders.py` | Folder CRUD |
| `/api/analysis` | `analysis.py` | Term frequency, n-grams, context search, speakers |
| `/api/video` | `video.py` | YouTube video metadata |
| `/api/playlist` | `playlist.py` | YouTube playlist metadata |
| `/api/polymarket` | `polymarket.py` | Series/events/markets CRUD, analysis |
| `/api/personas` | `personas.py` | Persona CRUD, alias management |

## Key Conventions & Gotchas

- **Python 3 binary**: Use `python3`, not `python`
- **FastAPI route ordering**: Static routes (`/series/search`) MUST be defined BEFORE parameterized routes (`/series/{series_id}`) to avoid path conflicts
- **Supabase client**: Use `from backend.core.database import supabase` — singleton client
- **Auth**: All endpoints use `require_auth` dependency (global in main.py). SSE streams accept `?token=` query param
- **Nuxt UI**: Use Nuxt UI components (UButton, UBadge, UModal, etc.), not raw HTML elements
- **Composables pattern**: All API calls go through composables in `app/composables/`, never direct fetch from pages
- **Gamma API quirk**: Series endpoint returns events WITHOUT nested markets — must fetch each event individually via `/events/{slug}` to get markets
- **Market resolution**: closed market with `outcome_prices[0] >= 0.95` → YES, `[1] >= 0.95` → NO
- **Speaker regex**: Pattern `^([A-Z0-9][\w\s\-'._()]{1,60}?):\s*(.*)$` — supports "Name:", "SPEAKER_00:", etc.
- **Idempotent upserts**: Polymarket events/markets use slug or condition_id as unique keys

## Development

```bash
# Frontend (port 3000)
cd app && pnpm dev

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
