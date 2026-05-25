-- Adds a per-source backfill cap used by the one-shot "Backfill" action.
-- NULL means "no cap" (pull every video yt-dlp can list for the source).
ALTER TABLE public.auto_sources
  ADD COLUMN IF NOT EXISTS backfill_limit integer DEFAULT 500;
