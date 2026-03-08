# Transcript Analysis Platform

A tool for transcribing YouTube videos (primarily press briefings), analyzing term frequency across transcripts, and tracking Kalshi prediction markets tied to speaker mentions. Includes a public-facing website with Stripe-powered paywall.

## Tech Stack

- **Frontend**: Nuxt 3 (Vue 3 + TypeScript) in `app/`
- **Backend**: FastAPI (Python 3) in `backend/`
- **Database**: Supabase (PostgreSQL)
- **Payments**: Stripe (monthly subscription)
- **Transcription**: Google Gemini 2.0 Flash (speaker diarization)
- **Audio Download**: yt-dlp
- **UI Components**: Nuxt UI (UButton, UBadge, UModal, UInput, USelectMenu, etc.)
- **ML Training**: MLX LoRA fine-tuning on Apple Silicon (per-persona)
- **SEO**: @nuxtjs/seo (robots, sitemap, schema-org, og-image), @nuxt/image
- **Blog**: @nuxt/content v3 (markdown in `content/blog/`)

## Project Structure

```
app/                          # Nuxt 3 frontend
  pages/                      # Route pages
    index.vue                 # Public personas grid
    login.vue                 # Authentication
    signup.vue                # User registration
    pricing.vue               # Subscription pricing
    account.vue               # User account & subscription management
    personas/[slug].vue       # Public persona detail & transcript listing
    transcripts/[id].vue      # Public transcript viewer
    blog/                     # Blog pages (public)
      index.vue               # Blog listing
      [...slug].vue           # Individual blog post
    admin/                    # Admin-only pages (require admin role)
      index.vue               # New Transcript creation
      term-search.vue         # Term Search
      transcripts/            # Admin transcript listing & detail
      personas/               # Admin persona listing & detail
      markets/                # Kalshi markets listing & detail
  composables/                # API interaction layer
    useAuthFetch.ts           # Authenticated fetch wrapper (admin)
    usePublicApi.ts           # Public fetch wrapper (attaches token if logged in)
    useSubscription.ts        # Stripe subscription state management
    useJobProgress.ts         # SSE job streaming
    useAnalysis.ts            # Term search & analysis API
    usePersonas.ts            # Persona CRUD API
    useKalshi.ts              # Kalshi API
    useFileTree.ts            # Folder/transcript management
    useAuth.ts                # Authentication state
  components/                 # Reusable components
    FileTree/                 # Sidebar file tree (FileTree.vue, FileTreeFolder.vue, FileTreeItem.vue)
    TermSearch.vue            # Term search interface
    TermSection.vue           # Per-market term analysis display
    SpeakerSelector.vue       # Multi-select speaker picker
    OgImage/                  # Dynamic OG image templates (nuxt-og-image)
      OgImageDefault.vue      # Default branded OG image
      OgImagePersona.vue      # Persona-specific OG image
      OgImageBlog.vue         # Blog post OG image
  layouts/
    default.vue               # Public layout with top navbar
    admin.vue                 # Admin layout with fixed sidebar
  middleware/
    auth.global.ts            # Global auth guard (public/admin/user zones)

backend/                      # FastAPI backend
  main.py                     # App entry point, per-router auth, router registration
  config.py                   # Settings from .env (Supabase, Gemini, Stripe, CORS)
  core/
    auth.py                   # Auth dependencies (require_admin, optional_auth, require_user_auth)
    database.py               # Supabase client, caching helpers
    process_tracker.py        # Subprocess termination tracking
  routers/                    # API route handlers
    jobs.py                   # /api/jobs/* - Job creation, SSE streaming (admin)
    transcripts.py            # /api/transcripts/* - Transcript CRUD (admin)
    folders.py                # /api/folders/* - Folder CRUD (admin)
    analysis.py               # /api/analysis/* - Term search, n-grams, speakers (admin)
    video.py                  # /api/video/* - YouTube metadata (admin)
    playlist.py               # /api/playlist/* - Playlist metadata (admin)
    channel.py                # /api/channel/* - YouTube channel video listing (admin)
    kalshi.py                 # /api/kalshi/* - Series, events, markets (admin)
    personas.py               # /api/personas/* - Persona CRUD, aliases (admin)
    public.py                 # /api/public/* - Public personas & transcripts (no auth)
    stripe_router.py          # /api/stripe/* - Checkout, webhook, subscription
  services/                   # Business logic
    job_service.py            # Job lifecycle, SSE events
    transcript_service.py     # Transcript DB operations
    transcription_service.py  # Gemini transcription
    download_service.py       # yt-dlp audio download
    speaker_service.py        # Speaker extraction & storage
    folder_service.py         # Folder hierarchy operations
    persona_service.py        # Persona DB operations
    kalshi_service.py         # Kalshi API client, market analysis
    youtube_service.py        # YouTube metadata via yt-dlp
    public_service.py         # Public data access, subscription checks
    stripe_service.py         # Stripe API integration
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

content/                        # @nuxt/content markdown files
  blog/                         # Blog posts (markdown with frontmatter)

content.config.ts               # Content collections config (blog schema)

docs/                         # Feature documentation (see below)
```

