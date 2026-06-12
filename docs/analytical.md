# Analytical Data Procurement

Deep analytical system for predicting word choices based on three pillars: preceding context (news + Truth Social), event context (where/how the speech happens), and past transcripts (baseline rhetoric).

## Architecture

Procurement uses **real, date-rangeable sources** behind a modular scraper
registry (`backend/services/scrapers/`):

- **Truth Social** — real @realDonaldTrump posts via the public Truth Social
  (Mastodon) API, credential-free using `curl_cffi` Chrome-TLS impersonation to
  pass Cloudflare. Paginates back to any start date.
- **Fox News** — articles via Fox's dated HTML sitemap
  (`/html-sitemap/{year}/{month}/{day}`), body-extracted with `trafilatura`.
  The only free route that reliably reaches back to January.

Each source is one `BaseScraper` subclass registered in `scrapers/__init__.SCRAPERS`;
adding an outlet (GDELT, a paid API, CNN, …) is one new module + one registry
line. The orchestrator (`analytical_procurement_service.py`) owns the
`procurement_runs` lifecycle — bulk upsert, true insert-vs-update counting, a
live progress heartbeat, and `cancel_requested` polling.

> Legacy note: the event-tag auto-classifier still uses DuckDuckGo (`ddgs`).
> News/Truth Social procurement no longer uses DDG.

### Data Flow

```
Analytical page (manual date-range scrape)   APScheduler (Fox: 6h, Truth Social: 12h, rolling 2-day window)
                       \                     /
                        v                   v
              analytical_procurement_service.run_scrape(source_type, persona, start, end)
                        |
                        v
         scrapers/{truth_social,fox_news}.py  → ScrapedItem stream
                        |
              chunked bulk upsert + dedup + progress heartbeat + cancel poll
                        |
                        v
        analytical.truth_social_posts / analytical.news_items
                        |
                        v
        Context window computation (aggregates data preceding each transcript)
```

## Database Tables

### `analytical_news_items`
Real news articles (currently Fox News via the dated sitemap).
- Dedup: `UNIQUE(persona_id, url)`
- Key fields: `title`, `body` (extracted article text, up to 5000 chars), `url`, `source_name` (e.g. "Fox News"), `source_domain` (e.g. "foxnews.com"), `published_at`, `procurement_source` ("fox_sitemap")
- Indexes: `(persona_id, source_domain)` for outlet filtering, `(persona_id, published_at DESC)` for range reads

### `analytical_truth_social_posts`
Real @realDonaldTrump posts via the public Truth Social (Mastodon) API.
- Dedup: `UNIQUE(persona_id, external_id)` where `external_id` = the stable Mastodon post id (closes the old nullable-hash dedup hole)
- Key fields: `content` (HTML-stripped), `post_url` (truthsocial.com permalink), `posted_at`, `media_urls`, `engagement` (replies/reblogs/favourites/up/down), **`is_retruth`** (reblog flag), `source` ("truthsocial")
- Index: `(persona_id, posted_at DESC)` for range reads

### `analytical_event_tags`
Per-transcript metadata bundle: event classification + location + timing. One row per transcript.
- Constraint: `UNIQUE(transcript_id)`
- **Surfaced fields (API + UI + persona export):** `event_type`, `city`, `state`, `country`, `venue`, `event_time`, plus `classification_source` (provenance only).
- Event types (16): `rally`, `press_conference`, `press_briefing`, `interview`, `prepared_remarks`, `signing_ceremony`, `bilateral_meeting`, `cabinet_meeting`, `reception`, `ceremony`, `summit`, `roundtable`, `announcement`, `greeting`, `troop_address`, `other`
- Classification sources: `manual`, `auto_ddgs`, `auto_llm`
- Location: `city`, `state`, `country`, `venue` (free-text, supports room-level detail like "Oval Office, The White House")
- Timing: `event_time` (timestamptz — from yt-dlp `release_timestamp` for livestream VODs, else the LLM-extracted full datetime, else upload `timestamp`)
- **Vestigial columns (still in the DB, no longer extracted or surfaced):** `audience_type`, `event_time_local`, `confidence`, `interviewer`, `network`, `is_teleprompter`, `notes`. The `auto_ddgs` keyword classifier may still write `network`/`audience_type`, but the `EventTag` API model drops them. Safe to drop in a future cleanup migration.

