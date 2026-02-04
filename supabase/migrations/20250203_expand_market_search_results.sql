-- Expand market_search_results to store full analysis data

ALTER TABLE public.market_search_results
ADD COLUMN IF NOT EXISTS briefings_with_term integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS total_briefings integer DEFAULT 0,
ADD COLUMN IF NOT EXISTS percentage numeric(5,2) DEFAULT 0,
ADD COLUMN IF NOT EXISTS trend text DEFAULT 'stable',
ADD COLUMN IF NOT EXISTS mentions_by_date jsonb DEFAULT '[]';
