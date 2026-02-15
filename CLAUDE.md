# Transcripts Generator

YouTube transcript analysis platform with prediction market integration and per-persona ML fine-tuning.

## Stack
- **Frontend:** Nuxt 3 (Vue 3) + Nuxt UI + Tailwind CSS → `app/`
- **Backend:** FastAPI (Python) + Pydantic → `backend/`
- **Database:** Supabase (PostgreSQL) → `supabase/migrations/`
- **ML:** MLX LoRA fine-tuning (Apple Silicon) → `models/`
- **External:** yt-dlp, Gemini Flash, Gamma API (Polymarket)

## Documentation

| Document | Content |
|----------|---------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System overview, directory layout, auth pattern, async patterns |
| [docs/DATABASE.md](docs/DATABASE.md) | Full schema reference with all tables and relationships |
| [docs/features/01-authentication.md](docs/features/01-authentication.md) | Supabase auth, JWT flow, route guards |
| [docs/features/02-transcription-pipeline.md](docs/features/02-transcription-pipeline.md) | Video download, Gemini transcription, job SSE streaming |
| [docs/features/03-transcript-viewer.md](docs/features/03-transcript-viewer.md) | List/detail views, search, speaker filtering |
| [docs/features/04-term-search.md](docs/features/04-term-search.md) | NLP analysis, n-grams, cached term search |
| [docs/features/05-persona-management.md](docs/features/05-persona-management.md) | Persona CRUD, aliases, market reprocessing |
| [docs/features/06-polymarket-integration.md](docs/features/06-polymarket-integration.md) | Gamma API, series/events/markets, term analysis |
| [docs/features/07-ml-training.md](docs/features/07-ml-training.md) | LoRA fine-tuning pipeline, inference |

## Mandatory Documentation Updates

**When you change code, update the relevant documentation file.** Use this mapping:

| Code area | Update this doc |
|-----------|----------------|
| `app/composables/useAuth.ts`, `app/middleware/`, `backend/core/auth.py` | `docs/features/01-authentication.md` |
| `app/pages/index.vue`, `app/components/VideoPreview.vue`, `app/components/BatchUrlInput.vue`, `app/components/PlaylistSelector.vue`, `app/components/JobProgress.vue`, `app/composables/useJobProgress.ts`, `backend/routers/jobs.py`, `backend/routers/video.py`, `backend/routers/playlist.py`, `backend/services/job_service.py`, `backend/services/youtube_service.py`, `backend/services/transcription_service.py`, `backend/services/download_service.py` | `docs/features/02-transcription-pipeline.md` |
| `app/pages/transcripts/`, `backend/routers/transcripts.py`, `backend/services/transcript_service.py` | `docs/features/03-transcript-viewer.md` |
| `app/pages/term-search.vue`, `app/components/TermSearch.vue`, `app/components/SpeakerSelector.vue`, `app/composables/useAnalysis.ts`, `backend/routers/analysis.py`, `backend/utils/nlp.py` | `docs/features/04-term-search.md` |
| `app/pages/personas/`, `app/composables/usePersonas.ts`, `backend/routers/personas.py`, `backend/services/persona_service.py` | `docs/features/05-persona-management.md` |
| `app/pages/events/`, `app/components/TermSection.vue`, `app/composables/usePolymarket.ts`, `backend/routers/polymarket.py`, `backend/services/polymarket_service.py` | `docs/features/06-polymarket-integration.md` |
| `app/pages/model.vue`, `app/pages/personas/[id]/model.vue`, `app/components/ModelTrainingPanel.vue`, `app/composables/useMLTraining.ts`, `backend/routers/ml_training.py`, `backend/services/ml_training_service.py`, `backend/services/ml_processing_service.py` | `docs/features/07-ml-training.md` |
| `supabase/migrations/`, `utils/db_refrence.sql` | `docs/DATABASE.md` |
| `backend/main.py`, `backend/config.py`, `backend/core/`, `nuxt.config.ts`, `app/layouts/` | `docs/ARCHITECTURE.md` |

## Key Conventions

- **Python 3** is available only as `python3`, not `python`
- **Static routes before parameterized routes** in FastAPI routers (e.g., `/series/search` before `/series/{series_id}`)
- **Nuxt UI components** — use UButton, UBadge, UModal, UInput, USelectMenu, UCard, UAlert, etc.
- **useAuthFetch** for all API calls — never use raw `$fetch` or `useFetch` for backend endpoints
- **SSE auth** — pass token as `?token=` query param (EventSource cannot set headers)
- **Supabase service key** on backend, **publishable key** on frontend
- **Schema reference** — `utils/db_refrence.sql` is for context only, not executable. Actual migrations in `supabase/migrations/`
- **Series → Events → Markets** hierarchy in Polymarket. Series API returns events WITHOUT nested markets; fetch each event individually for market data.
- **Resolution logic** — closed market with `outcome_prices[0] >= 0.95` → YES, `[1] >= 0.95` → NO

## Development

```bash
# Start both servers (opens Terminal tabs)
./start_dev.sh

# Or manually:
# Backend (port 8001)
source backend/venv/bin/activate && uvicorn backend.main:app --host 0.0.0.0 --port 8001 --reload

# Frontend (port 3000)
npm run dev
```
