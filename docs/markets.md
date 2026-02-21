# Markets (Kalshi Mentions Integration)

Tracks Kalshi **Mentions** prediction markets — binary contracts that resolve based on whether a specific word/phrase is spoken during a public event (press briefing, earnings call, etc.). Links personas to market series and analyzes whether the tracked terms were mentioned in transcripts.

## Hierarchy

```
KalshiSeries (e.g., "What will Trump say?" — KXTRUMPMENTION)
  └─ KalshiEvent (e.g., "Governors Dinner" — KXTRUMPMENTION-26FEB22)
       ├─ KalshiMarket ("Democrat" — custom_strike.Word)
       ├─ KalshiMarket ("Tariffs" — custom_strike.Word)
       └─ ...
```

- **Series**: A recurring group of events, always `category: "Mentions"` (identified by Kalshi ticker)
- **Events**: Individual occurrences within a series (e.g., a single briefing date)
- **Markets**: Binary contracts for specific words/phrases. Each market has a `custom_strike.Word` field containing the tracked term

## Browsing & Lazy Storage

The markets listing page fetches ALL open Mentions events directly from the Kalshi v1 search API, grouped by tag category: **Politicians**, **Earnings**, **Sports**. No manual add/delete workflow.

### Data Flow
1. **Listing page** calls `GET /api/kalshi/series/browse` → backend calls Kalshi v1 search API (`/v1/search/series?category=Mentions&tag={tag}`) for each tag, returns events grouped by tag with nested market previews
2. **Detail page** uses event_ticker routing (`/markets/{event_ticker}`). Calls `GET /api/kalshi/events/by-ticker/{event_ticker}` which lazily upserts the series + event + markets into DB via `ensure_event(event_ticker)` on first access
3. **Persona linking** happens at the series level — personas are linked to series, and analysis runs across all events in that series

### Key Functions (kalshi_service.py)
- `_search_events_by_tag(tag)` → Fetches open events for a tag from Kalshi v1 search API
- `browse_events()` → Fetches all tags, returns events grouped by tag with market previews
- `ensure_event(event_ticker)` → Ensures event is in DB; if not, fetches event's series_ticker via v2 API, then calls `ensure_series()` which upserts series + all events + markets
- `ensure_series(ticker)` → Ensures series is in DB; if not, fetches from API and upserts
- `get_event_detail_by_ticker(event_ticker, persona_id)` → Ensures event, returns event + markets + series info + persona analysis

## Kalshi API Integration

### v1 Search API (for browsing)
**Base URL**: `https://api.elections.kalshi.com/v1/search`
- `GET /series?category=Mentions&tag={tag}&status=open,unopened` → Returns events with nested markets
- Each item includes: `series_ticker`, `event_ticker`, `event_title`, `markets[]` with `custom_strike.Word`, prices, etc.

### v2 Trade API (for CRUD operations)
**Base URL**: `https://api.elections.kalshi.com/trade-api/v2` (unauthenticated, read-only)
- **Tickers** as identifiers (series, events, markets all use ticker strings)
- **Nested markets**: Event queries support `with_nested_markets=true`
- **Explicit resolution**: `result` field ("yes"/"no"/"")
- **Cursor-based pagination**
- **`custom_strike`**: JSONB field on markets containing `{"Word": "tracked term"}`

## Core Operations

### Search Term Extraction (`_extract_search_terms()`)
1. Check `custom_strike.Word` — if present, split on " / " and use as search terms
2. Fallback: parse quoted terms from question text via `parse_market_criteria()` (regex)

### Idempotent Upsert (`_upsert_event_and_markets()`)
- Events: matched by `event_ticker`
- Markets: matched by `ticker`
- Stores `custom_strike` JSONB from API
- For Mentions markets, derives `question` from `custom_strike.Word` (the tracked term)
- Automatically creates `market_search_configs` for each market during upsert (extracts search terms from `custom_strike.Word`), so terms are available from first load

### Market Resolution
Kalshi provides explicit resolution via the `result` field:
- `"yes"` → term was spoken
- `"no"` → term was not spoken
- `""` or `null` → unresolved

### Market Analysis Flow
When analysis runs (on link, refresh, or alias change):
1. For each market: extract search terms from `custom_strike.Word` → store in `market_search_configs`
2. Get transcripts for persona (respecting folder scope)
3. For each search term:
   - Count mentions (case-insensitive, speaker-filtered)
   - Find context matches (300-char window)
   - Calculate trend (rising/falling/stable)
   - Upsert `market_term_results` record