### `analytical_context_windows`
Pre-speech atmosphere snapshots aggregating news + Truth Social data.
- Constraint: `UNIQUE(transcript_id, persona_id)`
- Computed from the N-hour window before a transcript's `upload_date`
- Stores: counts, sentiment averages, top topics

### `analytical_procurement_runs`
Audit + live-status trail for all procurement operations.
- Source types: `truth_social`, `news_fox`, `news_ddgs`, `news_gdelt`, `news_newsapi`, `event_tag_auto`, `metadata_backfill`
- Tracks: `items_found`, `items_new`, `items_skipped`, `details` (JSONB), plus live `current_item_index`/`current_item_name`, `prompt_tokens`/`completion_tokens`, `cancel_requested`. Scrape runs now populate the live-progress fields (previously only metadata runs did).
- Statuses: `running`, `completed`, `failed`, `cancelled`

## API Endpoints

All admin-only under `/api/analytical/`.

### Scrape (procurement trigger)
| Method | Path | Description |
|--------|------|-------------|
| POST | `/scrape` | Start a date-ranged scrape in the background. Body: `{ persona_id, source_type: "truth_social"\|"news_fox", start_date, end_date? }`. Returns the **real** `run_id` for live tracking. |
| POST | `/scrape-sync` | Same body, runs synchronously (small ranges / testing). |

### News
| Method | Path | Description |
|--------|------|-------------|
| GET | `/news?persona_id=...&days=7&limit=100&start=&end=&source=` | List news items. `start`/`end` (ISO) select an explicit window; `source` filters by outlet (e.g. `foxnews.com` or `Fox News`). |

### Truth Social
| Method | Path | Description |
|--------|------|-------------|
| GET | `/truth-social?persona_id=...&days=7&limit=100&start=&end=` | List posts. `start`/`end` (ISO) select an explicit window. |

### Event Tags
| Method | Path | Description |
|--------|------|-------------|
| GET | `/event-tags?event_type=rally&limit=100` | List tags |
| GET | `/event-tags/{transcript_id}` | Get tag for transcript |
| POST | `/event-tags` | Manual tag creation |
| PATCH | `/event-tags/{transcript_id}` | Update tag |
| DELETE | `/event-tags/{transcript_id}` | Delete tag |
| POST | `/event-tags/auto-tag/{persona_id}` | Bulk auto-classify via DDG |

### Context Windows
| Method | Path | Description |
|--------|------|-------------|
| GET | `/context-windows/{transcript_id}?persona_id=...` | Get computed window |
| POST | `/context-windows/compute/{transcript_id}?persona_id=...&hours_before=72` | Compute window |
| POST | `/context-windows/bulk-compute/{persona_id}` | Compute all windows |

### Metadata Backfill
| Method | Path | Description |
|--------|------|-------------|
| POST | `/metadata/backfill/{persona_id}?force=false&limit=N` | Re-extract the metadata bundle (event_type, location, venue, event_time + frozen context_window) for every transcript belonging to a persona. Skips rows with `classification_source='manual'` unless `force=true`. Records a `procurement_runs` row with `source_type='metadata_backfill'`. |

### Audit
| Method | Path | Description |
|--------|------|-------------|
| GET | `/procurement-runs?source_type=...&persona_id=...&limit=20` | List runs |

## Services

