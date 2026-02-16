# Trading Bot

Trading bot that downloads and transcribes a YouTube video, detects market-relevant terms, and auto-trades on Polymarket via the CLOB API.

## Strategy

"Sell the news" — buy mention-market positions when terms are detected in a podcast transcript, sell when price rises (profit target) or cut losses (stop-loss).

## Data Flow

```
YouTube URL
       │
       ▼
[download_audio()] ── yt-dlp ── writes .mp3 file
       │
       ▼
[transcribe_audio()] ── Gemini Flash with diarization ── full transcript text
       │
       ▼
[TermDetector] ── \b{term}\b regex against market_search_configs
       │                              │
       ▼                              ▼
[TradingService.buy()]        [trading_session_log]
       │
       ▼
[PositionMonitor] ── polls prices every 10s
  • sell at +profit_target_pct
  • sell at -stop_loss_pct
  • sell on market close / session end
```

## Market Selection

Sessions select **markets** (not events). The system always auto-loads the **newest event** in the selected series. Users can then toggle individual markets on/off.

- **Default:** All active markets with search terms in the newest event are selected
- **`market_ids`** in the start request: empty array = all markets from newest event; specific IDs = only those markets
- Markets are stored as `market_ids` in the session's `config` JSONB column
- Closed markets are shown greyed out in the UI and cannot be selected

## Channel Monitor (Auto-Start)

Background service that polls YouTube channels for new uploads and auto-starts trading sessions.

### Setup
1. Set `youtube_channel_url` on a persona (via persona detail page)
2. Enable `auto_trade` on a persona↔series link (via persona detail page toggle)
3. Set `CHANNEL_MONITORING_ENABLED=true` in `.env`

