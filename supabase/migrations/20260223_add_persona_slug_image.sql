-- Add slug and image_url to personas for public-facing SaaS
ALTER TABLE public.personas
  ADD COLUMN IF NOT EXISTS slug text UNIQUE,
  ADD COLUMN IF NOT EXISTS image_url text;

-- Index for fast slug lookups (used by public API)
CREATE INDEX IF NOT EXISTS idx_personas_slug ON public.personas(slug);
