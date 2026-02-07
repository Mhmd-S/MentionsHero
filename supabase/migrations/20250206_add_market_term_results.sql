-- Precomputed market term analysis per (market, persona, search_term)

CREATE TABLE public.market_term_results (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    market_id uuid NOT NULL,
    persona_id uuid NOT NULL,
    search_term text NOT NULL,
    total_mentions integer NOT NULL DEFAULT 0,
    briefings_with_term integer NOT NULL DEFAULT 0,
    total_briefings integer NOT NULL DEFAULT 0,
    percentage numeric(5,2) NOT NULL DEFAULT 0,
    trend text NOT NULL DEFAULT 'stable',
    mentions_by_date jsonb NOT NULL DEFAULT '[]',
    context_matches jsonb NOT NULL DEFAULT '[]',
    context_total_matches integer NOT NULL DEFAULT 0,
    context_transcripts_with_matches integer NOT NULL DEFAULT 0,
    last_updated timestamptz DEFAULT now(),
    created_at timestamptz DEFAULT now(),
    CONSTRAINT market_term_results_pkey PRIMARY KEY (id),
    CONSTRAINT market_term_results_market_fkey FOREIGN KEY (market_id)
        REFERENCES public.polymarket_markets(id) ON DELETE CASCADE,
    CONSTRAINT market_term_results_persona_fkey FOREIGN KEY (persona_id)
        REFERENCES public.personas(id) ON DELETE CASCADE,
    CONSTRAINT market_term_results_unique UNIQUE (market_id, persona_id, search_term)
);

CREATE INDEX idx_mtr_persona ON market_term_results(persona_id);
CREATE INDEX idx_mtr_market_persona ON market_term_results(market_id, persona_id);
