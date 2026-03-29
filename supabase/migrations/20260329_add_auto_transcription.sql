-- Auto-transcription: periodic YouTube channel/playlist monitoring and transcription

-- Links a YouTube channel or playlist to a persona for automatic transcription
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
  CONSTRAINT auto_sources_unique_url UNIQUE (youtube_url)
);

-- History log of each automated check run
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

CREATE INDEX idx_auto_runs_source_id ON public.auto_runs (auto_source_id);
CREATE INDEX idx_auto_runs_started_at ON public.auto_runs (started_at DESC);

-- Tracks which videos have been seen per source (dedup + audit)
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
