-- Track which transcripts each client user has read (for free tier metering)
CREATE TABLE IF NOT EXISTS public.transcript_reads (
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL,
  transcript_id uuid NOT NULL REFERENCES public.transcripts(id) ON DELETE CASCADE,
  read_at timestamp with time zone DEFAULT now(),
  CONSTRAINT transcript_reads_pkey PRIMARY KEY (id),
  CONSTRAINT transcript_reads_unique UNIQUE (user_id, transcript_id)
);

-- Index for monthly read count query: WHERE user_id = ? AND read_at >= ?
CREATE INDEX IF NOT EXISTS idx_transcript_reads_user_month
  ON public.transcript_reads(user_id, read_at DESC);
