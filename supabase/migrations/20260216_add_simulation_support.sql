-- Add simulation support to trading tables

-- Alter trading_sessions: add simulation flag and metadata
ALTER TABLE public.trading_sessions
  ADD COLUMN is_simulation boolean NOT NULL DEFAULT false,
  ADD COLUMN simulation_metadata jsonb;

-- Alter trades: add simulated timestamp
ALTER TABLE public.trades ADD COLUMN simulated_at bigint;

-- Cache table for CLOB historical price data
CREATE TABLE public.market_price_history (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  token_id text NOT NULL,
  source text NOT NULL DEFAULT 'prices-history',
  start_ts bigint NOT NULL,
  end_ts bigint NOT NULL,
  fidelity integer,
  prices jsonb NOT NULL DEFAULT '[]'::jsonb,
  fetched_at timestamptz DEFAULT now(),
  created_at timestamptz DEFAULT now()
);
CREATE INDEX idx_price_history_lookup ON public.market_price_history (token_id, start_ts, end_ts);
ALTER TABLE public.market_price_history ADD CONSTRAINT uq_price_history UNIQUE (token_id, source, start_ts, end_ts);

-- Timeline events for simulation visualization
CREATE TABLE public.simulation_timeline_events (
  id uuid DEFAULT gen_random_uuid() PRIMARY KEY,
  session_id uuid NOT NULL REFERENCES public.trading_sessions(id) ON DELETE CASCADE,
  event_type text NOT NULL,
  simulated_timestamp bigint NOT NULL,
  wall_clock_timestamp timestamptz DEFAULT now(),
  market_id uuid,
  payload jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX idx_sim_timeline_session ON public.simulation_timeline_events (session_id, simulated_timestamp);
