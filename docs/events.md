# Events (Polymarket Integration)

Tracks Polymarket prediction markets tied to press briefing content. Links personas to market series and analyzes whether specific terms were mentioned in transcripts.

## Hierarchy

```
PolymarketSeries (e.g., "White House press briefings")
  └─ PolymarketEvent (e.g., "Briefing 2/15/2025")
       ├─ PolymarketMarket (e.g., "Will tariffs be mentioned?")
       ├─ PolymarketMarket (e.g., "Will 'fake news' be mentioned?")
       └─ ...
```

- **Series**: A recurring group of events (stored locally with a Gamma API slug as identifier)
- **Events**: Individual occurrences within a series (e.g., a single briefing date)
- **Markets**: Prediction questions within an event, with YES/NO outcome prices

## Gamma API Integration

**Base URL**: `https://gamma-api.polymarket.com`

**Critical gotcha**: The Gamma Series endpoint returns events WITHOUT nested markets. You must fetch each event individually via `GET /events/{slug}` to get its markets.

### Key API Calls (in polymarket_service.py)

- `fetch_event_by_slug(slug)` → Single event with markets
- `_fetch_gamma_events(...)` → Low-level event query with filters
- `_fetch_gamma_events_paginated(...)` → Paginated wrapper for large result sets
- `get_mentions_markets()` / `get_leavitt_markets()` → Fetch mention-style markets

## Core Operations

### Adding a Series
1. User provides a Polymarket slug or discovers via `GET /api/polymarket/series/discover`
2. Backend fetches event from Gamma API by slug
3. Creates `polymarket_series` record (uses slug as polymarket_id)
4. Upserts event + markets via `_upsert_event_and_markets()`

### Idempotent Upsert (`_upsert_event_and_markets()`)
- Events: matched by `slug` — creates if new, updates if existing
- Markets: matched by `condition_id` or `(event_id, question)` — creates if new, updates if existing
- Calculates `resolved_outcome` on every upsert
- Prevents duplicates across multiple API calls

### Market Resolution Logic
```python
def _resolve_outcome(market):
    if market.closed:
        if float(outcome_prices[0]) >= 0.95:  # YES price
            return "YES"
        if float(outcome_prices[1]) >= 0.95:  # NO price
            return "NO"
    return None
```

### Linking Personas to Series
- Creates `persona_polymarket_series` row
- Optional `folder_id` scopes transcript search to that folder tree
- Triggers market analysis for the linked persona

### Market Analysis Flow
When analysis runs (on link, refresh, or alias change):
1. For each market in the series:
   - Extract search terms from question via `parse_market_criteria()` (regex-based)
   - Store in `market_search_configs`
2. Get transcripts for persona (respecting folder scope)
3. For each search term:
   - Count mentions (case-insensitive)
   - Find context matches (300-char window)
   - Calculate trend (rising/falling/stable)
   - Upsert `market_term_results` record

### Market Criteria Parsing (`parse_market_criteria()`)
Extracts quoted terms from market questions:
- `'Will she say "Ally" or "Allied"?'` → `["Ally", "Allied"]`, logic: "any"
- `'Will Keir say "International"?'` → `["International"]`, logic: "at_least"

### Loading Past Events
- `fetch_past_events_for_series(series_id)` fetches closed events from Gamma
- Matches events by `base_slug` pattern (e.g., "briefing-2025-02-15" base slug matches variations)
- Stores as new `polymarket_events` under the same series

### Market Opportunity Analysis
`analyze_market_opportunity(market, historical_percentage)` calculates:
- Expected value for YES and NO bets
- Recommendation: "yes" (EV > 0.15), "no" (EV > 0.15), or "skip"
- Confidence score and reasoning

## API Endpoints

