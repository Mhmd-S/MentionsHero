-- Close a hole opened by 20260830_add_missing_market_and_billing_tables.sql.
--
-- That migration generated its DDL from utils/db_refrence.sql, which records only
-- CREATE TABLE statements — not row-level-security state. Tables created that way
-- default to RLS disabled, so all 11 new tables landed unprotected while every
-- pre-existing table in this database has RLS enabled.
--
-- That matters because the Supabase publishable/anon key is, by design, shipped to
-- the browser: it is serialised into Nuxt's runtimeConfig.public and readable from
-- page source. With RLS off, that key is enough to read `subscriptions` (user_id,
-- stripe_customer_id, stripe_subscription_id, status) and the entire market dataset
-- directly through the PostgREST API, bypassing the FastAPI backend completely.
--
-- The posture below matches the rest of the schema: RLS enabled with NO policies,
-- i.e. deny everything to `anon` and `authenticated`. Nothing in the app breaks,
-- because every read and write goes through the backend on the service key, and
-- `service_role` bypasses RLS. `profiles` keeps its one deliberate SELECT policy
-- (owner-only) from 20260830_auth_rebuild_profiles.sql.
--
-- Safe to re-run.

alter table public.analysis_cache              enable row level security;
alter table public.subscriptions               enable row level security;

alter table public.kalshi_series               enable row level security;
alter table public.kalshi_events               enable row level security;
alter table public.kalshi_markets              enable row level security;
alter table public.market_search_configs       enable row level security;
alter table public.market_term_results         enable row level security;

alter table public.poly_events                 enable row level security;
alter table public.poly_markets                enable row level security;
alter table public.poly_market_search_configs  enable row level security;
alter table public.poly_market_term_results    enable row level security;
