# Architecture

## Stack

| Layer | Technology | Details |
|-------|-----------|---------|
| Frontend | Nuxt 3 (Vue 3) | `app/` directory, Nuxt UI components, Tailwind CSS |
| Backend | FastAPI (Python) | `backend/` directory, Pydantic models, async endpoints |
| Database | Supabase (PostgreSQL) | Hosted PostgreSQL with Row-Level Security |
| ML | MLX (Apple Silicon) | LoRA fine-tuning via `mlx_lm` subprocess |
| External | yt-dlp, Gemini Flash, Gamma API | Video download, transcription, prediction markets |

## Directory Layout

```
transcripts_generator/
├── app/                          # Nuxt 3 frontend
│   ├── components/               # Vue components (VideoPreview, JobProgress, etc.)
│   ├── composables/              # API wrappers (useAuth, useAuthFetch, useJobProgress, etc.)
│   ├── layouts/default.vue       # Sidebar navigation layout
│   ├── middleware/auth.global.ts  # Route guard — redirects unauthenticated to /login
│   ├── pages/                    # File-based routing
│   │   ├── index.vue             # Transcription pipeline (home page)
│   │   ├── login.vue             # Login form
│   │   ├── term-search.vue       # NLP term search & analysis
│   │   ├── model.vue             # ML model training
│   │   ├── transcripts/          # Transcript list & detail views
│   │   ├── personas/             # Persona management & detail
│   │   └── events/               # Polymarket series & event views
│   ├── plugins/auth.client.ts    # Initializes auth on app load
│   └── utils/supabase.ts         # Supabase client singleton
│
├── backend/                      # FastAPI backend
│   ├── main.py                   # App entry, CORS, router registration
│   ├── config.py                 # Settings from .env (pydantic-settings)
│   ├── core/
│   │   ├── auth.py               # require_auth dependency (JWT validation)
│   │   ├── database.py           # get_supabase() cached client, analysis cache helpers
│   │   └── exceptions.py         # Custom exception classes
│   ├── models/                   # Pydantic request/response models
│   ├── routers/                  # FastAPI route handlers (one per feature)
│   ├── services/                 # Business logic layer
│   ├── utils/
│   │   ├── nlp.py                # Term frequency, n-grams, context search
│   │   └── transcript_filter.py  # Transcript filtering utilities
│   └── configs/ml_default.yaml   # Default MLX training hyperparameters
│
├── models/                       # ML model artifacts (git-ignored)
│   └── personas/{id}/adapters/   # LoRA adapters per persona
│
├── supabase/migrations/          # SQL migration files (chronological)
├── utils/db_refrence.sql         # Full schema reference (not executable)
├── nuxt.config.ts                # Nuxt config — API proxy, runtime config
└── start_dev.sh                  # Launches backend + frontend in Terminal tabs
```

## Authentication Pattern

```
Browser → login.vue → Supabase Auth (email/password)
                          ↓
                     JWT session stored in localStorage
                          ↓
       auth.global.ts middleware checks session on every navigation
                          ↓
       useAuthFetch() adds Bearer token to all API calls
                          ↓
       FastAPI require_auth dependency validates JWT via Supabase
       (supports both Authorization header and ?token query param for SSE)
                          ↓
       On 401: frontend attempts token refresh, then logs out
```

**Key files:** `app/composables/useAuth.ts`, `app/composables/useAuthFetch.ts`, `backend/core/auth.py`

## API Proxy

Nuxt proxies `/api/**` requests to `http://localhost:8001/api/**` (configured in `nuxt.config.ts`). The backend runs on port 8001, frontend on port 3000.

## Router Registration Order

Routers are registered in `backend/main.py`. All routes are protected by `require_auth` as a global dependency.

**Registered routers** (in order): jobs, transcripts, folders, analysis, video, playlist, polymarket, personas, ml_training

**Important:** Static routes (e.g., `/series/search`) must be defined BEFORE parameterized routes (e.g., `/series/{series_id}`) within each router to avoid path conflicts.

## Async Patterns

### SSE Streaming (Server-Sent Events)
Used for real-time progress in jobs and ML training.

- **Job progress:** `GET /api/jobs/{job_id}/stream` — streams job status changes
- **Jobs list:** `GET /api/jobs/list/stream` — streams active jobs list updates
- **ML training:** `GET /api/ml-training/jobs/{job_id}/stream` — streams training iterations

**Pattern:** `threading.Event` per job for instant wake + 5s/30s timeout heartbeat. Token passed as query param since EventSource cannot set custom headers.

### Background Tasks
FastAPI `BackgroundTasks` for long-running operations (transcription pipeline, market analysis reprocessing, series backfill).

## Navigation Structure

Sidebar links (from `app/layouts/default.vue`):

| Label | Route | Icon | Feature |
|-------|-------|------|---------|
| New Transcript | `/` | plus-circle | Transcription pipeline |
| Term Search | `/term-search` | magnifying-glass | NLP analysis |
| Personas | `/personas` | user-group | Persona management |
| Events | `/events` | chart-bar | Polymarket integration |
| Model | `/model` | cpu-chip | ML training |

Sidebar also contains: FileTree component (folder browser), JobsSidebar component (active jobs list), Logout button.
