-- Create jobs table for tracking transcription job progress
CREATE TABLE jobs (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  youtube_url TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  stage_progress JSONB DEFAULT '{}',
  error_message TEXT,
  transcript_id UUID REFERENCES transcripts(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for fetching active jobs
CREATE INDEX idx_jobs_status ON jobs(status) WHERE status NOT IN ('completed', 'failed');

-- Create index for ordering by creation time
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
