-- Add folder_id and name columns to transcripts table
ALTER TABLE transcripts ADD COLUMN folder_id UUID REFERENCES folders(id) ON DELETE SET NULL;
ALTER TABLE transcripts ADD COLUMN name TEXT;

-- Create index for folder lookups
CREATE INDEX idx_transcripts_folder_id ON transcripts(folder_id);

-- Populate names for existing records from video ID
UPDATE transcripts SET name = COALESCE(
  SUBSTRING(youtube_url FROM 'v=([a-zA-Z0-9_-]{11})'),
  'Transcript ' || TO_CHAR(created_at, 'YYYY-MM-DD')
) WHERE name IS NULL;