## Features & Documentation

Each feature has detailed documentation in `docs/`. Read the relevant file before modifying feature code.

| Feature | Doc File | Description |
|---------|----------|-------------|
| Public Site & Paywall | `docs/public-site.md` | Public website, Stripe subscription, paywall controls |
| Transcript Generation | `docs/transcripts.md` | YouTube → yt-dlp → Gemini → DB pipeline with SSE progress |
| Term Search | `docs/term-search.md` | Frequency analysis, context search, n-grams across transcripts |
| Personas | `docs/personas.md` | Speaker identity management with aliases, Kalshi links |
| Markets (Kalshi) | `docs/markets.md` | Mentions markets: Series → Events → Markets, custom_strike.Word, analysis |
| Sidebar & Directory | `docs/sidebar.md` | FileTree component, folder hierarchy, drag-and-drop |
| SEO & Blog | `docs/seo.md` | OG images, structured data, sitemap, @nuxt/content blog |

## Mandatory: Update Documentation on Feature Changes

When you edit code that belongs to a feature, you MUST also update the corresponding documentation file in `docs/`. This is not optional.

- Transcript generation changes → update `docs/transcripts.md`
- Term search changes → update `docs/term-search.md`
- Persona changes → update `docs/personas.md`
- Markets/Kalshi changes → update `docs/markets.md`
- Sidebar/FileTree/folder changes → update `docs/sidebar.md`
- SEO/OG images/blog/sitemap changes → update `docs/seo.md`
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
| `transcripts` | Full transcript text, youtube_url, name, folder_id, upload_date, is_public, is_premium |
| `profiles` | User profiles with role (admin/client), stripe_customer_id |
| `subscriptions` | Stripe subscription tracking (user_id, status, period) |
| `jobs` | Job progress tracking (status, stage_progress, cancel_requested) |
| `folders` | Hierarchical folders (self-referencing parent_id) |
| `speakers` | Normalized speaker names (unique) |
| `transcript_speakers` | Junction: transcript ↔ speaker with segment_count |
| `analysis_cache` | Cached analysis results with TTL (cache_key, result JSONB, expires_at) |

### Persona Tables

| Table | Purpose |
|-------|---------|
| `personas` | Speaker identities (name, description, slug, image_url) |
| `persona_aliases` | Aliases for a persona (unique alias text, FK → personas CASCADE) |

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
```

## API Overview

Admin routes require admin role. Public routes are unauthenticated or use optional auth. Stripe routes use user-level auth.

| Prefix | Router | Auth | Purpose |
|--------|--------|------|---------|
| `/api/jobs` | `jobs.py` | Admin | Create jobs, SSE streaming, cancel |
| `/api/transcripts` | `transcripts.py` | Admin | List, get, update, delete transcripts |
| `/api/folders` | `folders.py` | Admin | Folder CRUD |
| `/api/analysis` | `analysis.py` | Admin | Term frequency, n-grams, context search, speakers |
| `/api/video` | `video.py` | Admin | YouTube video metadata |
| `/api/playlist` | `playlist.py` | Admin | YouTube playlist metadata |
| `/api/channel` | `channel.py` | Admin | YouTube channel video listing |
| `/api/kalshi` | `kalshi.py` | Admin | Series/events/markets CRUD, analysis |
| `/api/personas` | `personas.py` | Admin | Persona CRUD, alias management |
| `/api/public` | `public.py` | None/Optional | Public personas & transcript browsing |
| `/api/stripe` | `stripe_router.py` | User/None | Checkout, webhook, subscription, portal |
| `/api/profile` | `profile.py` | User/None | Profile CRUD, signup init |

## Key Conventions & Gotchas

- **Python 3 binary**: Use `python3`, not `python`
- **FastAPI route ordering**: Static routes (`/series/search`) MUST be defined BEFORE parameterized routes (`/series/{series_id}`) to avoid path conflicts
- **Supabase client**: Use `from backend.core.database import supabase` — singleton client
- **Auth**: Admin routes use `require_admin` dependency (per-router in main.py). Public routes use `optional_auth` or no auth. Stripe routes use `require_user_auth`. SSE streams accept `?token=` query param
- **Admin pages**: All admin pages use `definePageMeta({ layout: 'admin' })` and live under `app/pages/admin/`
- **Public pages**: Public pages use the default layout and live at root level in `app/pages/`
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
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
STRIPE_PRICE_ID=...
```
