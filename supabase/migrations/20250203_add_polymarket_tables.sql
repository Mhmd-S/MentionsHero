-- Polymarket integration: events, markets, persona associations, search configs and results

CREATE TABLE public.polymarket_events (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    slug text NOT NULL,
    title text,
    image text,
    start_date timestamptz,
    end_date timestamptz,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    CONSTRAINT polymarket_events_pkey PRIMARY KEY (id),
    CONSTRAINT polymarket_events_slug_key UNIQUE (slug)
);

CREATE TABLE public.polymarket_markets (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    event_id uuid NOT NULL,
    condition_id text,
    question text,
    slug text,
    active boolean,
    closed boolean,
    outcome_prices jsonb,
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    CONSTRAINT polymarket_markets_pkey PRIMARY KEY (id),
    CONSTRAINT polymarket_markets_event_fkey FOREIGN KEY (event_id)
        REFERENCES public.polymarket_events(id) ON DELETE CASCADE
);

CREATE INDEX idx_polymarket_markets_event_id ON polymarket_markets(event_id);
CREATE UNIQUE INDEX idx_polymarket_markets_condition_id ON polymarket_markets(condition_id) WHERE condition_id IS NOT NULL;

CREATE TABLE public.persona_polymarket_events (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    persona_id uuid NOT NULL,
    polymarket_event_id uuid NOT NULL,
    created_at timestamptz DEFAULT now(),
    CONSTRAINT persona_polymarket_events_pkey PRIMARY KEY (id),
    CONSTRAINT persona_polymarket_events_persona_fkey FOREIGN KEY (persona_id)
        REFERENCES public.personas(id) ON DELETE CASCADE,
    CONSTRAINT persona_polymarket_events_event_fkey FOREIGN KEY (polymarket_event_id)
        REFERENCES public.polymarket_events(id) ON DELETE CASCADE,
    CONSTRAINT persona_polymarket_events_unique UNIQUE (persona_id, polymarket_event_id)
);

CREATE INDEX idx_persona_polymarket_events_persona ON persona_polymarket_events(persona_id);
CREATE INDEX idx_persona_polymarket_events_event ON persona_polymarket_events(polymarket_event_id);

CREATE TABLE public.market_search_configs (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    market_id uuid NOT NULL,
    search_terms jsonb NOT NULL DEFAULT '[]',
    min_count integer DEFAULT 0,
    logic text DEFAULT 'at_least',
    created_at timestamptz DEFAULT now(),
    updated_at timestamptz DEFAULT now(),
    CONSTRAINT market_search_configs_pkey PRIMARY KEY (id),
    CONSTRAINT market_search_configs_market_fkey FOREIGN KEY (market_id)
        REFERENCES public.polymarket_markets(id) ON DELETE CASCADE,
    CONSTRAINT market_search_configs_market_key UNIQUE (market_id)
);

CREATE INDEX idx_market_search_configs_market ON market_search_configs(market_id);

CREATE TABLE public.market_search_results (
    market_id uuid NOT NULL,
    persona_id uuid NOT NULL,
    count integer NOT NULL DEFAULT 0,
    last_updated timestamptz DEFAULT now(),
    CONSTRAINT market_search_results_pkey PRIMARY KEY (market_id, persona_id),
    CONSTRAINT market_search_results_market_fkey FOREIGN KEY (market_id)
        REFERENCES public.polymarket_markets(id) ON DELETE CASCADE,
    CONSTRAINT market_search_results_persona_fkey FOREIGN KEY (persona_id)
        REFERENCES public.personas(id) ON DELETE CASCADE
);

CREATE INDEX idx_market_search_results_persona ON market_search_results(persona_id);
