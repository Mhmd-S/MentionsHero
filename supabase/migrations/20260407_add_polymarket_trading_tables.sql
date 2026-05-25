-- Add CLOB token IDs to poly_markets (needed for trading)
ALTER TABLE public.poly_markets
  ADD COLUMN IF NOT EXISTS clob_token_ids jsonb,
  ADD COLUMN IF NOT EXISTS condition_id text;

-- Orders placed via CLOB API
CREATE TABLE IF NOT EXISTS public.poly_orders (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  clob_order_id text NOT NULL UNIQUE,
  market_id uuid NOT NULL,
  token_id text NOT NULL,
  side text NOT NULL CHECK (side IN ('BUY', 'SELL')),
  outcome text NOT NULL CHECK (outcome IN ('YES', 'NO')),
  order_type text NOT NULL DEFAULT 'limit' CHECK (order_type IN ('limit', 'market')),
  price numeric NOT NULL,
  original_size numeric NOT NULL,
  size_matched numeric NOT NULL DEFAULT 0,
  status text NOT NULL DEFAULT 'live' CHECK (status IN ('live', 'matched', 'cancelled', 'expired')),
  asset_id text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT poly_orders_pkey PRIMARY KEY (id),
  CONSTRAINT poly_orders_market_fkey FOREIGN KEY (market_id)
    REFERENCES public.poly_markets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_poly_orders_market ON poly_orders(market_id);
CREATE INDEX IF NOT EXISTS idx_poly_orders_status ON poly_orders(status);
CREATE INDEX IF NOT EXISTS idx_poly_orders_created ON poly_orders(created_at DESC);

-- Trade/fill history
CREATE TABLE IF NOT EXISTS public.poly_trades (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  trade_id text NOT NULL UNIQUE,
  order_id uuid,
  market_id uuid NOT NULL,
  token_id text NOT NULL,
  side text NOT NULL CHECK (side IN ('BUY', 'SELL')),
  outcome text NOT NULL CHECK (outcome IN ('YES', 'NO')),
  price numeric NOT NULL,
  size numeric NOT NULL,
  fee numeric DEFAULT 0,
  realized_pnl numeric,
  traded_at timestamp with time zone NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT poly_trades_pkey PRIMARY KEY (id),
  CONSTRAINT poly_trades_order_fkey FOREIGN KEY (order_id)
    REFERENCES public.poly_orders(id) ON DELETE SET NULL,
  CONSTRAINT poly_trades_market_fkey FOREIGN KEY (market_id)
    REFERENCES public.poly_markets(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_poly_trades_market ON poly_trades(market_id);
CREATE INDEX IF NOT EXISTS idx_poly_trades_traded ON poly_trades(traded_at DESC);

-- Current positions per market/outcome
CREATE TABLE IF NOT EXISTS public.poly_positions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  market_id uuid NOT NULL,
  token_id text NOT NULL,
  outcome text NOT NULL CHECK (outcome IN ('YES', 'NO')),
  size numeric NOT NULL DEFAULT 0,
  avg_price numeric NOT NULL DEFAULT 0,
  realized_pnl numeric NOT NULL DEFAULT 0,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT poly_positions_pkey PRIMARY KEY (id),
  CONSTRAINT poly_positions_market_fkey FOREIGN KEY (market_id)
    REFERENCES public.poly_markets(id) ON DELETE CASCADE,
  CONSTRAINT poly_positions_unique UNIQUE (market_id, outcome)
);

CREATE INDEX IF NOT EXISTS idx_poly_positions_market ON poly_positions(market_id);
