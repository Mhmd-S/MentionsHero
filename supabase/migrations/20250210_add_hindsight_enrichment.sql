-- Add hindsight v2 enrichment columns to market_term_results
ALTER TABLE public.market_term_results
  ADD COLUMN IF NOT EXISTS validated_mentions integer NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS validated_percentage numeric NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS llm_judgments jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS news_context text,
  ADD COLUMN IF NOT EXISTS analysis_mode text NOT NULL DEFAULT 'raw';