### How It Works
1. On startup, seeds initial state (records current latest video per persona, doesn't trigger)
2. Every `CHANNEL_POLL_INTERVAL_S` seconds (default 45), checks each persona's channel
3. Uses `yt-dlp --flat-playlist --playlist-items 1 --print id` to get latest video ID
4. If new video detected and persona has `auto_trade` series → creates session with default config
5. Logs `auto_started` event so the frontend can show an info alert

### Lifecycle
- Started/stopped via FastAPI `lifespan` context manager in `main.py`
- `start_monitor()` / `stop_monitor()` control the asyncio background task
- `get_monitor_status()` returns `{running, watched_personas, last_video_ids}`

## Session Statuses

| Status | Description |
|--------|-------------|
| `pending` | Session created, not yet started |
| `downloading` | Downloading audio from YouTube via yt-dlp |
| `transcribing` | Transcribing audio with Gemini |
| `analyzing` | Detecting terms and placing trades |
| `completed` | All positions closed, session done |
| `failed` | Error occurred |
| `cancelled` | User cancelled |

## API Endpoints

All routes under `/api/trading`.

### Static Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/markets-for-series?series_id=...` | Newest event + its markets with search terms |
| GET | `/channel-monitor/status` | Monitor running state |
| POST | `/channel-monitor/auto-trade?persona_id=...&series_id=...&enabled=...` | Toggle auto_trade on persona↔series |
| GET | `/active` | Get currently active session |
| GET | `/history` | List past sessions |
| POST | `/start` | Start new session |
| POST | `/stop` | Stop active session |

### Parameterized Routes

| Method | Path | Description |
|--------|------|-------------|
| GET | `/{session_id}` | Full session detail with trades, positions, logs |
| GET | `/{session_id}/stream` | SSE stream (5s heartbeat) |

### Start Session Request

```json
{
  "youtube_url": "https://youtube.com/watch?v=...",
  "persona_id": "uuid",
  "series_id": "uuid",
  "market_ids": ["uuid1", "uuid2"],
  "video_title": "optional title",
  "config": {
    "profit_target_pct": 30.0,
    "stop_loss_pct": 20.0,
    "max_price_to_buy": 0.90,
    "buy_amount_usd": 5.0,
    "max_concurrent_positions": 10,
    "price_poll_interval_s": 10
  }
}
```

**`market_ids`**: Optional list of specific market IDs to trade on. Empty array or omitted = all markets from the newest event in the series.

### Markets for Series Response

```json
{
  "event": { "id": "...", "title": "...", "slug": "..." },
  "markets": [
    {
      "id": "uuid",
      "condition_id": "...",
      "question": "Will X happen?",
      "slug": "...",
      "active": true,
      "closed": false,
      "outcome_prices": "[\"0.65\",\"0.35\"]",
      "resolved_outcome": null,
      "search_terms": ["term1", "term2"]
    }
  ]
}
```

## Configuration

Environment variables (all in `.env`):

| Variable | Default | Description |
|----------|---------|-------------|
| `POLYMARKET_API_KEY` | `""` | CLOB API key |
| `POLYMARKET_API_SECRET` | `""` | CLOB API secret |
| `POLYMARKET_PRIVATE_KEY` | `""` | Wallet private key for signing |
| `POLYMARKET_CHAIN_ID` | `137` | Polygon chain ID |
| `TRADING_ENABLED` | `false` | Kill switch — must be `true` to start sessions |
| `TRADING_DRY_RUN` | `true` | When `true`, logs trades with `order_id=DRY_RUN` without placing real orders |
| `CHANNEL_MONITORING_ENABLED` | `false` | Enable YouTube channel polling background service |
| `CHANNEL_POLL_INTERVAL_S` | `45` | Seconds between channel polls |

## Safety Features

- **`trading_enabled=false`** default — must explicitly enable
- **`trading_dry_run=true`** default — logs trades without placing real orders
- **`channel_monitoring_enabled=false`** default — must explicitly enable
- **`max_price_to_buy=0.90`** — won't buy near-certain markets
- **`max_concurrent_positions=10`** — limits exposure
- **Stop-loss** — configurable downside protection per position
- **Channel monitor seeding** — on startup, records current latest video per persona without triggering, preventing false auto-starts

## Database Tables

- `trading_sessions` — one per trading session
- `trades` — individual buy/sell records
- `trading_positions` — active positions monitored for sell conditions
- `trading_session_log` — event log for debugging and SSE

`market_ids` are stored in the `config` JSONB column of `trading_sessions` alongside trading config params.

See [DATABASE.md](../DATABASE.md) for full schema.

## Internal Components

### TermDetector (`streaming_service.py`)
Loads active markets + search terms from DB. Runs `\b{term}\b` regex on transcript text. Maintains per-market per-term "already triggered" set to prevent duplicate buys.

### `_load_markets_for_session(persona_id, series_id, market_ids)`
Loads active, non-closed markets with search terms. When `market_ids` is provided, loads those specific markets; otherwise gets the newest event in the series (ordered by `end_date DESC`, `created_at DESC`) and loads all its active markets.

### TradingService (`trading_service.py`)
Handles all CLOB API interactions with dry-run support, SSE events, session/trade/position CRUD.

### ChannelMonitorService (`channel_monitor_service.py`)
Background asyncio task that polls YouTube channels for new uploads. Uses `yt-dlp --flat-playlist` to efficiently check for new video IDs without downloading content. Auto-starts trading sessions when new videos are detected for personas with `auto_trade` enabled on a linked series.

### Pipeline (`run_trading_session`)
Sequential pipeline reusing existing services:
1. `download_audio()` from `download_service` — same function used by the transcript tab
2. `transcribe_audio()` from `transcription_service` — Gemini transcription with diarization
3. `TermDetector.detect()` — finds all terms in the full transcript
4. Position monitor loop — polls prices and sells on profit/loss/close conditions

## Frontend

### Composable: `app/composables/useTrading.ts`

Follows the same `authFetch` + SSE pattern as `useMLTraining.ts`.

**Types:** `TradingSession`, `TradingConfig`, `Trade`, `TradingPosition`, `SessionLog`, `SessionDetail`, `StartSessionRequest`, `TradingMarket`, `MarketsForSeriesResponse`, `ChannelMonitorStatus`

**Methods:**
- `getActiveSession()` — GET `/api/trading/active`
- `getSessionHistory()` — GET `/api/trading/history`
- `startSession(req)` — POST `/api/trading/start`
- `stopSession()` — POST `/api/trading/stop`
- `getSessionDetail(id)` — GET `/api/trading/{id}`
- `streamSession(id, onUpdate)` — EventSource with `?token=` param, returns cleanup function
- `getMarketsForSeries(seriesId)` — GET `/api/trading/markets-for-series`
- `getChannelMonitorStatus()` — GET `/api/trading/channel-monitor/status`
- `toggleAutoTrade(personaId, seriesId, enabled)` — POST `/api/trading/channel-monitor/auto-trade`

### Page: `app/pages/trading.vue`

Single self-contained page with conditional sections:

1. **Setup Form** — persona selector, series selector (filtered by persona), market cards (2-column grid showing question, YES/NO price, active/closed badge, term count, highlighted border when selected), YouTube URL, collapsible advanced config
2. **Live Session** — SSE-connected real-time view with auto-started alert (if applicable), status bar showing current phase, stats grid, transcript preview, positions table, trades table, scrollable event log, stop button
3. **Session Result** — shown after completion/failure/cancel with auto-started alert, summary stats, transcript preview, full positions and trades tables
4. **Session History** — always visible at bottom, expandable rows with detail fetched on click
5. **Channel Monitor Status** — header indicator showing green/grey dot with watched channel count

**Market selection:**
- After series is selected, markets are fetched via `getMarketsForSeries()`
- Displays newest event title as context label
- Markets shown as clickable cards in a 2-column grid
- Each card shows: question (bold), YES price (green), NO price (red), Active/Closed badge, term count badge
- Select All / Deselect All links
- Closed markets shown greyed out, non-clickable
- Default: all active markets with search terms are selected
- If all active markets selected, sends empty `market_ids` (= all markets on backend)

**Lifecycle:**
- `onMounted`: fetches personas, series, history, channel monitor status; checks for active session and reconnects SSE
- `onUnmounted`: cleans up SSE connection

### Navigation

`app/layouts/default.vue` — "Trading Bot" link with `i-heroicons-bolt` icon after Model link.

## Key Files

| File | Purpose |
|------|---------|
| `backend/routers/trading.py` | API endpoints |
| `backend/services/trading_service.py` | CLOB API, session/trade CRUD, SSE events |
| `backend/services/streaming_service.py` | TermDetector, market loader, download+transcribe orchestrator |
| `backend/services/channel_monitor_service.py` | YouTube channel poller, auto-start logic |
| `backend/models/trading.py` | Pydantic models and enums |
| `backend/config.py` | Trading + channel monitor settings |
| `supabase/migrations/20260215_add_trading_tables.sql` | Trading tables migration |
| `supabase/migrations/20260216_trading_channel_monitor.sql` | Channel monitor columns migration |
| `app/composables/useTrading.ts` | Frontend API + SSE composable |
| `app/pages/trading.vue` | Trading bot page |

## Simulation / Backtesting

Simulation mode re-processes a YouTube video against a **resolved past event**, looks up historical Polymarket prices, and produces a P&L report with timeline visualization — enabling config tuning without risking real money.

### How It Works

1. User selects Persona, Series, **Past Event** (including resolved), and markets
2. System downloads YouTube auto-generated subtitles via `yt-dlp --skip-download --write-auto-subs` (real timing measured)
3. TermDetector runs against the cleaned transcript text
4. For each detection: looks up **historical price** at the simulated timestamp (baseline + pipeline elapsed time)
5. Walks the price curve forward to find sell point (profit target / stop loss / end of data)
6. Builds P&L report with per-market breakdown and timeline

### Key Differences from Live Trading

| Aspect | Live Trading | Simulation |
|--------|-------------|------------|
| Session flag | `is_simulation = false` | `is_simulation = true` |
| Market selection | Active markets only | All markets (including closed/resolved) |
| Buy execution | CLOB API order | Historical price lookup |
| Position monitoring | Real-time polling loop | Walk price curve programmatically |
| Trading enabled check | Required | Not required |
| Active session check | Only one at a time | No limit |

### Price History

Historical prices are fetched from the CLOB API and cached in `market_price_history`:

1. **Primary:** `GET /prices-history?market={token_id}&startTs=...&endTs=...&fidelity=1`
2. **Quality check:** If average gap > 12 hours, falls back to trade data
3. **Fallback:** `GET /data/trades?market={token_id}&startTs=...&endTs=...`
4. **Cache:** Results stored in `market_price_history` table for reuse

### Simulation API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/simulation/start` | Start simulation (no trading_enabled check) |
| GET | `/simulation/history` | List past simulations |
| GET | `/simulation/compare?session_ids=id1,id2` | Compare multiple simulation runs |
| GET | `/simulation/events-for-series?series_id=...` | All events for a series (including resolved) |
| GET | `/simulation/markets-for-event?event_id=...` | All markets for an event (including closed) |

### Frontend

The trading page uses `UTabs` with "Live Trading" and "Simulation" tabs.

**Simulation tab sub-views:**
1. **Setup Form** — persona/series/event/market selection, YouTube URL, config
2. **Progress** — SSE streaming with pipeline stages
3. **Results** — `SimulationResults` component with P&L summary, timing bars, per-market table, timeline
4. **History** — simulation-only history list with checkbox selection for comparison

**Components:**
- `SimulationResults.vue` — P&L card, pipeline timing bars, per-market results table
- `SimulationTimeline.vue` — horizontal timeline with phase bars, event dots, hover tooltips
- `SimulationCompare.vue` — side-by-side comparison table with config diff highlighting

### Database Tables

- `market_price_history` — cached CLOB price data (indexed by token_id + time range)
- `simulation_timeline_events` — timeline events for visualization (cascade-deleted with session)
- `trading_sessions.is_simulation` — flag to distinguish simulation from live sessions
- `trading_sessions.simulation_metadata` — JSONB with P&L, timing, per-market results
- `trades.simulated_at` — unix timestamp in historical timeline (null for live trades)

### Key Files

| File | Purpose |
|------|---------|
| `backend/services/price_history_service.py` | CLOB historical price fetching + caching |
| `backend/services/simulation_service.py` | Simulation pipeline orchestrator |
| `app/components/SimulationResults.vue` | P&L report + timing breakdown |
| `app/components/SimulationTimeline.vue` | Horizontal timeline visualization |
| `app/components/SimulationCompare.vue` | Side-by-side run comparison |
| `supabase/migrations/20260216_add_simulation_support.sql` | Schema changes |

## Edge Cases

| Scenario | Strategy |
|---|---|
| No active markets for selected series | Session fails with descriptive error |
| No markets with search terms | Markets shown in UI with "No terms" badge, not selected by default |
| Download fails | Session marked FAILED, error message shown |
| Transcription fails | Session marked FAILED, error message shown |
| Market closes mid-session | Position monitor checks `closed` flag every poll |
| Buy order fails | Trade marked FAILED, logged, processing continues |
| Session cancellation | cancel_event checked between stages; all positions closed |
| Concurrent session race | App-level check for active session before creating new one |
| All active markets selected | Empty market_ids sent = backend loads newest event markets |
| Channel monitor starts with existing videos | Seeds initial state without triggering auto-start |
| Channel monitor: active session exists | Skips auto-start, logs info |
| Channel monitor: no auto_trade series | Skips auto-start for that persona |
| yt-dlp timeout checking channel | Logs warning, continues to next persona |
