-- Add live-progress + token observability fields to procurement_runs,
-- plus cancel/heartbeat plumbing so the /admin/operations dashboard can
-- cancel in-flight runs and reset stale rows after a crash.

ALTER TABLE analytical.procurement_runs
  ADD COLUMN IF NOT EXISTS current_item_index int,
  ADD COLUMN IF NOT EXISTS current_item_name text,
  ADD COLUMN IF NOT EXISTS prompt_tokens bigint DEFAULT 0,
  ADD COLUMN IF NOT EXISTS completion_tokens bigint DEFAULT 0,
  ADD COLUMN IF NOT EXISTS cancel_requested boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- Allow the new 'cancelled' terminal status on procurement_runs.status.
ALTER TABLE analytical.procurement_runs
  DROP CONSTRAINT IF EXISTS procurement_runs_status_check;
ALTER TABLE analytical.procurement_runs
  ADD CONSTRAINT procurement_runs_status_check
  CHECK (status IN ('running', 'completed', 'failed', 'cancelled'));
