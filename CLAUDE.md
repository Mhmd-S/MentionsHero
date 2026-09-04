# Transcript Analysis Platform

A tool for transcribing YouTube videos (primarily press briefings), analyzing term frequency across transcripts, and tracking prediction markets (Kalshi & Polymarket) tied to speaker mentions.

**The public site is free, anonymous and transcripts-only.** No accounts, no subscription, no paywall, no public markets pages. Auth exists for exactly one purpose: gating `/admin`. The markets tooling is admin-only.

## Tech Stack

- **Frontend**: Nuxt 3 (Vue 3 + TypeScript) in `app/`
- **Backend**: FastAPI (Python 3) in `backend/`
- **Database**: Supabase (PostgreSQL)
- **Auth**: `@nuxtjs/supabase` (cookie sessions, SSR) + local JWKS verification in FastAPI
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
    index.vue                 # Public speaker list
    login.vue                 # Admin sign-in (the ONLY auth page)
    personas/[slug].vue       # Public persona detail & transcript listing
    transcripts/[id].vue      # Public transcript viewer
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
    usePublicApi.ts           # Public fetch wrapper (anonymous; a plain $fetch seam)
    useJobProgress.ts         # SSE job streaming
    useAnalysis.ts            # Term search & analysis API
    usePersonas.ts            # Persona CRUD API
    useKalshi.ts              # Kalshi API
    usePolymarket.ts          # Polymarket API
    useFileTree.ts            # Folder/transcript management
    useAutoTranscription.ts   # Auto-transcription source management
    useAuth.ts                # Auth facade over @nuxtjs/supabase (login/logout/role)
    useProfile.ts             # profiles row + role (role is not a JWT claim)
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
  config.py                   # Settings from .env (Supabase, Gemini, CORS)
  scheduler.py                # APScheduler background scheduler for auto-transcription
  core/
    auth.py                   # Auth dependencies (require_admin, require_user_auth, require_auth)
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
    public.py                 # /api/public/* - Public personas & transcripts (no auth, ever)
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
    public_service.py         # Public data access (no gating)
    profile_service.py        # Profile reads/writes, self-healing ensure_profile()
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
| Public Site | `docs/public-site.md` | Public website (free & anonymous), admin auth model, visibility controls |
| Transcript Generation | `docs/transcripts.md` | YouTube → yt-dlp → Gemini → DB pipeline with SSE progress |
| Term Search | `docs/term-search.md` | Frequency analysis, context search, n-grams across transcripts |
| Personas | `docs/personas.md` | Speaker identity management with aliases, Kalshi links |
| Markets (Kalshi) | `docs/markets.md` | **Admin-only.** Mentions markets: Series → Events → Markets, custom_strike.Word, analysis |
| Sidebar & Directory | `docs/sidebar.md` | FileTree component, folder hierarchy, drag-and-drop |
| SEO & Blog | `docs/seo.md` | OG images, canonicals, structured data, sitemap, RSS feed, @nuxt/content blog |
| Auto-Transcription | `docs/auto-transcription.md` | Periodic YouTube channel/playlist monitoring & auto-transcription |
| Design System | `docs/design-system.md` | Colour scales, type utilities, the nine shared `ui/` components, icon rule |

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
| `transcripts` | Full transcript text, youtube_url, name, folder_id, upload_date, is_public. (`is_premium` still exists but is legacy — the public API ignores it) |
| `profiles` | User profiles with role (admin/client). RLS on, SELECT-own-row only; rows created by the `on_auth_user_created` trigger |
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

Admin routes require admin role. Public routes are unauthenticated, full stop — there is no optional auth and nothing widens for a signed-in visitor.

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
| `/api/public` | `public.py` | None | Public personas & transcripts browsing |
| `/api/profile` | `profile.py` | User | GET the current user's profile. Its only consumer is the admin role check |

## Key Conventions & Gotchas

