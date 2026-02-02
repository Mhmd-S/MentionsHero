-- Speaker persistence: normalized speakers and transcript_speakers junction table

CREATE TABLE public.speakers (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    name text NOT NULL,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT speakers_pkey PRIMARY KEY (id),
    CONSTRAINT speakers_name_key UNIQUE (name)
);

CREATE TABLE public.transcript_speakers (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    transcript_id uuid NOT NULL,
    speaker_id uuid NOT NULL,
    segment_count integer NOT NULL DEFAULT 0,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT transcript_speakers_pkey PRIMARY KEY (id),
    CONSTRAINT transcript_speakers_transcript_fkey FOREIGN KEY (transcript_id)
        REFERENCES public.transcripts(id) ON DELETE CASCADE,
    CONSTRAINT transcript_speakers_speaker_fkey FOREIGN KEY (speaker_id)
        REFERENCES public.speakers(id) ON DELETE CASCADE,
    CONSTRAINT transcript_speakers_unique UNIQUE (transcript_id, speaker_id)
);

CREATE INDEX idx_transcript_speakers_transcript ON transcript_speakers(transcript_id);
CREATE INDEX idx_transcript_speakers_speaker ON transcript_speakers(speaker_id);
CREATE INDEX idx_speakers_name_lower ON speakers(lower(name));
