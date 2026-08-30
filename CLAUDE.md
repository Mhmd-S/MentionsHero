# Transcript Analysis Platform

A tool for transcribing YouTube videos (primarily press briefings), analyzing term frequency across transcripts, and tracking prediction markets (Kalshi & Polymarket) tied to speaker mentions. Includes a public-facing website with Stripe-powered paywall.

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
    markets/                  # Public markets pages (premium-gated analysis)
      index.vue               # Markets listing grouped by persona
      [slug].vue              # Persona markets detail
    blog/                     # Blog pages (public)
      index.vue               # Blog listing
      [...slug].vue           # Individual blog post
    admin/                    # Admin-only pages (require admin role)
      index.vue               # New Transcript creation
      auto-transcription.vue  # Auto-transcription source management
      term-search.vue         # Term Search
      transcripts/            # Admin transcript listing & detail
      personas/               # Admin persona listing & detail
      markets/                # Markets listing (Kalshi + Polymarket tabs) & detail
        poly/                 # Polymarket event detail pages
  composables/                # API interaction layer
    useAuthFetch.ts           # Authenticated fetch wrapper (admin)
    usePublicApi.ts           # Public fetch wrapper (attaches token if logged in)
    usePublicMarkets.ts       # Public markets API
    useSubscription.ts        # Stripe subscription state management
    useJobProgress.ts         # SSE job streaming
    useAnalysis.ts            # Term search & analysis API
    usePersonas.ts            # Persona CRUD API
    useKalshi.ts              # Kalshi API
    usePolymarket.ts          # Polymarket API
    useFileTree.ts            # Folder/transcript management
    useAutoTranscription.ts   # Auto-transcription source management
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
  scheduler.py                # APScheduler background scheduler for auto-transcription
  core/
    auth.py                   # Auth dependencies (require_admin, optional_auth, require_user_auth)
    concurrency.py            # Shared semaphores for job processing
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
    polymarket.py             # /api/polymarket/* - Polymarket events, markets (admin)
    personas.py               # /api/personas/* - Persona CRUD, aliases (admin)
    auto_transcription.py     # /api/auto-transcription/* - Auto-transcription sources & runs (admin)
    public.py                 # /api/public/* - Public personas, transcripts & markets (no auth)
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
    polymarket_service.py     # Polymarket API client, market analysis
    youtube_service.py        # YouTube metadata via yt-dlp
    public_service.py         # Public data access, subscription checks
    stripe_service.py         # Stripe API integration
    auto_transcription_service.py  # Auto-transcription check logic & CRUD
  models/                     # Pydantic request/response models
    job.py, transcript.py, folder.py, analysis.py, auto_transcription.py,
    speaker.py, persona.py, kalshi.py, polymarket.py, video.py
  utils/
    nlp.py                    # Term frequency, n-grams, text cleaning, context search
    transcript_filter.py      # Transcript parsing, highlighting, speaker extraction

utils/
  db_refrence.sql             # Database schema reference (read-only, not executable)

supabase/
  migrations/                 # SQL migration files

server/                         # Nitro server routes (root-level, outside app/)
  routes/
    rss.xml.ts                  # Blog RSS 2.0 feed at /rss.xml

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
| SEO & Blog | `docs/seo.md` | OG images, canonicals, structured data, sitemap, RSS feed, @nuxt/content blog |
| Auto-Transcription | `docs/auto-transcription.md` | Periodic YouTube channel/playlist monitoring & auto-transcription |

## Mandatory: Update Documentation on Feature Changes

When you edit code that belongs to a feature, you MUST also update the corresponding documentation file in `docs/`. This is not optional.

- Transcript generation changes → update `docs/transcripts.md`
- Term search changes → update `docs/term-search.md`
- Persona changes → update `docs/personas.md`
- Markets/Kalshi changes → update `docs/markets.md`
- Sidebar/FileTree/folder changes → update `docs/sidebar.md`
- SEO/OG images/blog/sitemap changes → update `docs/seo.md`
- Auto-transcription changes → update `docs/auto-transcription.md`
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
| `kalshi_events` | Events within a series (event_ticker UNIQUE, status, strike_date, show_public) |
| `kalshi_markets` | Markets within events (ticker UNIQUE, question, last_price, result) |
| `market_search_configs` | Auto-extracted search terms from Kalshi market questions |
| `market_term_results` | Per-persona, per-term analysis results for Kalshi (mentions, trend, context) |

### Polymarket Tables