- **Python 3 binary**: Use `python3`, not `python`
- **FastAPI route ordering**: Static routes (`/series/search`) MUST be defined BEFORE parameterized routes (`/series/{series_id}`) to avoid path conflicts
- **Supabase client**: Use `from backend.core.database import supabase` — singleton client
- **Auth**: Admin routes use `require_admin` (per-router in main.py). `/api/public/**` takes no auth at all — there is no `optional_auth` any more, because nothing widens for a signed-in visitor. `/api/profile` uses `require_user_auth` and exists only so the admin UI can read `profiles.role`. SSE streams accept `?token=` query param
- **Auth is `@nuxtjs/supabase`**: it owns the client, session and SSR cookie hydration. `useSupabaseUser()` returns **JWT claims, not a `User`** — the id is `user.sub`. Never re-add a local `useSupabaseClient()`; it collides with the module's auto-import and writes no cookies
- **`supabase.redirect: false`**: the module's `global-auth` middleware is off. `app/middleware/auth.global.ts` is the only thing that redirects, and it guards exactly one prefix: `/admin`. The site is public by default, so an allow-list is the wrong shape
- **Profile rows are created by the database**, by the `on_auth_user_created` trigger, never by the browser. `profile_service.ensure_profile()` is the fallback. Never use `.single()` on `profiles` — a missing row 500s the admin role check. **Admin accounts are created in the Supabase dashboard**: there is no signup page, no email-confirmation route and no password reset in the app
- **Backend verifies tokens locally** against the project JWKS (ES256), cached in-process. Never reintroduce a per-request `supabase.auth.get_user(token)`. The admin role comes from the DB, never from a token claim — `user_metadata` is client-writable
- **Nuxt needs `NUXT_PUBLIC_SUPABASE_URL`/`_KEY` at runtime**: `@nuxtjs/supabase` resolves url/key at BUILD time, and Nuxt only overrides them from env names derived from the config path. The image has no `.env` (`.dockerignore`) and no build ARGs, so nothing is baked in — `start.sh` derives the `NUXT_PUBLIC_*` names from `SUPABASE_URL`/`SUPABASE_KEY` before launching Nuxt. Without that, every SSR page 500s with "Your project's URL and Key are required" while `/rss.xml` and `/_nuxt_icon` still return 200. `SUPABASE_KEY` is the anon/publishable key — `SUPABASE_SERVICE_KEY` is a different value and does not substitute
- **`start.sh` never exits on bad config**: it warns and starts Nuxt anyway. Exiting turns a partial outage into a container restart loop in which nothing serves at all
- **`SUPABASE_URL` is validated in `backend/config.py`**: stray characters appended to it fail deep in the stack as `'idna' codec ... label too long`, which names neither the setting nor the service, and 500s every `/api/**` route while `/health` stays green. The validator recovers the canonical `https://<ref>.supabase.co` and logs an error rather than raising (raising would restart-loop the container)
- **Nothing on the public site is gated.** No paywall, no accounts, no `is_locked`/`is_limited`/`isSubscribed`. `is_premium` survives as a `transcripts` column and an admin toggle, but the public API ignores it — do not re-add a read of it. If a feature needs a gate, that is a product decision, not a refactor
- **Admin pages**: All admin pages use `definePageMeta({ layout: 'admin' })` and live under `app/pages/admin/`
- **Public pages**: Public pages use the default layout and live at root level in `app/pages/`
- **Nuxt UI**: Use Nuxt UI components (UButton, UBadge, UModal, etc.), not raw HTML elements
- **Composables pattern**: All API calls go through composables in `app/composables/`, never direct fetch from pages
- **Kalshi API**: Two base URLs — v2 (`https://api.elections.kalshi.com/trade-api/v2`) for series/events/markets CRUD, v1 search (`https://api.elections.kalshi.com/v1/search`) for browsing open events by tag. Unauthenticated read-only. Scoped to `category=Mentions` only
- **Market resolution**: Kalshi provides explicit `result` field ("yes"/"no"/"") — no price-threshold heuristic needed
- **Search term extraction**: Uses `custom_strike.Word` from Kalshi API (e.g., `{"Word": "Shutdown / Shut Down"}`). Compound terms split on " / ". Falls back to `parse_market_criteria()` regex
- **Speaker regex**: Pattern `^([A-Z0-9][\w\s\-'._()]{1,60}?):\s*(.*)$` — supports "Name:", "SPEAKER_00:", etc.
- **Idempotent upserts**: Kalshi events/markets use `event_ticker`/`ticker` as unique keys
- **Markets are admin-only**: there is no public markets UI. `/markets`, `/api/public/markets*` and `usePublicMarkets.ts` were removed. `kalshi_events.show_public` / `poly_events.show_public` still exist and the admin still toggles them, but nothing reads them
- **Kalshi event browsing**: the admin markets listing fetches open Mentions events from the Kalshi v1 search API (`/api/kalshi/series/browse`), grouped by tag (Politicians, Earnings, Sports). No manual add/delete. Events are lazily upserted into DB on first detail page visit via `ensure_event(event_ticker)`. Detail pages use event_ticker routing (`/admin/markets/{event_ticker}`)
- **Polymarket API**: Gamma API (`https://gamma-api.polymarket.com`), unauthenticated read-only. Events discovered via admin keyword search (`_q` param), manually added to DB. No series concept — events directly contain markets. Slug-based identification. Pricing is 0-1 decimal (multiply by 100 for display). Resolution derived from `closed` + `outcomePrices`
- **Polymarket search terms**: Uses `groupItemTitle` (often the tracked term in multi-outcome events), falls back to `parse_market_criteria()` regex on question text. No `custom_strike.Word` equivalent
- **Markets UI**: Tabbed layout (Kalshi | Polymarket) on `/admin/markets`. Tab state persisted via `?tab=polymarket` query param. Kalshi detail at `/admin/markets/{event_ticker}`, Polymarket detail at `/admin/markets/poly/{event_id}`
- **Auto-transcription scheduler**: APScheduler `AsyncIOScheduler` starts via FastAPI lifespan in `main.py`. Disable with `AUTO_TRANSCRIPTION_ENABLED=false` env var. Scheduler state reconstructed from DB on restart. Multi-instance dedup prevents duplicate checks when running multiple replicas
- **SEO tags**: `canonical` is NOT a valid `useSeoMeta()` key — `nuxt-seo-utils` auto-injects `<link rel="canonical">` on every page; override with `useHead()` only where a route resolves under two URLs (a persona is reachable by slug or id). `defineOgImage()` already emits `twitter:card`/`twitter:image`; set alt once via its `alt` option, not `ogImageAlt`. `Organization`/`WebSite` schema live in `app/layouts/default.vue` — never redefine per page. See `docs/seo.md`
- **Icons are lucide only**: `i-lucide-*` everywhere, including the Nuxt UI icon map in `app/app.config.ts`. `@iconify-json/lucide` is installed and `icon.serverBundle: 'local'` bundles it for SSR, so nothing is fetched at runtime. Verify a name before using it — a wrong one renders a blank box: `node -e "console.log('menu' in require('./node_modules/@iconify-json/lucide/icons.json').icons)"`
- **`icon.localApiEndpoint` is `/_nuxt_icon`, NOT the default `/api/_nuxt_icon`**: Nitro *merges* route rules rather than letting a more specific key opt out, so `'/api/_nuxt_icon/**': {}` never excluded the icon endpoint from the `/api/**` FastAPI proxy — icon requests were proxied to the backend and 404'd, producing `[Icon] failed to load icon`. Never move it back under `/api`
- **Design system**: colours, type scale and the shared `app/components/ui/*` components are documented in `docs/design-system.md`. Amber (`mark`) means "a mention happened" and nothing else; green/red are reserved for market outcome and trend. Never write a raw Tailwind palette class
- **Persona slugs are mostly empty**: most `personas` rows have a NULL `slug`, and the UI links them as `slug || id`. Anything enumerating persona URLs (sitemap, canonicals) must use the same fallback or it will silently drop nearly every persona
- **Mandatory CLAUDE.md updates**: Any code change that affects project structure, conventions, API endpoints, database schema, key files, or development workflow MUST be reflected in this CLAUDE.md file