| File | Purpose |
|------|---------|
| `analytical_procurement_service.py` | Orchestrates scraper runs: run lifecycle, chunked bulk upsert, true insert/update counting, progress heartbeat, cancel polling. `start_run` / `execute_run` / `run_scrape`. |
| `scrapers/base.py` | `BaseScraper` ABC + `ScrapedItem` dataclass. |
| `scrapers/truth_social.py` | Real Truth Social posts (Mastodon API via `curl_cffi`). |
| `scrapers/fox_news.py` | Fox articles (dated sitemap crawl + `trafilatura` body extraction). |
| `scrapers/__init__.py` | `SCRAPERS` registry + `get_scraper(source_type)`. |
| `analytical_news_service.py` | News **read** helpers (date-range + outlet filter). |
| `analytical_truth_social_service.py` | Truth Social **read** helpers (date-range). |
| `analytical_event_tag_service.py` | Event tag CRUD + auto-classification via DDG |
| `analytical_context_service.py` | Context window computation + aggregation |

### Dependencies / env
- New Python deps: `curl_cffi` (Truth Social Cloudflare TLS), `trafilatura` (article extraction), `beautifulsoup4` + `lxml` (sitemap/HTML parsing). All in `backend/requirements.txt`.
- **No new env vars / no credentials** — Truth Social is read credential-free; Fox needs no key.

## Scheduler

Two background jobs (controlled by `ANALYTICAL_PROCUREMENT_ENABLED`) keep the
real sources current with a **rolling 2-day window** (the one-off Jan→now
backfill is triggered manually from the Analytical page):
- **Fox news**: every 6 hours → `run_scrape("news_fox", trump, now-2d, now)`
- **Truth Social**: every 12 hours → `run_scrape("truth_social", trump, now-2d, now)`

Jobs look up the Trump persona ID dynamically via `ilike("name", "%trump%")`.

## Analytical UI (`/admin/analytical`)

A dedicated, modular page for triggering + browsing procurement:
- **Persona picker** (defaults to the Trump persona).
- Two reusable `<AnalyticalSourcePanel>` instances (Truth Social, Fox News). Each
  wraps a date-range `<AnalyticalProcurementForm>`, a compact live-run banner with
  cancel, and a browsable result list (`<AnalyticalTruthSocialPostList>` /
  `<AnalyticalNewsItemList>`).
- A persona-scoped `<AnalyticalProcurementRunTable>` (the same component the
  Operations dashboard now uses — extracted from its old inline table).
- Composable `app/composables/useAnalyticalProcurement.ts` wraps `/scrape` +
  the read endpoints; run status/polling reuses `useProcurementRuns.ts`.

### Honest limitations
- Both sources are unofficial/unsupported — the Mastodon endpoint and Fox sitemap
  paths can change without notice (defensive parsers, pinned libs).
- Cloudflare is the single point of failure for Truth Social; large backfills are
  throttled (~1 req/s) to avoid temporary IP bans.
- Fox article bodies require a second fetch per URL; paywalled/video pages may
  extract poorly. GDELT/paid multi-outlet news is intentionally deferred (registry
  seam is in place).

## Event Auto-Classification

There are now two extraction paths:

### Primary: LLM extraction (runs after every new transcript)

`backend/services/metadata_extraction_service.py` is called from `jobs.py` after a transcript is saved. It performs two Gemini Flash calls per transcript:

1. **Location call** — sees title, description, DDG snippets ("Trump {title}", 10 results), and the first ~2000 chars of the transcript. Fills `city`, `state`, `country`, `venue`, and `event_datetime_utc` (a full ISO timestamp parsed from the inputs, used to derive `event_time`). Also returns `primary_source` + `reasoning` for diagnostics (logged into `procurement_runs.details`, not persisted). Venue extraction prioritizes DDG snippets (where room-level detail like "Brady Press Briefing Room" lives).
2. **event_type call** — title ONLY, classified via a 16-rule strict keyword map (rule order matters: ceremony triggers fire before prepared_remarks).

`compute_event_time` then sets `event_time` with priority: yt-dlp `release_timestamp` (if `was_live=True`) → the LLM-extracted `event_datetime_utc` → upload `timestamp`.

**Reliability:** both Gemini calls are wrapped in `with_retry` (retries 429/5xx/rate-limit) with a generous 120s timeout, and bulk backfills run at `BULK_CONCURRENCY=3` to avoid rate-limit storms. Any call that fails (timeout / error / empty / non-JSON) is logged at ERROR and recorded in `procurement_runs.details` as `action="llm_failed"` with the error reason — so an empty row is never mistaken for a clean extraction. (This replaced a silent-swallow bug where a hard 30s cap + no retry made every field come back null.)

