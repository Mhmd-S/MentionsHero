-- Add paywall columns to transcripts
ALTER TABLE public.transcripts
  ADD COLUMN is_public boolean NOT NULL DEFAULT false,
  ADD COLUMN is_premium boolean NOT NULL DEFAULT false;
