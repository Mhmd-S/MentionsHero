# Polymarket Integration

## Purpose
Connects prediction market data from Polymarket with transcript analysis. Tracks series of recurring events (e.g., "mention markets"), links them to personas, and analyzes how often market-specified terms appear in a persona's transcripts.

## User Flow
1. User navigates to `/events`
2. Views list of tracked Polymarket series
3. Clicks "Add Series" → discovers series from Gamma API → adds by slug
4. Opens a series detail page
5. Links a persona to the series (with optional folder scoping)
6. Selects an event and persona to view market analysis
7. Each market shows: question, search terms, term frequency, trend, context snippets
8. Can refresh events, load past events, and view resolved outcomes

## Data Flow

```
events/index.vue
  → GET /api/polymarket/series → polymarket_service.get_all_series()
  → GET /api/polymarket/series/discover → Gamma API GET /events?tag_slug=mention-markets
  → POST /api/polymarket/series { slug }
    → polymarket_service.add_series(slug)
      → Gamma: GET /events/slug/{slug} (includes markets)
      → _upsert_series_from_events() → INSERT/UPDATE polymarket_series
      → _upsert_event_and_markets() → INSERT/UPDATE polymarket_events + polymarket_markets
      → parse_market_criteria(question) → INSERT market_search_configs

events/[id].vue
  → GET /api/polymarket/series/{id} → series detail with events[], persona_ids
  → POST /api/polymarket/series/{id}/personas { persona_id, folder_id? }
    → link_persona_to_series() → INSERT persona_polymarket_series
  → GET /api/polymarket/series/{id}/events/{eventId}?persona_id=X
    → get_event_with_analysis(event_id, persona_id)
      → For each market: SELECT market_search_configs + market_term_results
      → Returns { event, markets: [{ market, search_config, term_results[] }] }
  → POST /api/polymarket/series/{id}/events/{eventId}/refresh
    → refresh_single_event(event_id)
      → Re-fetch from Gamma → upsert → re-run analysis for all linked personas
  → POST /api/polymarket/series/{id}/load-past-events
    → fetch_past_events_for_series() → Gamma paginated fetch of closed events → upsert all
```

## Key Files

### Frontend
| File | Purpose |
|------|---------|
| `app/pages/events/index.vue` | Series list, discover/add modal, delete series |
| `app/pages/events/[id].vue` | Series detail — persona selector, event selector, market analysis display |
| `app/components/TermSection.vue` | Per-market analysis display — term mentions, trend, context snippets with highlighting |
| `app/composables/usePolymarket.ts` | API wrapper for all Polymarket endpoints |

### Backend
| File | Purpose |
|------|---------|
| `backend/routers/polymarket.py` | Series CRUD, event refresh, persona linking, analysis endpoints, legacy event endpoints |
| `backend/services/polymarket_service.py` | Gamma API integration, upsert logic, market analysis pipeline, resolution logic |
| `backend/models/polymarket.py` | PolymarketMarket, AnalyzeRequest, AddSeriesRequest, LinkPersonaToSeriesRequest, etc. |
| `backend/utils/nlp.py` | `calculate_term_frequency()`, `search_term_in_context()` — shared with term search |

## Database Tables
- **polymarket_series** — series metadata (slug, title, recurrence, base_slug)
- **polymarket_events** — events within series (slug, dates, series_id FK)
- **polymarket_markets** — individual yes/no markets (question, outcome_prices, resolved_outcome)
- **market_search_configs** — extracted search terms from market questions (per market)
- **market_term_results** — per-term analysis results per market-persona pair
- **market_search_results** — aggregate results (legacy)
- **persona_polymarket_series** — junction linking personas to series with folder_id scope
- **persona_polymarket_events** — legacy junction linking personas directly to events

## External Integrations

### Gamma API (`https://gamma-api.polymarket.com`)
| Endpoint | Usage |
|----------|-------|
| `GET /tags` | Discover available tag categories |
| `GET /events` | Fetch events by tag, active/closed status (paginated) |
| `GET /events/slug/{slug}` | Fetch single event with nested markets |

**Important:** Series API returns events WITHOUT nested markets. Each event must be fetched individually via slug to get market data.

## Key Implementation Details

**Resolution logic:** When a market is closed, outcome is resolved from `outcome_prices`:
- `outcome_prices[0] >= 0.95` → resolved as "YES"
- `outcome_prices[1] >= 0.95` → resolved as "NO"
- Otherwise → unresolved (null)

**Market question parsing:** `parse_market_criteria(question)` extracts search terms in double quotes and "X+ times" patterns:
- `'Will she say "tariffs"?'` → `{search_terms: ["tariffs"], min_count: 0, logic: "any"}`
- `'Will he say "economy" 3+ times?'` → `{search_terms: ["economy"], min_count: 3, logic: "at_least"}`

**Analysis pipeline:** When viewing an event with a persona:
1. Get persona aliases
2. Get persona's transcripts (scoped to folder if configured in junction)
3. For each market's search terms: calculate frequency + extract context
4. Results stored in `market_term_results` for fast subsequent loads

**Past events backfill:** `fetch_past_events_for_series()` derives `base_slug` by stripping trailing `-NNN` from slug, then fetches all closed events matching that base slug from Gamma (paginated).

**Folder scoping:** The `persona_polymarket_series.folder_id` column allows analysis to be scoped to a specific folder tree, so a persona can be analyzed against only relevant transcripts.
