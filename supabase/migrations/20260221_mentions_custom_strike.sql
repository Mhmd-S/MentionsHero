-- Add custom_strike column to kalshi_markets for storing the Kalshi custom_strike data
-- For Mentions markets, this contains {"Word": "term"} which is the tracked term.
ALTER TABLE public.kalshi_markets ADD COLUMN IF NOT EXISTS custom_strike jsonb;
