-- Add folder_id to persona_polymarket_series so each link scopes transcripts to a folder tree
ALTER TABLE public.persona_polymarket_series
    ADD COLUMN folder_id uuid REFERENCES public.folders(id) ON DELETE SET NULL;