| Table | Purpose |
|-------|---------|
| `poly_events` | Polymarket events (poly_id UNIQUE, slug UNIQUE, title, volume, liquidity, show_public) |
| `poly_markets` | Markets within events (poly_id UNIQUE, question, last_trade_price 0-1, result) |
| `poly_market_search_configs` | Search terms for Polymarket markets (from groupItemTitle or question) |
| `poly_market_term_results` | Per-persona, per-term analysis results for Polymarket |

### Auto-Transcription Tables

| Table | Purpose |
|-------|---------|
| `auto_sources` | YouTube channel/playlist → persona links (youtube_url UNIQUE, check_interval, title_filter) |
| `auto_runs` | History log of each automated check (status, videos_found/new/queued/skipped, details JSONB) |
| `auto_source_videos` | Per-source video tracking for dedup (auto_source_id + youtube_url UNIQUE) |

### Key Relationships

```
folders (parent_id) → folders           # Recursive hierarchy
transcripts.folder_id → folders
transcript_speakers → transcripts + speakers
persona_aliases → personas (CASCADE)
kalshi_events.series_id → kalshi_series
kalshi_markets.event_id → kalshi_events (CASCADE)
market_search_configs.market_id → kalshi_markets (CASCADE)
market_term_results → kalshi_markets + personas
poly_markets.event_id → poly_events (CASCADE)
poly_market_search_configs.market_id → poly_markets (CASCADE)
poly_market_term_results → poly_markets + personas
auto_sources.persona_id → personas (CASCADE)
auto_sources.folder_id → folders (SET NULL)
auto_runs.auto_source_id → auto_sources (CASCADE)
auto_source_videos.auto_source_id → auto_sources (CASCADE)
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
| `/api/polymarket` | `polymarket.py` | Admin | Polymarket events/markets, search, analysis |
| `/api/personas` | `personas.py` | Admin | Persona CRUD, alias management |
| `/api/auto-transcription` | `auto_transcription.py` | Admin | Auto-transcription sources, runs, manual trigger |
| `/api/public` | `public.py` | None/Optional | Public personas, transcripts & markets browsing |
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
- **Polymarket API**: Gamma API (`https://gamma-api.polymarket.com`), unauthenticated read-only. Events discovered via admin keyword search (`_q` param), manually added to DB. No series concept — events directly contain markets. Slug-based identification. Pricing is 0-1 decimal (multiply by 100 for display). Resolution derived from `closed` + `outcomePrices`
- **Polymarket search terms**: Uses `groupItemTitle` (often the tracked term in multi-outcome events), falls back to `parse_market_criteria()` regex on question text. No `custom_strike.Word` equivalent
- **Markets UI**: Tabbed layout (Kalshi | Polymarket) on `/admin/markets`. Tab state persisted via `?tab=polymarket` query param. Kalshi detail at `/admin/markets/{event_ticker}`, Polymarket detail at `/admin/markets/poly/{event_id}`
- **Auto-transcription scheduler**: APScheduler `AsyncIOScheduler` starts via FastAPI lifespan in `main.py`. Disable with `AUTO_TRANSCRIPTION_ENABLED=false` env var. Scheduler state reconstructed from DB on restart. Multi-instance dedup prevents duplicate checks when running multiple replicas
- **SEO tags**: `canonical` is NOT a valid `useSeoMeta()` key — `nuxt-seo-utils` auto-injects `<link rel="canonical">` on every page; override with `useHead()` only where a route resolves under two URLs (persona/markets slug-or-id). `defineOgImage()` already emits `twitter:card`/`twitter:image`; set alt once via its `alt` option, not `ogImageAlt`. `Organization`/`WebSite` schema live in `app/layouts/default.vue` — never redefine per page. See `docs/seo.md`
- **Persona slugs are mostly empty**: most `personas` rows have a NULL `slug`, and the UI links them as `slug || id`. Anything enumerating persona URLs (sitemap, canonicals) must use the same fallback or it will silently drop nearly every persona
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
CORS_ORIGINS=https://mentionshero.com,https://www.mentionshero.com
```

`SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are required — `Settings()` raises at import and the app never boots without them. `CORS_ORIGINS` accepts a comma-separated list or a JSON array; the field is annotated `NoDecode` so pydantic-settings doesn't JSON-decode it before `parse_cors_origins` runs.

## Deployment

Single container (`Dockerfile` → `start.sh`) on Railway: FastAPI on `:8001`, Nuxt on `:$PORT`. Nuxt proxies `/api/**` to `localhost:8001` via `routeRules` in `nuxt.config.ts`. `start.sh` supervises both processes — if either exits, the container exits non-zero so the platform restarts it. Never let Nuxt outlive FastAPI: it serves every page normally while all `/api/**` requests 502.
