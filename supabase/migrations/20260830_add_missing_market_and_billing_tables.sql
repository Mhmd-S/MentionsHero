-- Provision the 11 tables the app needs that the new Supabase project never got.
--
-- The MentionsHero database was recreated on 2026-08-11 from mentionshero_setup.sql,
-- which created 15 public tables. The application expects 24 (see utils/db_refrence.sql).
-- The gap is why:
--   * GET /api/public/markets returns 500 ("Could not find the table
--     'public.market_term_results' in the schema cache"), so the whole /markets
--     section of the public site is dark
--   * Stripe checkout cannot record anything — the `subscriptions` table is absent,
--     so the webhook has nowhere to write and nobody can actually become a subscriber
--   * every term-frequency analysis recomputes from scratch — `analysis_cache` is absent
--
-- Every statement is idempotent, so this is safe to re-run.
-- Table definitions are lifted verbatim from utils/db_refrence.sql, which is the
-- authoritative snapshot of the schema the code is written against — not reconstructed
-- from the migration history, which has since been partly superseded.
--
-- Deliberately NOT included: persona_kalshi_series and persona_poly_events. They appear
-- in supabase/migrations/20260221_* and 20260309_* but are absent from db_refrence.sql
-- and no longer referenced anywhere in backend/ or app/. They are dead.

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.analysis_cache (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  cache_key text NOT NULL UNIQUE,
  result jsonb NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  expires_at timestamp with time zone,
  CONSTRAINT analysis_cache_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.subscriptions (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  stripe_customer_id text NOT NULL,
  stripe_subscription_id text UNIQUE,
  status text NOT NULL DEFAULT 'inactive',
  current_period_start timestamp with time zone,
  current_period_end timestamp with time zone,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT subscriptions_pkey PRIMARY KEY (id),
  CONSTRAINT subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES auth.users(id)
);

CREATE TABLE IF NOT EXISTS public.kalshi_series (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  ticker text NOT NULL UNIQUE,
  title text,
  frequency text,
  category text,
  tags jsonb DEFAULT '[]'::jsonb,
  settlement_sources jsonb DEFAULT '[]'::jsonb,
  fee_type text,
  status text DEFAULT 'active'::text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT kalshi_series_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.kalshi_events (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  event_ticker text NOT NULL UNIQUE,
  series_ticker text,
  series_id uuid,
  title text,
  sub_title text,
  mutually_exclusive boolean DEFAULT false,
  category text,
  status text DEFAULT 'active'::text,
  strike_date timestamp with time zone,
  strike_period text,
  show_public boolean NOT NULL DEFAULT false,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT kalshi_events_pkey PRIMARY KEY (id),
  CONSTRAINT kalshi_events_series_fkey FOREIGN KEY (series_id) REFERENCES public.kalshi_series(id)
);

CREATE TABLE IF NOT EXISTS public.kalshi_markets (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  ticker text NOT NULL UNIQUE,
  event_ticker text NOT NULL,
  event_id uuid NOT NULL,
  market_type text DEFAULT 'binary'::text,
  question text,
  yes_sub_title text,
  no_sub_title text,
  status text DEFAULT 'active'::text,
  result text,
  last_price numeric,
  yes_bid numeric,
  yes_ask numeric,
  no_bid numeric,
  no_ask numeric,
  previous_price numeric,
  volume numeric,
  open_interest numeric,
  close_time timestamp with time zone,
  open_time timestamp with time zone,
  settlement_value numeric,
  settlement_timer timestamp with time zone,
  rules_primary text,
  rules_secondary text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  custom_strike jsonb,
  CONSTRAINT kalshi_markets_pkey PRIMARY KEY (id),
  CONSTRAINT kalshi_markets_event_fkey FOREIGN KEY (event_id) REFERENCES public.kalshi_events(id)
);

CREATE TABLE IF NOT EXISTS public.market_search_configs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  market_id uuid NOT NULL UNIQUE,
  search_terms jsonb NOT NULL DEFAULT '[]'::jsonb,
  min_count integer DEFAULT 0,
  logic text DEFAULT 'at_least'::text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT market_search_configs_pkey PRIMARY KEY (id),
  CONSTRAINT market_search_configs_market_fkey FOREIGN KEY (market_id) REFERENCES public.kalshi_markets(id)
);

CREATE TABLE IF NOT EXISTS public.market_term_results (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  market_id uuid NOT NULL,
  persona_id uuid NOT NULL,
  search_term text NOT NULL,
  total_mentions integer NOT NULL DEFAULT 0,
  briefings_with_term integer NOT NULL DEFAULT 0,
  total_briefings integer NOT NULL DEFAULT 0,
  percentage numeric NOT NULL DEFAULT 0,
  trend text NOT NULL DEFAULT 'stable'::text,
  mentions_by_date jsonb NOT NULL DEFAULT '[]'::jsonb,
  context_matches jsonb NOT NULL DEFAULT '[]'::jsonb,
  context_total_matches integer NOT NULL DEFAULT 0,
  context_transcripts_with_matches integer NOT NULL DEFAULT 0,
  validated_mentions integer,
  validated_percentage numeric,
  llm_judgments jsonb,
  news_context text,
  analysis_mode text,
  last_updated timestamp with time zone DEFAULT now(),
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT market_term_results_pkey PRIMARY KEY (id),
  CONSTRAINT market_term_results_market_fkey FOREIGN KEY (market_id) REFERENCES public.kalshi_markets(id),
  CONSTRAINT market_term_results_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id)
);

CREATE TABLE IF NOT EXISTS public.poly_events (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  poly_id text NOT NULL UNIQUE,
  slug text NOT NULL UNIQUE,
  title text,
  description text,
  start_date timestamp with time zone,
  end_date timestamp with time zone,
  active boolean DEFAULT true,
  closed boolean DEFAULT false,
  volume numeric,
  liquidity numeric,
  image text,
  neg_risk boolean DEFAULT false,
  show_public boolean NOT NULL DEFAULT false,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT poly_events_pkey PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS public.poly_markets (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  poly_id text NOT NULL UNIQUE,
  event_id uuid NOT NULL,
  slug text,
  question text,
  group_item_title text,
  outcome_prices jsonb,
  outcomes jsonb,
  last_trade_price numeric,
  one_day_price_change numeric,
  volume numeric,
  active boolean DEFAULT true,
  closed boolean DEFAULT false,
  closed_time timestamp with time zone,
  neg_risk boolean DEFAULT false,
  result text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT poly_markets_pkey PRIMARY KEY (id),
  CONSTRAINT poly_markets_event_fkey FOREIGN KEY (event_id) REFERENCES public.poly_events(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.poly_market_search_configs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  market_id uuid NOT NULL UNIQUE,
  search_terms jsonb NOT NULL DEFAULT '[]'::jsonb,
  min_count integer DEFAULT 0,
  logic text DEFAULT 'at_least'::text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT poly_market_search_configs_pkey PRIMARY KEY (id),
  CONSTRAINT poly_market_search_configs_market_fkey FOREIGN KEY (market_id) REFERENCES public.poly_markets(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.poly_market_term_results (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  market_id uuid NOT NULL,
  persona_id uuid NOT NULL,
  search_term text NOT NULL,
  total_mentions integer NOT NULL DEFAULT 0,
  briefings_with_term integer NOT NULL DEFAULT 0,
  total_briefings integer NOT NULL DEFAULT 0,
  percentage numeric NOT NULL DEFAULT 0,
  trend text NOT NULL DEFAULT 'stable'::text,
  mentions_by_date jsonb NOT NULL DEFAULT '[]'::jsonb,
  context_matches jsonb NOT NULL DEFAULT '[]'::jsonb,
  context_total_matches integer NOT NULL DEFAULT 0,
  context_transcripts_with_matches integer NOT NULL DEFAULT 0,
  last_updated timestamp with time zone DEFAULT now(),
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT poly_market_term_results_pkey PRIMARY KEY (id),
  CONSTRAINT poly_market_term_results_market_fkey FOREIGN KEY (market_id) REFERENCES public.poly_markets(id) ON DELETE CASCADE,
  CONSTRAINT poly_market_term_results_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT poly_market_term_results_unique UNIQUE (market_id, persona_id, search_term)
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_analysis_cache_key ON analysis_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_analysis_cache_expires ON analysis_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_market_search_configs_market ON market_search_configs(market_id);
CREATE INDEX IF NOT EXISTS idx_mtr_persona ON market_term_results(persona_id);
CREATE INDEX IF NOT EXISTS idx_mtr_market_persona ON market_term_results(market_id, persona_id);
