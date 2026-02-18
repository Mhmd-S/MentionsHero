-- Drop trading feature tables and columns

-- Drop tables in dependency order (children first)
DROP TABLE IF EXISTS simulation_timeline_events;
DROP TABLE IF EXISTS market_price_history;
DROP TABLE IF EXISTS trading_session_log;
DROP TABLE IF EXISTS trading_positions;
DROP TABLE IF EXISTS trades;
DROP TABLE IF EXISTS trading_sessions;

-- Drop trading-related columns
ALTER TABLE personas DROP COLUMN IF EXISTS youtube_channel_url;
ALTER TABLE persona_polymarket_series DROP COLUMN IF EXISTS auto_trade;
