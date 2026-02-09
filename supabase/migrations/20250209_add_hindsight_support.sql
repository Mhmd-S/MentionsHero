-- Add base_slug column to polymarket_series for grouping related events
ALTER TABLE public.polymarket_series ADD COLUMN IF NOT EXISTS base_slug text;
CREATE INDEX IF NOT EXISTS idx_polymarket_series_base_slug ON polymarket_series(base_slug);
UPDATE public.polymarket_series SET base_slug = regexp_replace(slug, '-\d+$', '') WHERE base_slug IS NULL;
