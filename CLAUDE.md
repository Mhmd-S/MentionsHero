# Transcript Analysis Platform

A SaaS platform for transcribing YouTube videos (primarily press briefings), analyzing term frequency across transcripts, and tracking Kalshi prediction markets tied to speaker mentions. Features a public persona directory with free-tier transcript access and an admin panel for content management.

## Tech Stack

- **Frontend**: Nuxt 3 (Vue 3 + TypeScript) in `app/`
- **Backend**: FastAPI (Python 3) in `backend/`
- **Database**: Supabase (PostgreSQL)
- **Auth**: Supabase Auth (same pool, role-based: admin vs client)
- **Transcription**: Google Gemini 2.0 Flash (speaker diarization)
- **Audio Download**: yt-dlp
- **UI Components**: Nuxt UI (UButton, UBadge, UModal, UInput, USelectMenu, etc.)
- **ML Training**: MLX LoRA fine-tuning on Apple Silicon (per-persona)

## Project Structure

```
app/                          # Nuxt 3 frontend
  pages/                      # Route pages
    index.vue                 # Public landing page (persona directory)
    login.vue                 # Authentication (shared by admin + client)
    signup.vue                # Client registration
    p/[slug].vue              # Public persona detail page
    view/[id].vue             # Public transcript viewer (metered)
    admin/                    # Admin panel (requires admin role)
      index.vue               # New Transcript creation
      term-search.vue         # Term Search
      transcripts/            # Transcript listing & detail
      personas/               # Persona listing & detail (slug/image management)
      markets/                # Kalshi markets listing & detail
  composables/                # API interaction layer
    useAuthFetch.ts           # Authenticated fetch wrapper
    useJobProgress.ts         # SSE job streaming
    useAnalysis.ts            # Term search & analysis API
    usePersonas.ts            # Persona CRUD API
    useKalshi.ts              # Kalshi API
    useFileTree.ts            # Folder/transcript management
    useAuth.ts                # Authentication state (login + signup)
    useReads.ts               # Free tier read metering
  components/                 # Reusable components
    FileTree/                 # Sidebar file tree (FileTree.vue, FileTreeFolder.vue, FileTreeItem.vue)
    TermSearch.vue            # Term search interface
    TermSection.vue           # Per-market term analysis display
    SpeakerSelector.vue       # Multi-select speaker picker
  layouts/
    default.vue               # Admin layout with fixed sidebar
    saas.vue                  # Client-facing layout with top nav bar
    public.vue                # Minimal layout for transcript viewer (no nav)
  middleware/
    auth.global.ts            # Three-tier auth guard (public/client/admin)

backend/                      # FastAPI backend
  main.py                     # App entry point, per-router auth registration
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
    kalshi.py                 # /api/kalshi/* - Series, events, markets
    personas.py               # /api/personas/* - Persona CRUD, aliases
    public.py                 # /api/public/* - Unauthenticated personas, transcripts, read metering
  services/                   # Business logic
    job_service.py            # Job lifecycle, SSE events
    transcript_service.py     # Transcript DB operations
    transcription_service.py  # Gemini transcription
    download_service.py       # yt-dlp audio download
    speaker_service.py        # Speaker extraction & storage
    folder_service.py         # Folder hierarchy operations
    persona_service.py        # Persona DB operations, public queries, speaker normalization
    kalshi_service.py         # Kalshi API client, market analysis
    youtube_service.py        # YouTube metadata via yt-dlp
  models/                     # Pydantic request/response models
    job.py, transcript.py, folder.py, analysis.py,
    speaker.py, persona.py, kalshi.py, video.py
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
| Transcript Generation | `docs/transcripts.md` | YouTube → yt-dlp → Gemini → DB pipeline with SSE progress. Includes public viewer with speaker normalization and read metering |
| Term Search | `docs/term-search.md` | Frequency analysis, context search, n-grams across transcripts |
| Personas | `docs/personas.md` | Speaker identity management with aliases, public directory, slug/image publishing |
| Markets (Kalshi) | `docs/markets.md` | Mentions markets: Series → Events → Markets, custom_strike.Word, analysis |
| Sidebar & Directory | `docs/sidebar.md` | FileTree component, folder hierarchy, drag-and-drop |

## Mandatory: Update Documentation on Feature Changes

When you edit code that belongs to a feature, you MUST also update the corresponding documentation file in `docs/`. This is not optional.

- Transcript generation changes → update `docs/transcripts.md`
- Term search changes → update `docs/term-search.md`
- Persona changes → update `docs/personas.md`
- Markets/Kalshi changes → update `docs/markets.md`
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
| `personas` | Speaker identities (name, description, slug, image_url). Slug acts as publish flag for public directory |
| `persona_aliases` | Aliases for a persona (unique alias text, FK → personas CASCADE) |

### SaaS Tables

| Table | Purpose |
|-------|---------|
| `profiles` | User profiles linked to `auth.users(id)`. Stores `role` ('admin' or 'client'). Auto-created via DB trigger on signup |
| `transcript_reads` | Tracks per-user transcript reads for free tier metering. UNIQUE(user_id, transcript_id) so re-reads don't count |

### Kalshi Tables

| Table | Purpose |
|-------|---------|
| `kalshi_series` | Series wrapper (ticker UNIQUE, title, category, tags, frequency, status) |
| `kalshi_events` | Events within a series (event_ticker UNIQUE, status, strike_date) |
| `kalshi_markets` | Markets within events (ticker UNIQUE, question, last_price, result) |
| `persona_kalshi_series` | Junction: persona ↔ series with optional folder_id scoping |
| `market_search_configs` | Auto-extracted search terms from market questions |
| `market_term_results` | Per-persona, per-term analysis results (mentions, trend, context) |

### Key Relationships

```
folders (parent_id) → folders           # Recursive hierarchy
transcripts.folder_id → folders
transcript_speakers → transcripts + speakers
persona_aliases → personas (CASCADE)
kalshi_events.series_id → kalshi_series
kalshi_markets.event_id → kalshi_events (CASCADE)
persona_kalshi_series → personas + kalshi_series + folders
market_search_configs.market_id → kalshi_markets (CASCADE)
market_term_results → kalshi_markets + personas
transcript_reads.transcript_id → transcripts (CASCADE)
profiles.id → auth.users (CASCADE)
```

## API Overview

Authenticated routes require Supabase JWT auth (`Authorization: Bearer <token>`). Auth is applied per-router in `main.py`, not globally.

| Prefix | Router | Auth | Purpose |
|--------|--------|------|---------|
| `/api/jobs` | `jobs.py` | Yes | Create jobs, SSE streaming, cancel |
| `/api/transcripts` | `transcripts.py` | Yes | List, get, update, delete transcripts |
| `/api/folders` | `folders.py` | Yes | Folder CRUD |
| `/api/analysis` | `analysis.py` | Yes | Term frequency, n-grams, context search, speakers |
| `/api/video` | `video.py` | Yes | YouTube video metadata |
| `/api/playlist` | `playlist.py` | Yes | YouTube playlist metadata |
| `/api/kalshi` | `kalshi.py` | Yes | Series/events/markets CRUD, analysis |
| `/api/personas` | `personas.py` | Yes | Persona CRUD, alias management |
| `/api/public` | `public.py` | **No** | Public persona directory, transcript viewer, read metering |

## Key Conventions & Gotchas

- **Python 3 binary**: Use `python3`, not `python`
- **FastAPI route ordering**: Static routes (`/series/search`) MUST be defined BEFORE parameterized routes (`/series/{series_id}`) to avoid path conflicts
- **Supabase client**: Use `from backend.core.database import supabase` — singleton client
- **Auth**: Authenticated endpoints use `require_auth` dependency (per-router in main.py, not global). SSE streams accept `?token=` query param. Public routes (`/api/public/*`) have no auth. Frontend auth middleware has three tiers: public routes (`/`, `/p/*`, `/view/*`, `/login`, `/signup`) skip auth; `/admin/*` requires session + `profiles.role === 'admin'`; other routes require any session
- **User roles**: `profiles` table stores role ('admin' or 'client'). Auto-created on signup via DB trigger. Frontend fetches role via `GET /api/public/profile` (Bearer token). To make a user admin: `UPDATE profiles SET role = 'admin' WHERE id = '<user-uuid>'`
- **Persona publishing**: Personas with a non-null `slug` are "published" and appear in the public directory. Personas without a slug are admin-only/draft
- **Nuxt UI**: Use Nuxt UI components (UButton, UBadge, UModal, etc.), not raw HTML elements
- **Composables pattern**: All API calls go through composables in `app/composables/`, never direct fetch from pages
- **Kalshi API**: Two base URLs — v2 (`https://api.elections.kalshi.com/trade-api/v2`) for series/events/markets CRUD, v1 search (`https://api.elections.kalshi.com/v1/search`) for browsing open events by tag. Unauthenticated read-only. Scoped to `category=Mentions` only
- **Market resolution**: Kalshi provides explicit `result` field ("yes"/"no"/"") — no price-threshold heuristic needed
- **Search term extraction**: Uses `custom_strike.Word` from Kalshi API (e.g., `{"Word": "Shutdown / Shut Down"}`). Compound terms split on " / ". Falls back to `parse_market_criteria()` regex
- **Speaker regex**: Pattern `^([A-Z0-9][\w\s\-'._()]{1,60}?):\s*(.*)$` — supports "Name:", "SPEAKER_00:", etc.
- **Idempotent upserts**: Kalshi events/markets use `event_ticker`/`ticker` as unique keys
- **Kalshi event browsing**: Markets listing page fetches open Mentions events from Kalshi v1 search API (`/api/kalshi/series/browse`), grouped by tag (Politicians, Earnings, Sports). No manual add/delete. Events are lazily upserted into DB on first detail page visit via `ensure_event(event_ticker)`. Detail pages use event_ticker routing (`/markets/{event_ticker}`)
- **Mandatory CLAUDE.md updates**: Any code change that affects project structure, conventions, API endpoints, database schema, key files, or development workflow MUST be reflected in this CLAUDE.md file

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
