-- Add show_public flag to event tables for admin-controlled public visibility
ALTER TABLE public.kalshi_events ADD COLUMN show_public boolean NOT NULL DEFAULT false;
ALTER TABLE public.poly_events ADD COLUMN show_public boolean NOT NULL DEFAULT false;
