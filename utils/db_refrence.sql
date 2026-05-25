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
  clob_token_ids jsonb,
  condition_id text,
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

CREATE TABLE public.poly_orders (
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
  CONSTRAINT poly_orders_market_fkey FOREIGN KEY (market_id) REFERENCES public.poly_markets(id) ON DELETE CASCADE
);

CREATE TABLE public.poly_trades (
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
  CONSTRAINT poly_trades_order_fkey FOREIGN KEY (order_id) REFERENCES public.poly_orders(id) ON DELETE SET NULL,
  CONSTRAINT poly_trades_market_fkey FOREIGN KEY (market_id) REFERENCES public.poly_markets(id) ON DELETE CASCADE
);

CREATE TABLE public.poly_positions (
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
  CONSTRAINT poly_positions_market_fkey FOREIGN KEY (market_id) REFERENCES public.poly_markets(id) ON DELETE CASCADE,
  CONSTRAINT poly_positions_unique UNIQUE (market_id, outcome)
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

-- Auto-transcription tables

CREATE TABLE public.auto_sources (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  persona_id uuid NOT NULL,
  source_type text NOT NULL CHECK (source_type IN ('channel', 'playlist')),
  youtube_url text NOT NULL,
  source_name text,
  folder_id uuid,
  speaker_hint text,
  check_interval_minutes integer NOT NULL DEFAULT 360,
  max_videos_per_check integer NOT NULL DEFAULT 5,
  is_enabled boolean NOT NULL DEFAULT true,
  title_filter text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT auto_sources_pkey PRIMARY KEY (id),
  CONSTRAINT auto_sources_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT auto_sources_folder_fkey FOREIGN KEY (folder_id) REFERENCES public.folders(id) ON DELETE SET NULL,
  CONSTRAINT auto_sources_unique_persona_url UNIQUE (persona_id, youtube_url)
);

CREATE TABLE public.auto_runs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  auto_source_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
  videos_found integer NOT NULL DEFAULT 0,
  videos_new integer NOT NULL DEFAULT 0,
  videos_queued integer NOT NULL DEFAULT 0,
  videos_skipped integer NOT NULL DEFAULT 0,
  error_message text,
  details jsonb DEFAULT '[]'::jsonb,
  started_at timestamp with time zone DEFAULT now(),
  completed_at timestamp with time zone,
  CONSTRAINT auto_runs_pkey PRIMARY KEY (id),
  CONSTRAINT auto_runs_source_fkey FOREIGN KEY (auto_source_id) REFERENCES public.auto_sources(id) ON DELETE CASCADE
);

CREATE TABLE public.auto_source_videos (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  auto_source_id uuid NOT NULL,
  youtube_url text NOT NULL,
  video_title text,
  action text NOT NULL CHECK (action IN ('transcribed', 'filtered', 'skipped')),
  job_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT auto_source_videos_pkey PRIMARY KEY (id),
  CONSTRAINT auto_source_videos_source_fkey FOREIGN KEY (auto_source_id) REFERENCES public.auto_sources(id) ON DELETE CASCADE,
  CONSTRAINT auto_source_videos_unique UNIQUE (auto_source_id, youtube_url)
);

-- ============================================================
-- Analytical Data Procurement Tables (analytical schema)
-- ============================================================

CREATE SCHEMA IF NOT EXISTS analytical;

CREATE TABLE analytical.news_items (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  persona_id uuid NOT NULL,
  title text NOT NULL,
  body text,
  url text NOT NULL,
  source_name text,
  source_domain text,
  published_at timestamp with time zone NOT NULL,
  procurement_source text NOT NULL DEFAULT 'ddgs',
  sentiment_score numeric,
  topics jsonb DEFAULT '[]'::jsonb,
  raw_payload jsonb,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT analytical_news_items_pkey PRIMARY KEY (id),
  CONSTRAINT analytical_news_items_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT analytical_news_items_dedup UNIQUE (persona_id, url)
);

CREATE TABLE analytical.truth_social_posts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  persona_id uuid NOT NULL,
  external_id text,
  content text NOT NULL,
  post_url text,
  posted_at timestamp with time zone NOT NULL,
  source text NOT NULL DEFAULT 'ddgs',
  media_urls jsonb DEFAULT '[]'::jsonb,
  engagement jsonb,
  raw_payload jsonb,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT analytical_truth_social_posts_pkey PRIMARY KEY (id),
  CONSTRAINT analytical_truth_social_posts_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT analytical_truth_social_posts_dedup UNIQUE (persona_id, external_id)
);

CREATE TABLE analytical.event_tags (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  transcript_id uuid NOT NULL,
  event_type text NOT NULL CHECK (event_type IN ('rally', 'press_conference', 'interview', 'prepared_remarks', 'social_media', 'debate', 'other')),
  venue text,
  interviewer text,
  network text,
  is_teleprompter boolean,
  audience_type text CHECK (audience_type IN ('supporters', 'general', 'press', 'congress', 'foreign', 'mixed')),
  classification_source text NOT NULL DEFAULT 'manual' CHECK (classification_source IN ('manual', 'auto_ddgs', 'auto_llm')),
  confidence numeric,
  notes text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT analytical_event_tags_pkey PRIMARY KEY (id),
  CONSTRAINT analytical_event_tags_transcript_fkey FOREIGN KEY (transcript_id) REFERENCES public.transcripts(id) ON DELETE CASCADE,
  CONSTRAINT analytical_event_tags_unique UNIQUE (transcript_id)
);

CREATE TABLE analytical.context_windows (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  transcript_id uuid NOT NULL,
  persona_id uuid NOT NULL,
  window_start timestamp with time zone NOT NULL,
  window_end timestamp with time zone NOT NULL,
  truth_social_post_count integer DEFAULT 0,
  news_item_count integer DEFAULT 0,
  news_sentiment_avg numeric,
  top_news_topics jsonb DEFAULT '[]'::jsonb,
  truth_social_topics jsonb DEFAULT '[]'::jsonb,
  market_snapshot jsonb,
  computed_at timestamp with time zone DEFAULT now(),
  CONSTRAINT analytical_context_windows_pkey PRIMARY KEY (id),
  CONSTRAINT analytical_context_windows_transcript_fkey FOREIGN KEY (transcript_id) REFERENCES public.transcripts(id) ON DELETE CASCADE,
  CONSTRAINT analytical_context_windows_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT analytical_context_windows_unique UNIQUE (transcript_id, persona_id)
);

CREATE TABLE analytical.procurement_runs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  source_type text NOT NULL CHECK (source_type IN ('truth_social', 'news_ddgs', 'news_gdelt', 'news_newsapi', 'event_tag_auto')),
  persona_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
  items_found integer DEFAULT 0,
  items_new integer DEFAULT 0,
  items_skipped integer DEFAULT 0,
  error_message text,
  details jsonb DEFAULT '[]'::jsonb,
  started_at timestamp with time zone DEFAULT now(),
  completed_at timestamp with time zone,
  CONSTRAINT analytical_procurement_runs_pkey PRIMARY KEY (id),
  CONSTRAINT analytical_procurement_runs_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id) ON DELETE CASCADE
);