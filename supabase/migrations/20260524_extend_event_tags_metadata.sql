-- Extend analytical.event_tags with per-transcript metadata bundle:
--   - location: city, state, country (venue already exists)
--   - timing: event_time, event_time_local
--   - expanded event_type taxonomy (drops social_media + debate, adds 10 WH-specific types)
--   - expanded audience_type taxonomy (adds military, cabinet, invited, industry, other)
--
-- See plan: per-transcript metadata bundle. Phase 1 schema migration.

-- 1. Add new columns
ALTER TABLE analytical.event_tags
  ADD COLUMN IF NOT EXISTS city text,
  ADD COLUMN IF NOT EXISTS state text,
  ADD COLUMN IF NOT EXISTS country text,
  ADD COLUMN IF NOT EXISTS event_time timestamptz,
  ADD COLUMN IF NOT EXISTS event_time_local text;

-- 2. Backfill any rows using the deprecated event_type values, otherwise the
--    new CHECK constraint will fail.
UPDATE analytical.event_tags
  SET event_type = 'other'
  WHERE event_type IN ('social_media', 'debate');

-- 3. Replace event_type CHECK constraint with the expanded taxonomy.
ALTER TABLE analytical.event_tags
  DROP CONSTRAINT IF EXISTS event_tags_event_type_check;
ALTER TABLE analytical.event_tags
  ADD CONSTRAINT event_tags_event_type_check
  CHECK (event_type IN (
    'rally', 'press_conference', 'press_briefing', 'interview',
    'prepared_remarks', 'signing_ceremony', 'bilateral_meeting',
    'cabinet_meeting', 'reception', 'ceremony', 'summit', 'roundtable',
    'announcement', 'greeting', 'troop_address', 'other'
  ));

-- 4. Replace audience_type CHECK constraint with the expanded taxonomy.
--    (Existing values 'supporters','general','press','congress','foreign','mixed'
--    all remain valid; we just add new options.)
ALTER TABLE analytical.event_tags
  DROP CONSTRAINT IF EXISTS event_tags_audience_type_check;
ALTER TABLE analytical.event_tags
  ADD CONSTRAINT event_tags_audience_type_check
  CHECK (audience_type IN (
    'supporters', 'general', 'press', 'congress', 'foreign', 'military',
    'cabinet', 'invited', 'industry', 'mixed', 'other'
  ));

-- 5. Index event_time so the upcoming UI can sort transcripts by event time
--    without a full scan.
CREATE INDEX IF NOT EXISTS idx_event_tags_event_time
  ON analytical.event_tags (event_time);

-- 6. Expand procurement_runs.source_type to allow the new metadata_backfill
--    audit value (used by metadata_extraction_service.bulk_backfill_metadata).
ALTER TABLE analytical.procurement_runs
  DROP CONSTRAINT IF EXISTS procurement_runs_source_type_check;
ALTER TABLE analytical.procurement_runs
  ADD CONSTRAINT procurement_runs_source_type_check
  CHECK (source_type IN (
    'truth_social', 'news_ddgs', 'news_gdelt', 'news_newsapi',
    'event_tag_auto', 'metadata_backfill'
  ));

-- 7. Grant permissions on the analytical schema to Supabase roles.
--    The original analytical migration (20260330) created the schema but never
--    granted USAGE/SELECT — see Phase 1 troubleshooting in docs/analytical.md.
GRANT USAGE ON SCHEMA analytical TO service_role;
GRANT ALL ON ALL TABLES IN SCHEMA analytical TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA analytical TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytical
  GRANT ALL ON TABLES TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytical
  GRANT ALL ON SEQUENCES TO service_role;

GRANT USAGE ON SCHEMA analytical TO authenticated;
GRANT SELECT ON ALL TABLES IN SCHEMA analytical TO authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA analytical
  GRANT SELECT ON TABLES TO authenticated;
