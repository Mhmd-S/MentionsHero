-- Add speakers column to store extracted speaker names per transcript
ALTER TABLE transcripts ADD COLUMN IF NOT EXISTS speakers jsonb DEFAULT NULL;

COMMENT ON COLUMN transcripts.speakers IS 'Extracted speaker names (array of strings) from transcript text';