### Market Opportunity Analysis
`analyze_market_opportunity(yes_price, historical_percentage)` calculates:
- Expected value for YES and NO bets
- Recommendation: "yes" (EV > 0.15), "no" (EV > 0.15), or "skip"
- Confidence score and reasoning

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/kalshi/series/browse` | Browse open Mentions events grouped by tag (Politicians, Earnings, Sports) |
| `GET` | `/api/kalshi/events/by-ticker/{event_ticker}` | Get event detail by ticker (lazy upserts on first access) |
| `GET` | `/api/kalshi/series/by-ticker/{ticker}` | Get series detail by ticker (lazy upserts on first access) |
| `GET` | `/api/kalshi/series/discover` | Discover Mentions series (optional `?tags=` filter) |
| `GET` | `/api/kalshi/series` | List stored series with event counts and persona links |
| `POST` | `/api/kalshi/series` | Add series by ticker (legacy) |
| `GET` | `/api/kalshi/series/{id}` | Series detail with events and persona IDs |
| `POST` | `/api/kalshi/series/{id}/refresh` | Re-fetch from Kalshi |
| `DELETE` | `/api/kalshi/series/{id}` | Delete series (cascades) |
| `POST` | `/api/kalshi/series/{id}/load-past-events` | Fetch closed events by series_ticker |
| `POST` | `/api/kalshi/series/{id}/personas` | Link persona to series (accepts ticker or UUID) |
| `DELETE` | `/api/kalshi/series/{id}/personas/{pid}` | Unlink persona |
| `GET` | `/api/kalshi/series/{id}/personas` | Get linked personas |
| `GET` | `/api/kalshi/series/{id}/events/{eid}` | Event with market analysis |
| `POST` | `/api/kalshi/series/{id}/events/{eid}/refresh` | Refresh single event |
| `POST` | `/api/kalshi/analyze` | Analyze market opportunity |

## File Map

| Layer | File | Purpose |
|-------|------|---------|
| Page | `app/pages/markets/index.vue` | Event listing grouped by tag (Politicians, Earnings, Sports), auto-fetched from Kalshi v1 search API |
| Page | `app/pages/markets/[id].vue` | Event detail by event_ticker: markets with persona analysis |
| Composable | `app/composables/useKalshi.ts` | All Kalshi API calls (`browseEvents`, `getEventDetailByTicker`, etc.) |
| Component | `app/components/TermSection.vue` | Per-market term analysis display |
| Router | `backend/routers/kalshi.py` | All `/api/kalshi/*` endpoints |
| Service | `backend/services/kalshi_service.py` | Kalshi API client, browse/ensure/upsert logic, market analysis |
| Model | `backend/models/kalshi.py` | Kalshi API models, DB record models, analysis result models |

## Database Tables

**kalshi_series**
- `id` (uuid PK), `ticker` (text UNIQUE), `title`, `category`, `tags` (jsonb), `frequency`, `status` (text), `created_at`, `updated_at`

**kalshi_events**
- `id` (uuid PK), `event_ticker` (text UNIQUE), `series_ticker`, `series_id` (uuid FK → kalshi_series SET NULL), `title`, `sub_title`, `status` (text), `strike_date`, `strike_period`, `created_at`, `updated_at`

**kalshi_markets**
- `id` (uuid PK), `ticker` (text UNIQUE), `event_id` (uuid FK → kalshi_events CASCADE), `event_ticker`, `question`, `market_type`, `status`, `result` (text — "yes"/"no"/""), `last_price` (numeric), `yes_bid`/`yes_ask`/`no_bid`/`no_ask` (numeric), `custom_strike` (jsonb — `{"Word": "term"}`), `close_time`, `rules_primary`, `rules_secondary`, `created_at`, `updated_at`

**persona_kalshi_series** (junction)
- `id` (uuid PK), `persona_id` (uuid FK CASCADE), `kalshi_series_id` (uuid FK CASCADE), `folder_id` (uuid FK SET NULL — scopes transcript search), `created_at`
- UNIQUE(persona_id, kalshi_series_id)

**market_search_configs**
- `id` (uuid PK), `market_id` (uuid FK CASCADE), `search_terms` (jsonb), `min_count` (int), `logic` (text), `created_at`, `updated_at`
- UNIQUE(market_id)

**market_term_results**
- `id` (uuid PK), `market_id` (uuid FK CASCADE), `persona_id` (uuid FK CASCADE), `search_term` (text), `total_mentions` (int), `briefings_with_term` (int), `total_briefings` (int), `percentage` (numeric), `trend` (text), `mentions_by_date` (jsonb), `context_matches` (jsonb), `context_total_matches` (int), `context_transcripts_with_matches` (int), `last_updated`, `created_at`
- UNIQUE(market_id, persona_id, search_term)
