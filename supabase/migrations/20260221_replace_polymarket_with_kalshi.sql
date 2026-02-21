-- Migration: Replace Polymarket tables with Kalshi tables
-- This drops ALL polymarket-related tables and creates new kalshi equivalents.
-- No data migration — starting fresh.

-- Drop dependent tables first (FK order)
DROP TABLE IF EXISTS public.market_term_results CASCADE;
DROP TABLE IF EXISTS public.market_search_configs CASCADE;
DROP TABLE IF EXISTS public.market_search_results CASCADE;
DROP TABLE IF EXISTS public.persona_polymarket_events CASCADE;
DROP TABLE IF EXISTS public.persona_polymarket_series CASCADE;
DROP TABLE IF EXISTS public.polymarket_markets CASCADE;
DROP TABLE IF EXISTS public.polymarket_events CASCADE;
DROP TABLE IF EXISTS public.polymarket_series CASCADE;

-- Create Kalshi tables

CREATE TABLE public.kalshi_series (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  ticker text NOT NULL UNIQUE,
  title text,
  frequency text,
  category text,
  tags jsonb DEFAULT '[]'::jsonb,
  settlement_sources jsonb DEFAULT '[]'::jsonb,
  fee_type text,
  status text DEFAULT 'active',
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT kalshi_series_pkey PRIMARY KEY (id)
);

CREATE TABLE public.kalshi_events (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  event_ticker text NOT NULL UNIQUE,
  series_ticker text,
  series_id uuid,
  title text,
  sub_title text,
  mutually_exclusive boolean DEFAULT false,
  category text,
  status text DEFAULT 'active',
  strike_date timestamp with time zone,
  strike_period text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT kalshi_events_pkey PRIMARY KEY (id),
  CONSTRAINT kalshi_events_series_fkey FOREIGN KEY (series_id) REFERENCES public.kalshi_series(id) ON DELETE SET NULL
);

CREATE TABLE public.kalshi_markets (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  ticker text NOT NULL UNIQUE,
  event_ticker text NOT NULL,
  event_id uuid NOT NULL,
  market_type text DEFAULT 'binary',
  question text,
  yes_sub_title text,
  no_sub_title text,
  status text DEFAULT 'active',
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
  CONSTRAINT kalshi_markets_pkey PRIMARY KEY (id),
  CONSTRAINT kalshi_markets_event_fkey FOREIGN KEY (event_id) REFERENCES public.kalshi_events(id) ON DELETE CASCADE
);

CREATE TABLE public.persona_kalshi_series (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  persona_id uuid NOT NULL,
  kalshi_series_id uuid NOT NULL,
  folder_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT persona_kalshi_series_pkey PRIMARY KEY (id),
  CONSTRAINT persona_kalshi_series_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT persona_kalshi_series_series_fkey FOREIGN KEY (kalshi_series_id) REFERENCES public.kalshi_series(id) ON DELETE CASCADE,
  CONSTRAINT persona_kalshi_series_folder_fkey FOREIGN KEY (folder_id) REFERENCES public.folders(id) ON DELETE SET NULL,
  CONSTRAINT persona_kalshi_series_unique UNIQUE (persona_id, kalshi_series_id)
);

CREATE TABLE public.market_search_configs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  market_id uuid NOT NULL UNIQUE,
  search_terms jsonb NOT NULL DEFAULT '[]'::jsonb,
  min_count integer DEFAULT 0,
  logic text DEFAULT 'at_least'::text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT market_search_configs_pkey PRIMARY KEY (id),
  CONSTRAINT market_search_configs_market_fkey FOREIGN KEY (market_id) REFERENCES public.kalshi_markets(id) ON DELETE CASCADE
);

CREATE TABLE public.market_term_results (
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
  CONSTRAINT market_term_results_market_fkey FOREIGN KEY (market_id) REFERENCES public.kalshi_markets(id) ON DELETE CASCADE,
  CONSTRAINT market_term_results_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT market_term_results_unique UNIQUE (market_id, persona_id, search_term)
);
