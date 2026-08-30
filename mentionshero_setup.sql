-- =====================================================================
-- MentionsHero -> co-located onto Insteshop LOCAL Supabase (Postgres 15)
-- Named schemas:  public  (active app tables)
--                 analytical  (analytical procurement tables)
-- Applied via: psql -f public_local.sql
--
-- Source of truth: utils/db_refrence.sql (consolidated snapshot) RECONCILED
--   with later migrations for the CURRENT column set:
--     - 20240131_add_speakers_to_transcripts (transcripts.speakers jsonb)
--     - 20250202_add_speakers_tables (speakers / transcript_speakers + CASCADE + unique)
--     - 20260228_add_profile_fields / _paywall_columns / _persona_seo_fields
--     - 20260329_add_auto_transcription (auto_sources / auto_source_videos)
--     - 20260523_add_backfill_limit (auto_sources.backfill_limit)
--     - 20260330_add_analytical_tables (analytical.*)
--     - 20260524_extend_event_tags_metadata (event_tags city/state/country/event_time..)
--     - 20260524_procurement_runs_observability (procurement_runs live-progress cols)
--     - 20260612_analytical_scraping (truth_social_posts.is_retruth; source_type CHECK)
--     - 20260613_procurement_runs_retry (procurement_runs params/retry_of/attempt)
--
-- Does NOT touch Insteshop data in `public`. All app objects are namespaced.
-- auth.* / extensions.* references are shared and preserved as-is.
-- =====================================================================

BEGIN;

CREATE SCHEMA IF NOT EXISTS public;
CREATE SCHEMA IF NOT EXISTS analytical;

SET LOCAL search_path TO public, extensions, public;

-- Required extensions (idempotent; gen_random_uuid() is built-in on PG15,
-- uuid-ossp ensured per co-location convention, installed into `extensions`).
CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA extensions;

-- =====================================================================
-- ACTIVE TABLES  (schema: public)  -- FK-safe creation order
-- =====================================================================

-- personas ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.personas (
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

-- profiles (FK -> shared auth.users) ----------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
  id uuid NOT NULL,
  role text NOT NULL DEFAULT 'client'::text
    CHECK (role = ANY (ARRAY['admin'::text, 'client'::text])),
  stripe_customer_id text,
  first_name text,
  last_name text,
  phone text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT profiles_pkey PRIMARY KEY (id),
  CONSTRAINT profiles_id_fkey FOREIGN KEY (id) REFERENCES auth.users(id)
);

-- folders (self-referencing) ------------------------------------------
CREATE TABLE IF NOT EXISTS public.folders (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL,
  parent_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT folders_pkey PRIMARY KEY (id),
  CONSTRAINT folders_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.folders(id)
);

-- transcripts (FK -> folders) -----------------------------------------
CREATE TABLE IF NOT EXISTS public.transcripts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  youtube_url text NOT NULL,
  transcript text NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  folder_id uuid,
  name text,
  upload_date text,
  is_public boolean NOT NULL DEFAULT false,
  is_premium boolean NOT NULL DEFAULT false,
  speakers jsonb DEFAULT NULL,  -- reconciled from 20240131_add_speakers_to_transcripts
  CONSTRAINT transcripts_pkey PRIMARY KEY (id),
  CONSTRAINT transcripts_folder_id_fkey FOREIGN KEY (folder_id) REFERENCES public.folders(id)
);

