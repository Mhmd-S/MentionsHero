-- Add youtube_channel_url to personas for channel monitoring
ALTER TABLE public.personas
  ADD COLUMN youtube_channel_url text;

-- Add auto_trade flag to persona-series junction for auto-trading
ALTER TABLE public.persona_polymarket_series
  ADD COLUMN auto_trade boolean NOT NULL DEFAULT false;
