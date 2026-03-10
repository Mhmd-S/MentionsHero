-- Polymarket integration tables

-- Polymarket events (no series level, unlike Kalshi)
CREATE TABLE public.poly_events (
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
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT poly_events_pkey PRIMARY KEY (id)
);

-- Polymarket markets (nested within events)
CREATE TABLE public.poly_markets (
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

-- Persona <-> Polymarket event linking
CREATE TABLE public.persona_poly_events (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  persona_id uuid NOT NULL,
  poly_event_id uuid NOT NULL,
  folder_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT persona_poly_events_pkey PRIMARY KEY (id),
  CONSTRAINT persona_poly_events_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT persona_poly_events_event_fkey FOREIGN KEY (poly_event_id) REFERENCES public.poly_events(id) ON DELETE CASCADE,
  CONSTRAINT persona_poly_events_folder_fkey FOREIGN KEY (folder_id) REFERENCES public.folders(id) ON DELETE SET NULL,
  CONSTRAINT persona_poly_events_unique UNIQUE (persona_id, poly_event_id)
);

-- Search configs for Polymarket markets
CREATE TABLE public.poly_market_search_configs (
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

-- Term analysis results for Polymarket markets
CREATE TABLE public.poly_market_term_results (
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
