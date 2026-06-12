-- ============================================================
-- Real Truth Social + Fox News scraping support
-- ============================================================
-- Switches Truth Social procurement from the DDG news proxy to real
-- @realDonaldTrump posts (Mastodon API), and news procurement to the Fox
-- dated-sitemap crawler. Both now support arbitrary date ranges, so these
-- columns/indexes back the new range reads + outlet filtering + retruth flag.

-- 1. Distinguish re-truths (reblogs) from original posts.
ALTER TABLE analytical.truth_social_posts
  ADD COLUMN IF NOT EXISTS is_retruth boolean DEFAULT false;

-- 2. Allow the new 'news_fox' procurement source_type (Fox direct sitemap).
--    Re-declares the full allowed set (last set in 20260524_extend_event_tags_metadata).
ALTER TABLE analytical.procurement_runs
  DROP CONSTRAINT IF EXISTS procurement_runs_source_type_check;
ALTER TABLE analytical.procurement_runs
  ADD CONSTRAINT procurement_runs_source_type_check
  CHECK (source_type IN (
    'truth_social', 'news_ddgs', 'news_gdelt', 'news_newsapi', 'news_fox',
    'event_tag_auto', 'metadata_backfill'
  ));

-- 3. Indexes for outlet filtering + persona-scoped date-range reads.
CREATE INDEX IF NOT EXISTS idx_news_items_persona_source
  ON analytical.news_items (persona_id, source_domain);
CREATE INDEX IF NOT EXISTS idx_news_items_persona_published
  ON analytical.news_items (persona_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_ts_posts_persona_posted
  ON analytical.truth_social_posts (persona_id, posted_at DESC);
