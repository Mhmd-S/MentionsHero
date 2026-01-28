-- Add cancellation support to jobs table
ALTER TABLE jobs ADD COLUMN cancel_requested BOOLEAN DEFAULT FALSE;

-- Update index to exclude cancelled jobs from active jobs
DROP INDEX IF EXISTS idx_jobs_status;
CREATE INDEX idx_jobs_status ON jobs(status) WHERE status NOT IN ('completed', 'failed', 'cancelled');
