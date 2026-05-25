# Analytical Data Procurement

Deep analytical system for predicting word choices based on three pillars: preceding context (news + Truth Social), event context (where/how the speech happens), and past transcripts (baseline rhetoric).

## Architecture

All data procurement uses DuckDuckGo Search (`ddgs` package). Tables are prefixed with `analytical_` to isolate from core production tables.

### Data Flow

```
APScheduler (news: 6h, truth social: 12h)
  |
  v
DuckDuckGo Search API (ddgs)
  |
  v
Dedup + Upsert into analytical_* tables
  |
  v
Context window computation (aggregates data preceding each transcript)
```

## Database Tables

### `analytical_news_items`
News headlines/snippets from DuckDuckGo news search.
- Dedup: `UNIQUE(persona_id, url)`
- Key fields: `title`, `body` (snippet), `url`, `source_name`, `published_at`
- Future: `sentiment_score`, `topics` (JSONB array)

### `analytical_truth_social_posts`
Truth Social posts as reported by media (via DDG search proxy).
- Dedup: `UNIQUE(persona_id, external_id)` where `external_id` = SHA256(url)[:32]
- Key fields: `content`, `post_url`, `posted_at`
- Source is news coverage, not direct Truth Social API (no official API exists)

### `analytical_event_tags`
Per-transcript metadata bundle: event classification + location + timing. One row per transcript.
- Constraint: `UNIQUE(transcript_id)`
- Event types (16): `rally`, `press_conference`, `press_briefing`, `interview`, `prepared_remarks`, `signing_ceremony`, `bilateral_meeting`, `cabinet_meeting`, `reception`, `ceremony`, `summit`, `roundtable`, `announcement`, `greeting`, `troop_address`, `other`
- Audience types (11): `supporters`, `general`, `press`, `congress`, `foreign`, `military`, `cabinet`, `invited`, `industry`, `mixed`, `other`
- Classification sources: `manual`, `auto_ddgs`, `auto_llm`
- Location: `city`, `state`, `country`, `venue` (free-text, supports room-level detail like "Oval Office, The White House")
- Timing: `event_time` (timestamptz — from yt-dlp `release_timestamp` for livestream VODs, else upload `timestamp`), `event_time_local` (HH:MM text when explicitly stated in inputs)
- Additional: `interviewer`, `network`, `is_teleprompter`

### `analytical_context_windows`
Pre-speech atmosphere snapshots aggregating news + Truth Social data.
- Constraint: `UNIQUE(transcript_id, persona_id)`
- Computed from the N-hour window before a transcript's `upload_date`
- Stores: counts, sentiment averages, top topics

### `analytical_procurement_runs`
Audit trail for all procurement operations.
- Source types: `truth_social`, `news_ddgs`, `news_gdelt`, `news_newsapi`, `event_tag_auto`
- Tracks: `items_found`, `items_new`, `items_skipped`, `details` (JSONB)

## API Endpoints

All admin-only under `/api/analytical/`.

### News
| Method | Path | Description |
|--------|------|-------------|
| GET | `/news?persona_id=...&days=7&limit=100` | List news items |
| POST | `/news/procure` | Trigger async procurement |
| POST | `/news/procure-sync` | Trigger sync procurement (testing) |

### Truth Social
| Method | Path | Description |
|--------|------|-------------|
| GET | `/truth-social?persona_id=...&days=7&limit=100` | List posts |
| POST | `/truth-social/procure` | Trigger async procurement |
| POST | `/truth-social/procure-sync` | Trigger sync procurement (testing) |

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
| POST | `/metadata/backfill/{persona_id}?force=false&limit=N` | Re-extract the full metadata bundle (event_type, location, audience, event_time + frozen context_window) for every transcript belonging to a persona. Skips rows with `classification_source='manual'` unless `force=true`. Records a `procurement_runs` row with `source_type='metadata_backfill'`. |

### Audit
| Method | Path | Description |
|--------|------|-------------|
| GET | `/procurement-runs?source_type=...&persona_id=...&limit=20` | List runs |

## Services

| File | Purpose |
|------|---------|
| `analytical_news_service.py` | DDG news procurement, dedup, read |
| `analytical_truth_social_service.py` | DDG Truth Social proxy, dedup, read |
| `analytical_event_tag_service.py` | Event tag CRUD + auto-classification via DDG |
| `analytical_context_service.py` | Context window computation + aggregation |

## Scheduler

Two background jobs added to APScheduler (controlled by `ANALYTICAL_PROCUREMENT_ENABLED` env var):
- **News procurement**: every 6 hours, searches DDG for "Trump" news
- **Truth Social procurement**: every 12 hours, searches DDG for Trump Truth Social posts

Jobs look up the Trump persona ID dynamically via `ilike("name", "%trump%")`.

## Event Auto-Classification

There are now two extraction paths:

### Primary: LLM extraction (runs after every new transcript)

`backend/services/metadata_extraction_service.py` is called from `jobs.py` after a transcript is saved. It performs two Gemini Flash calls per transcript:

1. **Location/audience/time_of_day call** — sees title, description, DDG snippets ("Trump {title}", 10 results), and the first ~2000 chars of the transcript. Fills `city`, `state`, `country`, `venue`, `audience_type`, `event_time_local`, `confidence`. Venue extraction prioritizes DDG snippets (where room-level detail like "Brady Press Briefing Room" lives).
2. **event_type call** — title ONLY, classified via a 16-rule strict keyword map (rule order matters: ceremony triggers fire before prepared_remarks).

`compute_event_time` then sets `event_time` from yt-dlp's `release_timestamp` if `was_live=True` (matches actual stream start), else falls back to the upload `timestamp`.

All values are written with `classification_source='auto_llm'` and surfaced as **suggestions** in the UI — admin must confirm via the metadata edit modal on the transcript detail page.

Cost: ~$0.0004 per transcript at current Gemini Flash pricing (negligible for backfills).

### Bulk backfill

For an existing persona, `bulk_backfill_metadata(persona_id, force, limit)` in `metadata_extraction_service.py` iterates every transcript belonging to that persona (matched by speaker name), re-fetches yt-dlp info, calls the same `populate_for_transcript` helper that `jobs.py` uses, and writes a `procurement_runs` audit row. Reachable two ways:
- **UI**: persona detail page → "Backfill metadata" button (next to "Download all"). Shows a confirm dialog with the candidate count, then toasts the result.
- **API**: `POST /api/analytical/metadata/backfill/{persona_id}?force=...&limit=...` (sync; long-running for large personas).
- **CLI**: `python3 -m backend.scripts.backfill_metadata --persona-id <uuid>` (thin wrapper around the service, useful when the server isn't available).

Audit trail: query `analytical.procurement_runs` where `source_type='metadata_backfill'`. The `details` JSONB column holds a per-transcript breakdown.

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
