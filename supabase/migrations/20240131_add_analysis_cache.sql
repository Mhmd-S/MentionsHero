-- Create analysis_cache table for caching NLP analysis results
CREATE TABLE IF NOT EXISTS analysis_cache (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  cache_key TEXT UNIQUE NOT NULL,
  result JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ
);

-- Index for fast cache key lookups
CREATE INDEX IF NOT EXISTS idx_analysis_cache_key ON analysis_cache(cache_key);

-- Index for expiration queries
CREATE INDEX IF NOT EXISTS idx_analysis_cache_expires ON analysis_cache(expires_at);

-- Function to clean up expired cache entries
CREATE OR REPLACE FUNCTION cleanup_expired_analysis_cache()
RETURNS void AS $$
BEGIN
  DELETE FROM analysis_cache WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;
