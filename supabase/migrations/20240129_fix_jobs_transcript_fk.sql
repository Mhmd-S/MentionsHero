-- Fix foreign key constraint on jobs table to allow transcript deletion
ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_transcript_id_fkey;
ALTER TABLE jobs ADD CONSTRAINT jobs_transcript_id_fkey
  FOREIGN KEY (transcript_id) REFERENCES transcripts(id) ON DELETE SET NULL;
