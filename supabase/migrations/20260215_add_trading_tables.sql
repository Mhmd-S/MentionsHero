-- Trading session: one live streaming + trading session
CREATE TABLE public.trading_sessions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  youtube_url text NOT NULL,
  video_title text,
  persona_id uuid NOT NULL,
  series_id uuid,
  status text NOT NULL DEFAULT 'pending',
  config jsonb NOT NULL DEFAULT '{}'::jsonb,
  stage_progress jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_message text,
  cancel_requested boolean NOT NULL DEFAULT false,
  started_at timestamp with time zone,
  ended_at timestamp with time zone,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT trading_sessions_pkey PRIMARY KEY (id),
  CONSTRAINT trading_sessions_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id),
  CONSTRAINT trading_sessions_series_fkey FOREIGN KEY (series_id) REFERENCES public.polymarket_series(id) ON DELETE SET NULL
);

-- Individual buy/sell trade records
CREATE TABLE public.trades (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL,
  market_id uuid NOT NULL,
  token_id text,
  condition_id text,
  side text NOT NULL,
  amount_usd numeric NOT NULL DEFAULT 0,
  price numeric NOT NULL DEFAULT 0,
  shares numeric NOT NULL DEFAULT 0,
  order_id text,
  status text NOT NULL DEFAULT 'pending',
  triggered_by text NOT NULL,
  detected_term text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT trades_pkey PRIMARY KEY (id),
  CONSTRAINT trades_session_fkey FOREIGN KEY (session_id) REFERENCES public.trading_sessions(id) ON DELETE CASCADE,
  CONSTRAINT trades_market_fkey FOREIGN KEY (market_id) REFERENCES public.polymarket_markets(id)
);

-- Active positions monitored for sell conditions
CREATE TABLE public.trading_positions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL,
  market_id uuid NOT NULL,
  token_id text,
  buy_trade_id uuid,
  buy_price numeric NOT NULL DEFAULT 0,
  shares numeric NOT NULL DEFAULT 0,
  current_price numeric NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'open',
  sell_trade_id uuid,
  profit_loss_pct numeric,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT trading_positions_pkey PRIMARY KEY (id),
  CONSTRAINT trading_positions_session_fkey FOREIGN KEY (session_id) REFERENCES public.trading_sessions(id) ON DELETE CASCADE,
  CONSTRAINT trading_positions_market_fkey FOREIGN KEY (market_id) REFERENCES public.polymarket_markets(id),
  CONSTRAINT trading_positions_buy_trade_fkey FOREIGN KEY (buy_trade_id) REFERENCES public.trades(id),
  CONSTRAINT trading_positions_sell_trade_fkey FOREIGN KEY (sell_trade_id) REFERENCES public.trades(id)
);

-- Event log for debugging and SSE streaming
CREATE TABLE public.trading_session_log (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  session_id uuid NOT NULL,
  event_type text NOT NULL,
  payload jsonb DEFAULT '{}'::jsonb,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT trading_session_log_pkey PRIMARY KEY (id),
  CONSTRAINT trading_session_log_session_fkey FOREIGN KEY (session_id) REFERENCES public.trading_sessions(id) ON DELETE CASCADE
);

-- Index for fast log lookups
CREATE INDEX trading_session_log_session_idx ON public.trading_session_log (session_id, created_at DESC);

-- Index for finding active sessions
CREATE INDEX trading_sessions_status_idx ON public.trading_sessions (status) WHERE status NOT IN ('completed', 'failed', 'cancelled');
