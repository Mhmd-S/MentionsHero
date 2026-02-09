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
CREATE TABLE public.market_search_configs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  market_id uuid NOT NULL UNIQUE,
  search_terms jsonb NOT NULL DEFAULT '[]'::jsonb,
  min_count integer DEFAULT 0,
  logic text DEFAULT 'at_least'::text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT market_search_configs_pkey PRIMARY KEY (id),
  CONSTRAINT market_search_configs_market_fkey FOREIGN KEY (market_id) REFERENCES public.polymarket_markets(id)
);
CREATE TABLE public.market_search_results (
  market_id uuid NOT NULL,
  persona_id uuid NOT NULL,
  count integer NOT NULL DEFAULT 0,
  last_updated timestamp with time zone DEFAULT now(),
  briefings_with_term integer DEFAULT 0,
  total_briefings integer DEFAULT 0,
  percentage numeric DEFAULT 0,
  trend text DEFAULT 'stable'::text,
  mentions_by_date jsonb DEFAULT '[]'::jsonb,
  CONSTRAINT market_search_results_pkey PRIMARY KEY (market_id, persona_id),
  CONSTRAINT market_search_results_market_fkey FOREIGN KEY (market_id) REFERENCES public.polymarket_markets(id),
  CONSTRAINT market_search_results_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id)
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
  last_updated timestamp with time zone DEFAULT now(),
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT market_term_results_pkey PRIMARY KEY (id),
  CONSTRAINT market_term_results_market_fkey FOREIGN KEY (market_id) REFERENCES public.polymarket_markets(id),
  CONSTRAINT market_term_results_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id)
);
CREATE TABLE public.persona_aliases (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  persona_id uuid NOT NULL,
  alias text NOT NULL UNIQUE,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT persona_aliases_pkey PRIMARY KEY (id),
  CONSTRAINT persona_aliases_persona_id_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id)
);
CREATE TABLE public.persona_polymarket_events (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  persona_id uuid NOT NULL,
  polymarket_event_id uuid NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT persona_polymarket_events_pkey PRIMARY KEY (id),
  CONSTRAINT persona_polymarket_events_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id),
  CONSTRAINT persona_polymarket_events_event_fkey FOREIGN KEY (polymarket_event_id) REFERENCES public.polymarket_events(id)
);
CREATE TABLE public.personas (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL,
  description text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT personas_pkey PRIMARY KEY (id)
);
CREATE TABLE public.polymarket_series (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  polymarket_id text NOT NULL UNIQUE,
  slug text NOT NULL UNIQUE,
  title text,
  description text,
  image text,
  icon text,
  series_type text,
  recurrence text,
  active boolean DEFAULT true,
  closed boolean DEFAULT false,
  base_slug text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT polymarket_series_pkey PRIMARY KEY (id)
);
CREATE TABLE public.persona_polymarket_series (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  persona_id uuid NOT NULL,
  polymarket_series_id uuid NOT NULL,
  folder_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT persona_polymarket_series_pkey PRIMARY KEY (id),
  CONSTRAINT persona_polymarket_series_persona_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT persona_polymarket_series_series_fkey FOREIGN KEY (polymarket_series_id) REFERENCES public.polymarket_series(id) ON DELETE CASCADE,
  CONSTRAINT persona_polymarket_series_folder_fkey FOREIGN KEY (folder_id) REFERENCES public.folders(id) ON DELETE SET NULL,
  CONSTRAINT persona_polymarket_series_unique UNIQUE (persona_id, polymarket_series_id)
);
CREATE TABLE public.polymarket_events (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  slug text NOT NULL UNIQUE,
  title text,
  image text,
  start_date timestamp with time zone,
  end_date timestamp with time zone,
  series_id uuid,
  polymarket_id text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT polymarket_events_pkey PRIMARY KEY (id),
  CONSTRAINT polymarket_events_series_fkey FOREIGN KEY (series_id) REFERENCES public.polymarket_series(id) ON DELETE SET NULL
);
CREATE TABLE public.polymarket_markets (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  event_id uuid NOT NULL,
  condition_id text,
  question text,
  slug text,
  active boolean,
  closed boolean,
  outcome_prices jsonb,
  resolved_outcome text,
  closed_time timestamp with time zone,
  resolution_source text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT polymarket_markets_pkey PRIMARY KEY (id),
  CONSTRAINT polymarket_markets_event_fkey FOREIGN KEY (event_id) REFERENCES public.polymarket_events(id)
);
CREATE TABLE public.speakers (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL UNIQUE,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT speakers_pkey PRIMARY KEY (id)
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
CREATE TABLE public.transcripts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  youtube_url text NOT NULL,
  transcript text NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  folder_id uuid,
  name text,
  upload_date text,
  CONSTRAINT transcripts_pkey PRIMARY KEY (id),
  CONSTRAINT transcripts_folder_id_fkey FOREIGN KEY (folder_id) REFERENCES public.folders(id)
);