## Development

**Node 22+ is required.** `@supabase/supabase-js` needs a native `WebSocket`, which Node 20
does not have — on Node 20 every SSR page returns a bare 500 with no logged error. The
Dockerfile already uses Node 22; `package.json` pins `engines.node >= 22`. After switching
Node versions run `pnpm rebuild better-sqlite3`, or @nuxt/content will fail at runtime.

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
CORS_ORIGINS=https://mentionshero.com,https://www.mentionshero.com
SUPABASE_JWT_SECRET=...   # optional; only for projects still on the legacy HS256 secret
```

`SUPABASE_URL` and `SUPABASE_KEY` are read by `@nuxtjs/supabase` directly — they sit in the
module's own env fallback chain, so no `NUXT_PUBLIC_` rename is needed.

`SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are required — `Settings()` raises at import and the app never boots without them. `CORS_ORIGINS` accepts a comma-separated list or a JSON array; the field is annotated `NoDecode` so pydantic-settings doesn't JSON-decode it before `parse_cors_origins` runs.

## Deployment

Single container (`Dockerfile` → `start.sh`) on Railway: FastAPI on `:8001`, Nuxt on `:$PORT`. Nuxt proxies `/api/**` to `localhost:8001` via `routeRules` in `nuxt.config.ts`. `start.sh` supervises both processes — if either exits, the container exits non-zero so the platform restarts it. Never let Nuxt outlive FastAPI: it serves every page normally while all `/api/**` requests 502.