-- jobs (FK -> transcripts) --------------------------------------------
CREATE TABLE IF NOT EXISTS public.jobs (
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

-- speakers ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.speakers (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  name text NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT speakers_pkey PRIMARY KEY (id),
  CONSTRAINT speakers_name_key UNIQUE (name)
);

-- transcript_speakers (FK -> transcripts, speakers) -------------------
CREATE TABLE IF NOT EXISTS public.transcript_speakers (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  transcript_id uuid NOT NULL,
  speaker_id uuid NOT NULL,
  segment_count integer NOT NULL DEFAULT 0,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT transcript_speakers_pkey PRIMARY KEY (id),
  CONSTRAINT transcript_speakers_transcript_fkey FOREIGN KEY (transcript_id)
    REFERENCES public.transcripts(id) ON DELETE CASCADE,
  CONSTRAINT transcript_speakers_speaker_fkey FOREIGN KEY (speaker_id)
    REFERENCES public.speakers(id) ON DELETE CASCADE,
  CONSTRAINT transcript_speakers_unique UNIQUE (transcript_id, speaker_id)
);

-- persona_aliases (FK -> personas) ------------------------------------
CREATE TABLE IF NOT EXISTS public.persona_aliases (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  persona_id uuid NOT NULL,
  alias text NOT NULL UNIQUE,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT persona_aliases_pkey PRIMARY KEY (id),
  CONSTRAINT persona_aliases_persona_id_fkey FOREIGN KEY (persona_id) REFERENCES public.personas(id)
);

-- auto_sources (FK -> personas, folders) ------------------------------
CREATE TABLE IF NOT EXISTS public.auto_sources (
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
  backfill_limit integer DEFAULT 500,  -- reconciled from 20260523_add_backfill_limit
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT auto_sources_pkey PRIMARY KEY (id),
  CONSTRAINT auto_sources_persona_fkey FOREIGN KEY (persona_id)
    REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT auto_sources_folder_fkey FOREIGN KEY (folder_id)
    REFERENCES public.folders(id) ON DELETE SET NULL,
  CONSTRAINT auto_sources_unique_persona_url UNIQUE (persona_id, youtube_url)
);

-- auto_source_videos (FK -> auto_sources; job_id has no FK in source) --
CREATE TABLE IF NOT EXISTS public.auto_source_videos (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  auto_source_id uuid NOT NULL,
  youtube_url text NOT NULL,
  video_title text,
  action text NOT NULL CHECK (action IN ('transcribed', 'filtered', 'skipped')),
  job_id uuid,
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT auto_source_videos_pkey PRIMARY KEY (id),
  CONSTRAINT auto_source_videos_source_fkey FOREIGN KEY (auto_source_id)
    REFERENCES public.auto_sources(id) ON DELETE CASCADE,
  CONSTRAINT auto_source_videos_unique UNIQUE (auto_source_id, youtube_url)
);

-- Indexes (public) ----------------------------------------------
CREATE INDEX IF NOT EXISTS idx_transcript_speakers_transcript
  ON public.transcript_speakers (transcript_id);
CREATE INDEX IF NOT EXISTS idx_transcript_speakers_speaker
  ON public.transcript_speakers (speaker_id);
CREATE INDEX IF NOT EXISTS idx_speakers_name_lower
  ON public.speakers (lower(name));

-- =====================================================================
-- ANALYTICAL TABLES  (schema: analytical)
-- Cross-schema FKs -> public.personas / public.transcripts
-- =====================================================================

-- news_items (FK -> personas) -----------------------------------------
CREATE TABLE IF NOT EXISTS analytical.news_items (
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
  CONSTRAINT news_items_pkey PRIMARY KEY (id),
  CONSTRAINT news_items_persona_fkey FOREIGN KEY (persona_id)
    REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT news_items_dedup UNIQUE (persona_id, url)
);

-- truth_social_posts (FK -> personas) ---------------------------------
CREATE TABLE IF NOT EXISTS analytical.truth_social_posts (
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
  is_retruth boolean DEFAULT false,  -- reconciled from 20260612_analytical_scraping
  created_at timestamp with time zone DEFAULT now(),
  CONSTRAINT truth_social_posts_pkey PRIMARY KEY (id),
  CONSTRAINT truth_social_posts_persona_fkey FOREIGN KEY (persona_id)
    REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT truth_social_posts_dedup UNIQUE (persona_id, external_id)
);

-- event_tags (FK -> transcripts) --------------------------------------
-- Reconciled with 20260524_extend_event_tags_metadata:
--   + city/state/country/event_time/event_time_local
--   + expanded event_type + audience_type CHECK taxonomies
CREATE TABLE IF NOT EXISTS analytical.event_tags (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  transcript_id uuid NOT NULL,
  event_type text NOT NULL CHECK (event_type IN (
    'rally', 'press_conference', 'press_briefing', 'interview',
    'prepared_remarks', 'signing_ceremony', 'bilateral_meeting',
    'cabinet_meeting', 'reception', 'ceremony', 'summit', 'roundtable',
    'announcement', 'greeting', 'troop_address', 'other'
  )),
  venue text,
  interviewer text,
  network text,
  is_teleprompter boolean,
  audience_type text CHECK (audience_type IN (
    'supporters', 'general', 'press', 'congress', 'foreign', 'military',
    'cabinet', 'invited', 'industry', 'mixed', 'other'
  )),
  classification_source text NOT NULL DEFAULT 'manual' CHECK (
    classification_source IN ('manual', 'auto_ddgs', 'auto_llm')
  ),
  confidence numeric,
  notes text,
  city text,
  state text,
  country text,
  event_time timestamptz,
  event_time_local text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT event_tags_pkey PRIMARY KEY (id),
  CONSTRAINT event_tags_transcript_fkey FOREIGN KEY (transcript_id)
    REFERENCES public.transcripts(id) ON DELETE CASCADE,
  CONSTRAINT event_tags_unique UNIQUE (transcript_id)
);

-- context_windows (FK -> transcripts, personas) -----------------------
CREATE TABLE IF NOT EXISTS analytical.context_windows (
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
  CONSTRAINT context_windows_pkey PRIMARY KEY (id),
  CONSTRAINT context_windows_transcript_fkey FOREIGN KEY (transcript_id)
    REFERENCES public.transcripts(id) ON DELETE CASCADE,
  CONSTRAINT context_windows_persona_fkey FOREIGN KEY (persona_id)
    REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT context_windows_unique UNIQUE (transcript_id, persona_id)
);

-- procurement_runs (FK -> personas; self-FK retry_of) -----------------
-- Reconciled with 20260524_procurement_runs_observability, 20260613_retry,
-- and 20260612 (source_type CHECK final set; status CHECK adds 'cancelled').
CREATE TABLE IF NOT EXISTS analytical.procurement_runs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  source_type text NOT NULL CHECK (source_type IN (
    'truth_social', 'news_ddgs', 'news_gdelt', 'news_newsapi', 'news_fox',
    'event_tag_auto', 'metadata_backfill'
  )),
  persona_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'running'
    CHECK (status IN ('running', 'completed', 'failed', 'cancelled')),
  items_found integer DEFAULT 0,
  items_new integer DEFAULT 0,
  items_skipped integer DEFAULT 0,
  error_message text,
  details jsonb DEFAULT '[]'::jsonb,
  -- observability (20260524_procurement_runs_observability)
  current_item_index int,
  current_item_name text,
  prompt_tokens bigint DEFAULT 0,
  completion_tokens bigint DEFAULT 0,
  cancel_requested boolean DEFAULT false,
  updated_at timestamptz DEFAULT now(),
  -- retry support (20260613_procurement_runs_retry)
  params jsonb DEFAULT '{}'::jsonb,
  retry_of uuid,
  attempt int DEFAULT 1,
  started_at timestamp with time zone DEFAULT now(),
  completed_at timestamp with time zone,
  CONSTRAINT procurement_runs_pkey PRIMARY KEY (id),
  CONSTRAINT procurement_runs_persona_fkey FOREIGN KEY (persona_id)
    REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT procurement_runs_retry_of_fkey FOREIGN KEY (retry_of)
    REFERENCES analytical.procurement_runs(id) ON DELETE SET NULL
);

