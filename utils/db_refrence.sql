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
CREATE TABLE public.transcripts (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  youtube_url text NOT NULL,
  transcript text NOT NULL,
  created_at timestamp with time zone DEFAULT now(),
  folder_id uuid,
  name text,
  CONSTRAINT transcripts_pkey PRIMARY KEY (id),
  CONSTRAINT transcripts_folder_id_fkey FOREIGN KEY (folder_id) REFERENCES public.folders(id)
);