-- Analytical data procurement tables for Trump prediction model
-- Uses separate 'analytical' schema to isolate from production tables
-- FKs reference public.personas and public.transcripts

CREATE SCHEMA IF NOT EXISTS analytical;

-- ============================================================
-- Pillar 1: Preceding Context ("The Atmosphere")
-- ============================================================

-- News headlines/snippets about the persona
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
  CONSTRAINT news_items_pkey PRIMARY KEY (id),
  CONSTRAINT news_items_persona_fkey FOREIGN KEY (persona_id)
    REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT news_items_dedup UNIQUE (persona_id, url)
);

CREATE INDEX idx_news_items_published_at ON analytical.news_items (published_at DESC);
CREATE INDEX idx_news_items_persona ON analytical.news_items (persona_id);

-- Truth Social posts (via ddgs proxy or direct scraping)
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
  CONSTRAINT truth_social_posts_pkey PRIMARY KEY (id),
  CONSTRAINT truth_social_posts_persona_fkey FOREIGN KEY (persona_id)
    REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT truth_social_posts_dedup UNIQUE (persona_id, external_id)
);

CREATE INDEX idx_ts_posts_posted_at ON analytical.truth_social_posts (posted_at DESC);
CREATE INDEX idx_ts_posts_persona ON analytical.truth_social_posts (persona_id);

-- ============================================================
-- Pillar 2: Event Context ("The Arena")
-- ============================================================

-- Event type classification for transcripts
CREATE TABLE analytical.event_tags (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  transcript_id uuid NOT NULL,
  event_type text NOT NULL CHECK (event_type IN (
    'rally', 'press_conference', 'interview',
    'prepared_remarks', 'social_media', 'debate', 'other'
  )),
  venue text,
  interviewer text,
  network text,
  is_teleprompter boolean,
  audience_type text CHECK (audience_type IN (
    'supporters', 'general', 'press', 'congress', 'foreign', 'mixed'
  )),
  classification_source text NOT NULL DEFAULT 'manual' CHECK (
    classification_source IN ('manual', 'auto_ddgs', 'auto_llm')
  ),
  confidence numeric,
  notes text,
  created_at timestamp with time zone DEFAULT now(),
  updated_at timestamp with time zone DEFAULT now(),
  CONSTRAINT event_tags_pkey PRIMARY KEY (id),
  CONSTRAINT event_tags_transcript_fkey FOREIGN KEY (transcript_id)
    REFERENCES public.transcripts(id) ON DELETE CASCADE,
  CONSTRAINT event_tags_unique UNIQUE (transcript_id)
);

CREATE INDEX idx_event_tags_type ON analytical.event_tags (event_type);

-- ============================================================
-- Context windows: pre-speech atmosphere snapshots
-- ============================================================

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
  CONSTRAINT context_windows_pkey PRIMARY KEY (id),
  CONSTRAINT context_windows_transcript_fkey FOREIGN KEY (transcript_id)
    REFERENCES public.transcripts(id) ON DELETE CASCADE,
  CONSTRAINT context_windows_persona_fkey FOREIGN KEY (persona_id)
    REFERENCES public.personas(id) ON DELETE CASCADE,
  CONSTRAINT context_windows_unique UNIQUE (transcript_id, persona_id)
);

-- ============================================================
-- Procurement audit log
-- ============================================================

CREATE TABLE analytical.procurement_runs (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  source_type text NOT NULL CHECK (source_type IN (
    'truth_social', 'news_ddgs', 'news_gdelt', 'news_newsapi', 'event_tag_auto'
  )),
  persona_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'running' CHECK (status IN ('running', 'completed', 'failed')),
  items_found integer DEFAULT 0,
  items_new integer DEFAULT 0,
  items_skipped integer DEFAULT 0,
  error_message text,
  details jsonb DEFAULT '[]'::jsonb,
  started_at timestamp with time zone DEFAULT now(),
  completed_at timestamp with time zone,
  CONSTRAINT procurement_runs_pkey PRIMARY KEY (id),
  CONSTRAINT procurement_runs_persona_fkey FOREIGN KEY (persona_id)
    REFERENCES public.personas(id) ON DELETE CASCADE
);

CREATE INDEX idx_procurement_runs_started ON analytical.procurement_runs (started_at DESC);
