-- Retry + richer-error support for procurement_runs.
--
-- Adds the input params a run was launched with (so the Operations dashboard
-- can re-run it) and links a retry back to the run it re-ran. `error_message`
-- + `details` already exist (added with the base table / observability
-- migration) and now get surfaced in the UI.

ALTER TABLE analytical.procurement_runs
  -- Input params the run was launched with (scrape date window, metadata
  -- force/limit, …). Enough to re-run the same ingestion via the Retry action.
  ADD COLUMN IF NOT EXISTS params jsonb DEFAULT '{}'::jsonb,
  -- When this run is a retry, the id of the run it re-ran (informational trail).
  ADD COLUMN IF NOT EXISTS retry_of uuid REFERENCES analytical.procurement_runs(id) ON DELETE SET NULL,
  -- 1 for an original run; incremented for each retry in a chain.
  ADD COLUMN IF NOT EXISTS attempt int DEFAULT 1;

-- The dashboard now filters by status; keep that lookup cheap.
CREATE INDEX IF NOT EXISTS idx_procurement_runs_status
  ON analytical.procurement_runs (status);