### Series (modern API)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/polymarket/series` | List all series with event counts and persona links |
| `POST` | `/api/polymarket/series` | Add series by slug |
| `GET` | `/api/polymarket/series/discover` | Discover available series from Gamma |
| `GET` | `/api/polymarket/series/{id}` | Series detail with events and persona IDs |
| `POST` | `/api/polymarket/series/{id}/refresh` | Re-fetch from Gamma |
| `DELETE` | `/api/polymarket/series/{id}` | Delete series (cascades) |
| `POST` | `/api/polymarket/series/{id}/load-past-events` | Fetch closed events by base_slug |
| `POST` | `/api/polymarket/series/{id}/personas` | Link persona to series |
| `DELETE` | `/api/polymarket/series/{id}/personas/{pid}` | Unlink persona |
| `GET` | `/api/polymarket/series/{id}/personas` | Get linked personas |
| `GET` | `/api/polymarket/series/{id}/events/{eid}` | Event with market analysis |
| `POST` | `/api/polymarket/series/{id}/events/{eid}/refresh` | Refresh single event |

### Legacy Event API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/polymarket/events` | Add event by slug to persona |
| `GET` | `/api/polymarket/events/{persona_id}` | List persona's events |
| `DELETE` | `/api/polymarket/events/{event_id}` | Remove persona-event link |
| `POST` | `/api/polymarket/events/{event_id}/refresh` | Refresh persona event |

### Markets

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/polymarket/markets` | Get markets (mentions/leavitt/all) |
| `POST` | `/api/polymarket/analyze` | Analyze market opportunity |

## File Map

| Layer | File | Purpose |
|-------|------|---------|
| Page | `app/pages/events/index.vue` | Series listing with event counts and personas |
| Page | `app/pages/events/[id].vue` | Series detail: events, markets, persona analysis |
| Composable | `app/composables/usePolymarket.ts` | All Polymarket API calls |
| Router | `backend/routers/polymarket.py` | All `/api/polymarket/*` endpoints |
| Service | `backend/services/polymarket_service.py` | Gamma API client, upsert logic, market analysis (~1300 lines) |
| Model | `backend/models/polymarket.py` | Gamma API models, DB record models, analysis result models |

## Database Tables

**polymarket_series**
- `id` (uuid PK), `polymarket_id` (text UNIQUE — Gamma slug), `slug` (text UNIQUE), `title`, `description`, `image`, `icon`, `series_type`, `recurrence`, `active` (bool), `closed` (bool), `base_slug` (text), `created_at`, `updated_at`

**polymarket_events**
- `id` (uuid PK), `slug` (text UNIQUE), `title`, `image`, `start_date`, `end_date`, `series_id` (uuid FK → polymarket_series SET NULL), `polymarket_id` (text — Gamma event ID), `created_at`, `updated_at`

**polymarket_markets**
- `id` (uuid PK), `event_id` (uuid FK → polymarket_events CASCADE), `condition_id` (text), `question`, `slug`, `active` (bool), `closed` (bool), `outcome_prices` (jsonb — [yes_price, no_price]), `resolved_outcome` (text — YES/NO/null), `closed_time`, `resolution_source`, `created_at`, `updated_at`

**persona_polymarket_series** (junction)
- `id` (uuid PK), `persona_id` (uuid FK CASCADE), `polymarket_series_id` (uuid FK CASCADE), `folder_id` (uuid FK SET NULL — scopes transcript search), `created_at`
- UNIQUE(persona_id, polymarket_series_id)

**market_search_configs**
- `id` (uuid PK), `market_id` (uuid FK CASCADE), `search_terms` (jsonb), `min_count` (int), `logic` (text — 'at_least'/'any'), `created_at`, `updated_at`
- UNIQUE(market_id)

**market_term_results**
- `id` (uuid PK), `market_id` (uuid FK CASCADE), `persona_id` (uuid FK CASCADE), `search_term` (text), `total_mentions` (int), `briefings_with_term` (int), `total_briefings` (int), `percentage` (numeric), `trend` (text), `mentions_by_date` (jsonb), `context_matches` (jsonb), `context_total_matches` (int), `context_transcripts_with_matches` (int), `last_updated`, `created_at`
- UNIQUE(market_id, persona_id, search_term)
