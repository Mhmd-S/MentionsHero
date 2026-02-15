# Database Schema

All tables live in the `public` schema on Supabase (PostgreSQL). Source of truth: `utils/db_refrence.sql` and `supabase/migrations/`.

## Core Tables

### transcripts
Primary content store for all transcribed videos.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| youtube_url | text NOT NULL | Source video URL |
| transcript | text NOT NULL | Full transcript text with speaker labels |
| name | text | Display name (usually video title) |
| folder_id | uuid FK → folders | Optional folder grouping |
| upload_date | text | YouTube upload date (YYYYMMDD format) |
| created_at | timestamptz | |

### folders
Hierarchical folder tree for organizing transcripts.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| name | text NOT NULL | |
| parent_id | uuid FK → folders | Self-referential for nesting |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### jobs
Transcription job queue with progress tracking.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| youtube_url | text NOT NULL | |
| status | text NOT NULL | pending, downloading, transcribing, saving, completed, failed, cancelled |
| stage_progress | jsonb | `{current_chunk, total_chunks, substep, substep_detail}` |
| error_message | text | |
| transcript_id | uuid FK → transcripts | Set on completion |
| cancel_requested | boolean | Cooperative cancellation flag |
| playlist_id | text | YouTube playlist ID (for batch) |
| playlist_name | text | |
| playlist_index | integer | Position in playlist |
| video_title | text | |
| created_at | timestamptz | |
| updated_at | timestamptz | |

## Speaker Tables

### speakers
Deduplicated speaker names extracted from transcripts.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| name | text NOT NULL UNIQUE | |
| created_at | timestamptz | |

### transcript_speakers
Junction: which speakers appear in which transcripts.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| transcript_id | uuid FK → transcripts | |
| speaker_id | uuid FK → speakers | |
| segment_count | integer | Number of segments by this speaker |
| created_at | timestamptz | |

## Persona Tables

### personas
Named entities (people) tracked across transcripts.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| name | text NOT NULL | |
| description | text | |
| youtube_channel_url | text | YouTube channel URL for channel monitor auto-detection |
| has_model | boolean | True if ML model trained |
| last_trained_at | timestamptz | Last successful training time |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### persona_aliases
Speaker name variants that map to a persona.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| persona_id | uuid FK → personas | |
| alias | text NOT NULL UNIQUE | Case-insensitive matching |
| created_at | timestamptz | |

## Analysis Tables

### analysis_cache
Caches NLP analysis results with TTL.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| cache_key | text NOT NULL UNIQUE | |
| result | jsonb NOT NULL | Cached analysis payload |
| created_at | timestamptz | |
| expires_at | timestamptz | Cache expiration (default 24h) |

## Polymarket Tables

### polymarket_series
Top-level grouping for recurring prediction market events.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| polymarket_id | text UNIQUE | External Gamma ID |
| slug | text UNIQUE | URL slug |
| title | text | |
| description | text | |
| image | text | |
| icon | text | |
| series_type | text | |
| recurrence | text | e.g., "weekly" |
| active | boolean | |
| closed | boolean | |
| base_slug | text | Slug without trailing `-NNN` suffix |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### polymarket_events
Individual events within a series.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| slug | text UNIQUE | |
| title | text | |
| image | text | |
| start_date | timestamptz | |
| end_date | timestamptz | |
| series_id | uuid FK → polymarket_series | ON DELETE SET NULL |
| polymarket_id | text | External Gamma ID |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### polymarket_markets
Individual yes/no markets within an event.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| event_id | uuid FK → polymarket_events | |
| condition_id | text | Gamma condition ID |
| question | text | Market question (contains search terms in quotes) |
| slug | text | |
| active | boolean | |
| closed | boolean | |
| outcome_prices | jsonb | `["0.95", "0.05"]` — [yes_price, no_price] |
| resolved_outcome | text | "YES", "NO", or null |
| closed_time | timestamptz | |
| resolution_source | text | |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### market_search_configs
Extracted search criteria from market questions.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| market_id | uuid UNIQUE FK → polymarket_markets | |
| search_terms | jsonb | `["tariffs", "economy"]` |
| min_count | integer | Minimum mentions threshold |
| logic | text | `at_least` or `any` |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### market_search_results
Aggregate search results per market per persona (legacy).

| Column | Type | Notes |
|--------|------|-------|
| market_id | uuid PK FK → polymarket_markets | Composite PK |
| persona_id | uuid PK FK → personas | Composite PK |
| count | integer | Total mentions |
| briefings_with_term | integer | |
| total_briefings | integer | |
| percentage | numeric | |
| trend | text | stable, increasing, decreasing |
| mentions_by_date | jsonb | `[{date, name, count}]` |
| last_updated | timestamptz | |

### market_term_results
Per-term analysis results for a market-persona pair.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| market_id | uuid FK → polymarket_markets | |
| persona_id | uuid FK → personas | |
| search_term | text | Individual term being tracked |
| total_mentions | integer | |
| briefings_with_term | integer | |
| total_briefings | integer | |
| percentage | numeric | |
| trend | text | stable, increasing, decreasing |
| mentions_by_date | jsonb | `[{date, name, count}]` |
| context_matches | jsonb | `[{transcript_id, transcript_name, date, context, position}]` |
| context_total_matches | integer | |
| context_transcripts_with_matches | integer | |
| last_updated | timestamptz | |
| created_at | timestamptz | |