-- Indexes (analytical) -----------------------------------
CREATE INDEX IF NOT EXISTS idx_news_items_published_at
  ON analytical.news_items (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_items_persona
  ON analytical.news_items (persona_id);
CREATE INDEX IF NOT EXISTS idx_news_items_persona_source
  ON analytical.news_items (persona_id, source_domain);
CREATE INDEX IF NOT EXISTS idx_news_items_persona_published
  ON analytical.news_items (persona_id, published_at DESC);

CREATE INDEX IF NOT EXISTS idx_ts_posts_posted_at
  ON analytical.truth_social_posts (posted_at DESC);
CREATE INDEX IF NOT EXISTS idx_ts_posts_persona
  ON analytical.truth_social_posts (persona_id);
CREATE INDEX IF NOT EXISTS idx_ts_posts_persona_posted
  ON analytical.truth_social_posts (persona_id, posted_at DESC);

CREATE INDEX IF NOT EXISTS idx_event_tags_type
  ON analytical.event_tags (event_type);
CREATE INDEX IF NOT EXISTS idx_event_tags_event_time
  ON analytical.event_tags (event_time);

CREATE INDEX IF NOT EXISTS idx_procurement_runs_started
  ON analytical.procurement_runs (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_procurement_runs_status
  ON analytical.procurement_runs (status);

-- =====================================================================
-- GRANTS  (replicated pattern for BOTH schemas)
-- =====================================================================

-- public --------------------------------------------------------
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA public TO service_role;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon, authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO anon, authenticated;

-- analytical ---------------------------------------------
GRANT USAGE ON SCHEMA analytical TO anon, authenticated, service_role;
GRANT ALL ON ALL TABLES IN SCHEMA analytical TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA analytical TO service_role;
GRANT ALL ON ALL FUNCTIONS IN SCHEMA analytical TO service_role;
GRANT SELECT ON ALL TABLES IN SCHEMA analytical TO anon, authenticated;

ALTER DEFAULT PRIVILEGES IN SCHEMA analytical GRANT ALL ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytical GRANT ALL ON SEQUENCES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytical GRANT ALL ON FUNCTIONS TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytical GRANT SELECT ON TABLES TO anon, authenticated;

-- =====================================================================
-- SEED  (FK-safe with an EMPTY auth.users -- personas need no auth)
-- =====================================================================
INSERT INTO public.personas (id, name, description, slug, has_model, meta_title, meta_description)
VALUES (
  '11111111-1111-1111-1111-111111111111',
  'Donald Trump',
  'Seed persona for local rehearsal',
  'donald-trump',
  false,
  'Donald Trump',
  'Donald Trump transcripts and analysis'
)
ON CONFLICT DO NOTHING;

-- =====================================================================
-- LOCAL REHEARSAL ONLY  (optional admin profile; touches shared auth.users)
-- Left COMMENTED so the default apply stays FK-safe against an EMPTY
-- auth.users. Uncomment to seed a throwaway admin locally.
-- =====================================================================
-- WITH new_user AS (
--   INSERT INTO auth.users (id, aud, role, email)
--   VALUES (gen_random_uuid(), 'authenticated', 'authenticated', 'local-admin@example.test')
--   RETURNING id
-- )
-- INSERT INTO public.profiles (id, role, first_name, last_name)
-- SELECT id, 'admin', 'Local', 'Admin' FROM new_user
-- ON CONFLICT DO NOTHING;

COMMIT;