All values are written with `classification_source='auto_llm'` and surfaced as **suggestions** in the UI — admin must confirm via the metadata edit modal on the transcript detail page.

Cost: ~$0.0004 per transcript at current Gemini Flash pricing (negligible for backfills).

### Bulk backfill

For an existing persona, `bulk_backfill_metadata(persona_id, force, limit)` in `metadata_extraction_service.py` iterates every transcript belonging to that persona (matched by speaker name), re-fetches yt-dlp info, calls the same `populate_for_transcript` helper that `jobs.py` uses, and writes a `procurement_runs` audit row. Reachable two ways:
- **UI**: persona detail page → "Backfill metadata" button (next to "Download all"). Shows a confirm dialog with the candidate count, then toasts the result.
- **API**: `POST /api/analytical/metadata/backfill/{persona_id}?force=...&limit=...` (sync; long-running for large personas).
- **CLI**: `python3 -m backend.scripts.backfill_metadata --persona-id <uuid>` (thin wrapper around the service, useful when the server isn't available).

Audit trail: query `analytical.procurement_runs` where `source_type='metadata_backfill'`. The `details` JSONB column holds a per-transcript breakdown.

### Operations dashboard

`/admin/operations` is a live status table backed by `GET /api/analytical/procurement-runs`. It polls every 4 seconds and surfaces:
- Per-run progress (items done / total + bar)
- Current item title and index for any `status='running'` run (powered by `procurement_runs.current_item_index` and `current_item_name`, which the bulk loop writes at the start of every transcript — also acts as a heartbeat via `updated_at`)
- ETA (linear extrapolation from elapsed time and items completed so far)
- Cumulative Gemini token totals (input + output) and a USD estimate

Token totals come from `procurement_runs.prompt_tokens` / `completion_tokens`, populated by accumulating `response.usage_metadata.prompt_token_count` / `candidates_token_count` from each Gemini Flash call. Cost estimate is derived in the frontend (`app/composables/useProcurementRuns.ts`) from a hard-coded pricing table — **update `GEMINI_PRICING` when Google changes Flash rates** (https://ai.google.dev/pricing).

The persona detail page also shows an inline pulse with the current progress + cost when a backfill for that persona is running, linking to `/admin/operations` for the full view.

### Run control

| Method | Path | Description |
|--------|------|-------------|
| POST | `/procurement-runs/{run_id}/cancel` | Request cancellation. Sets `cancel_requested=true`; the bulk loop polls this flag at the top of each iteration and exits cleanly with `status='cancelled'`. |
| POST | `/procurement-runs/reset-stale` | Find any `status='running'` row whose `updated_at` is older than `STALE_THRESHOLD_SECONDS` (2 min) and mark it cancelled. Use after a backend crash. Idempotent. |
| DELETE | `/procurement-runs/{run_id}` | Delete a procurement_run record. Refuses while `status='running'` — cancel first. |

The Operations page exposes all three: per-row **Cancel** button (for running rows) or **Delete** button (for terminal rows), plus a top-of-page **Reset stale** button. New `status` value `cancelled` joins `running`/`completed`/`failed`.

### Fallback: DDG keyword classifier

`auto_tag_transcript` in `analytical_event_tag_service.py` remains as a fallback / bulk-tagging path. It runs only when invoked via `POST /event-tags/auto-tag/{persona_id}` (no longer wired into transcript creation):
1. Gets the transcript's name/title
2. Searches DDG for `"Trump {title}"`
3. Combines all result snippets
4. Keyword-matches against the expanded event_type taxonomy
5. Inserts tag with `classification_source='auto_ddgs'`

## Configuration

| Env Var | Default | Description |
|---------|---------|-------------|
| `ANALYTICAL_PROCUREMENT_ENABLED` | `true` | Enable/disable scheduled procurement |
