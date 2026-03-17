-- WARNING: This schema is for context only and is not meant to be run.
-- Table order and constraints may not be valid for execution.

CREATE TABLE public.analysis_cache (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  cache_key text NOT NULL UNIQUE,
  result jsonb NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  expires_at timestamp with time zone,
  CONSTRAINT analysis_cache_pkey PRIMARY KEY (id)
);
cd
CREATE TABLE public.folders (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL,
  parent_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT folders_pkey PRIMARY KEY (id),
  CONSTRAINT folders_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.folders(id)
);

CREATE TABLE public.jobs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  youtube_url text NOT NULL,
  status text NOT NULL DEFAULT 'pending'::text,
  stage_progress jsonb DEFAULT '{}'::jsonb,
  error_message text,
  transcript_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  cancel_requested boolean DEFAULT false,
  playlist_id text,
  playlist_name text,
  playlist_index integer,
  video_title text,
  CONSTRAINT jobs_pkey PRIMARY KEY (id),
  CONSTRAINT jobs_transcript_id_fkey FOREIGN KEY (transcript_id) REFERENCES public.transcripts(id)
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
  status text DEFAULT 'active'::text,
  strike_date timestamp with time zone,
  strike_period text,
  show_public boolean NOT NULL DEFAULT false,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT kalshi_events_pkey PRIMARY KEY (id),
  CONSTRAINT kalshi_events_series_fkey FOREIGN KEY (series_id) REFERENCES public.kalshi_series(id)
);

CREATE TABLE public.kalshi_markets (
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

CREATE TABLE public.kalshi_series (
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

CREATE TABLE public.market_search_configs (
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
  CONSTRAINT market_term_results_market_fkey FOREIGN KEY (market_id) REFERENCES public.kalshi_markets(id),
  CONSTRAINT market_term_results_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id)
);

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
  show_public boolean NOT NULL DEFAULT false,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT poly_events_pkey PRIMARY KEY (id)
);

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

-- persona_poly_events table DEPRECATED and removed

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

CREATE TABLE public.ml_training_jobs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  persona_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'pending'::text,
  stage_progress jsonb DEFAULT '{}'::jsonb,
  error_message text,
  total_segments integer DEFAULT 0,
  train_segments integer DEFAULT 0,
  valid_segments integer DEFAULT 0,
  test_segments integer DEFAULT 0,
  config jsonb DEFAULT '{}'::jsonb,
  adapter_path text,
  data_path text,
  final_train_loss numeric,
  final_valid_loss numeric,
  training_duration_seconds integer,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  completed_at timestamp with time zone,
  cancel_requested boolean DEFAULT false,
  CONSTRAINT ml_training_jobs_pkey PRIMARY KEY (id),
  CONSTRAINT ml_training_jobs_persona_id_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id)
);

CREATE TABLE public.persona_aliases (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  persona_id uuid NOT NULL,
  alias text NOT NULL UNIQUE,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT persona_aliases_pkey PRIMARY KEY (id),
  CONSTRAINT persona_aliases_persona_id_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id)
);

-- persona_kalshi_series table DEPRECATED and removed

CREATE TABLE public.personas (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL,
  description text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  last_trained_at timestamp with time zone,
  has_model boolean DEFAULT false,
  slug text UNIQUE,
  image_url text,
  meta_title text,
  meta_description text,
  CONSTRAINT personas_pkey PRIMARY KEY (id)
);

CREATE TABLE public.profiles (
  id uuid NOT NULL,
  role text NOT NULL DEFAULT 'client'::text CHECK (role = ANY (ARRAY['admin'::text, 'client'::text])),
  stripe_customer_id text,
  first_name text,
  last_name text,
  phone text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT profiles_pkey PRIMARY KEY (id),
  CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);

CREATE TABLE public.speakers (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT speakers_pkey PRIMARY KEY (id)
);

CREATE TABLE public.transcript_reads (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  transcript_id uuid NOT NULL,
  read_at timestamp with time zone DEFAULT now(),
  CONSTRAINT transcript_reads_pkey PRIMARY KEY (id),
  CONSTRAINT transcript_reads_transcript_id_fkey FOREIGN KEY (transcript_id) REFERENCES public.transcripts(id)
);

CREATE TABLE public.transcript_speakers (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  transcript_id uuid NOT NULL,
  speaker_id uuid NOT NULL,
  segment_count integer NOT NULL DEFAULT 0,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT transcript_speakers_pkey PRIMARY KEY (id),
  CONSTRAINT transcript_speakers_transcript_fkey FOREIGN KEY (transcript_id) REFERENCES public.transcripts(id),
  CONSTRAINT transcript_speakers_speaker_fkey FOREIGN KEY (speaker_id) REFERENCES public.speakers(id)
);

CREATE TABLE public.subscriptions (
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

CREATE TABLE public.transcripts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  youtube_url text NOT NULL,
  transcript text NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  folder_id uuid,
  name text,
  upload_date text,
  is_public boolean NOT NULL DEFAULT false,
  is_premium boolean NOT NULL DEFAULT false,
  CONSTRAINT transcripts_pkey PRIMARY KEY (id),
  CONSTRAINT transcripts_folder_id_fkey FOREIGN KEY (folder_id) REFERENCES public.folders(id)
);