**Unique constraint:** `(market_id, persona_id, search_term)`

## Junction Tables

### persona_polymarket_series
Links personas to series with optional folder scoping and auto-trade flag.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| persona_id | uuid FK → personas | ON DELETE CASCADE |
| polymarket_series_id | uuid FK → polymarket_series | ON DELETE CASCADE |
| folder_id | uuid FK → folders | ON DELETE SET NULL — scopes transcript analysis |
| auto_trade | boolean NOT NULL DEFAULT false | Enable auto-trading when channel monitor detects new video |
| created_at | timestamptz | |

**Unique constraint:** `(persona_id, polymarket_series_id)`

### persona_polymarket_events
Legacy junction linking personas directly to events.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| persona_id | uuid FK → personas | |
| polymarket_event_id | uuid FK → polymarket_events | |
| created_at | timestamptz | |

## ML Training Tables

### ml_training_jobs
LoRA fine-tuning job tracking.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| persona_id | uuid FK → personas | ON DELETE CASCADE |
| status | text | pending, preparing_data, training, evaluating, completed, failed, cancelled |
| stage_progress | jsonb | `{stage, iteration, total_iterations, train_loss, valid_loss, elapsed_seconds, detail, output[]}` |
| error_message | text | |
| total_segments | integer | Segments extracted from transcripts |
| train_segments | integer | 80% split |
| valid_segments | integer | 10% split |
| test_segments | integer | 10% split |
| config | jsonb | Full training config (model, hyperparams, LoRA params) |
| adapter_path | text | Filesystem path to LoRA adapters |
| data_path | text | Filesystem path to training JSONL |
| final_train_loss | numeric | |
| final_valid_loss | numeric | |
| training_duration_seconds | integer | |
| created_at | timestamptz | |
| updated_at | timestamptz | |
| completed_at | timestamptz | |
| cancel_requested | boolean | Cooperative cancellation flag |

## Trading Tables

### trading_sessions
One per live streaming + trading session.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| youtube_url | text NOT NULL | Live stream URL |
| video_title | text | |
| persona_id | uuid FK → personas | |
| series_id | uuid FK → polymarket_series | ON DELETE SET NULL |
| status | text NOT NULL | pending, streaming, completed, failed, cancelled |
| config | jsonb NOT NULL | TradingConfig (chunk sizes, thresholds, amounts) |
| stage_progress | jsonb NOT NULL | `{chunks_processed, terms_detected, trades_placed, positions_open}` |
| error_message | text | |
| cancel_requested | boolean NOT NULL | Cooperative cancellation flag |
| started_at | timestamptz | When streaming began |
| ended_at | timestamptz | When session finished |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### trades
Individual buy/sell trade records.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| session_id | uuid FK → trading_sessions | ON DELETE CASCADE |
| market_id | uuid FK → polymarket_markets | |
| token_id | text | CLOB token ID |
| condition_id | text | Market condition ID |
| side | text NOT NULL | buy, sell |
| amount_usd | numeric | Dollar amount |
| price | numeric | Execution price |
| shares | numeric | Number of shares |
| order_id | text | CLOB order ID or "DRY_RUN" |
| status | text NOT NULL | pending, submitted, filled, failed |
| triggered_by | text NOT NULL | term_detection, profit_target, stop_loss, market_close, session_end |
| detected_term | text | The term that triggered a buy |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### trading_positions
Active positions monitored for sell conditions.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| session_id | uuid FK → trading_sessions | ON DELETE CASCADE |
| market_id | uuid FK → polymarket_markets | |
| token_id | text | |
| buy_trade_id | uuid FK → trades | |
| buy_price | numeric | Entry price |
| shares | numeric | |
| current_price | numeric | Last polled price |
| status | text NOT NULL | open, closed_profit, closed_loss, closed_market, closed_session |
| sell_trade_id | uuid FK → trades | Set when position closed |
| profit_loss_pct | numeric | Final P&L percentage |
| created_at | timestamptz | |
| updated_at | timestamptz | |

### trading_session_log
Event log for debugging and SSE streaming.

| Column | Type | Notes |
|--------|------|-------|
| id | uuid PK | |
| session_id | uuid FK → trading_sessions | ON DELETE CASCADE |
| event_type | text NOT NULL | e.g., stream_started, chunk_transcribed, term_detected, buy_executed |
| payload | jsonb | Event-specific data |
| created_at | timestamptz | |

**Indexes:** `(session_id, created_at DESC)` on trading_session_log; partial index on trading_sessions for active status.

## Entity Relationship Summary

```
folders ←──── transcripts ←──── transcript_speakers ────→ speakers
   │
   │           jobs ─────────────→ transcripts
   │
   ├──── persona_polymarket_series ────→ polymarket_series
   │              │                           │
   │              ↓                           ↓
   │          personas ←── persona_aliases    polymarket_events
   │              │                                │
   │              ├─→ ml_training_jobs             ↓
   │              │                       polymarket_markets
   │              ├─→ trading_sessions       │         │
   │              │        │        market_search_configs
   │              │        ├─→ trades         │
   │              │        ├─→ trading_positions
   │              │        └─→ trading_session_log
   │              │
   └───────── analysis_cache        market_term_results
                                    market_search_results
```
