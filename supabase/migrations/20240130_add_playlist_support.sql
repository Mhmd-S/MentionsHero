-- Add playlist-related columns to jobs table
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS playlist_id TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS playlist_name TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS playlist_index INTEGER;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS video_title TEXT;

-- Create index for playlist grouping
CREATE INDEX IF NOT EXISTS idx_jobs_playlist_id ON jobs(playlist_id);
