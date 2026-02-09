-- Add Polymarket Series support: series tables, event/market columns

-- 1. polymarket_series table
CREATE TABLE public.polymarket_series (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    polymarket_id text NOT NULL,
    slug text NOT NULL,
    title text,
    description text,
    image text,
    icon text,
    series_type text,
    recurrence text,
    active boolean DEFAULT true,
    closed boolean DEFAULT false,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    CONSTRAINT polymarket_series_pkey PRIMARY KEY (id),
    CONSTRAINT polymarket_series_polymarket_id_key UNIQUE (polymarket_id),
    CONSTRAINT polymarket_series_slug_key UNIQUE (slug)
);

-- 2. persona_polymarket_series junction table
CREATE TABLE public.persona_polymarket_series (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    persona_id uuid NOT NULL,
    polymarket_series_id uuid NOT NULL,
    created_at timestamptz DEFAULT now(),
    CONSTRAINT persona_polymarket_series_pkey PRIMARY KEY (id),
    CONSTRAINT persona_polymarket_series_persona_fkey FOREIGN KEY (persona_id)
        REFERENCES public.personas(id) ON DELETE CASCADE,
    CONSTRAINT persona_polymarket_series_series_fkey FOREIGN KEY (polymarket_series_id)
        REFERENCES public.polymarket_series(id) ON DELETE CASCADE,
    CONSTRAINT persona_polymarket_series_unique UNIQUE (persona_id, polymarket_series_id)
);

CREATE INDEX idx_persona_polymarket_series_persona ON persona_polymarket_series(persona_id);
CREATE INDEX idx_persona_polymarket_series_series ON persona_polymarket_series(polymarket_series_id);

-- 3. Add series_id and polymarket_id to polymarket_events
ALTER TABLE public.polymarket_events
    ADD COLUMN series_id uuid REFERENCES public.polymarket_series(id) ON DELETE SET NULL;

ALTER TABLE public.polymarket_events
    ADD COLUMN polymarket_id text;

CREATE UNIQUE INDEX idx_polymarket_events_polymarket_id
    ON polymarket_events(polymarket_id) WHERE polymarket_id IS NOT NULL;

CREATE INDEX idx_polymarket_events_series ON polymarket_events(series_id);

-- 4. Add resolution fields to polymarket_markets
ALTER TABLE public.polymarket_markets
    ADD COLUMN resolved_outcome text;

ALTER TABLE public.polymarket_markets
    ADD COLUMN closed_time timestamptz;

ALTER TABLE public.polymarket_markets
    ADD COLUMN resolution_source text;
