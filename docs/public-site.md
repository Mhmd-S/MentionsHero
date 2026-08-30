# Public Website & Stripe Paywall

## Overview

The platform has two distinct areas:
- **Public site** (`/`, `/personas/*`, `/transcripts/*`, `/markets/*`, `/pricing`, `/account`) — browseable by anyone, with optional paywall
- **Admin area** (`/admin/*`) — existing features behind admin auth

## Architecture

### Auth Model

Auth is the official **`@nuxtjs/supabase`** module. It owns the browser and server clients,
cookie-based sessions and SSR hydration; the app adds only what the module cannot know about.

Role-based access lives in the `profiles` table:
- `profiles.role = 'admin'` — full admin access
- `profiles.role = 'client'` — public user (free or subscribed)

**The database creates profile rows, not the browser.** `on_auth_user_created` fires on every
`auth.users` insert and writes the matching `public.profiles` row
(`supabase/migrations/20260830_auth_rebuild_profiles.sql`). This replaced a browser call to a
public `POST /api/profile/init` made immediately after `signUp()`. That call was the single
biggest source of broken accounts: if the tab closed, the network blipped, or the user confirmed
their email on a different device, no profile row was ever created — and a user without a profile
row could not check out (`stripe_service` used `.single()`), could not load `/account`, and could
never be an admin. `backend/services/profile_service.ensure_profile()` is the second, independent
guarantee: any read repairs a missing row instead of 500ing.

**Session state**
| Piece | Source | Notes |
|-------|--------|-------|
| session | `useSupabaseSession()` | `Omit<Session, 'user'>`, hydrated from cookies during SSR |
| user | `useSupabaseUser()` | **JWT claims, not a `User`** — the id is `user.sub`, not `user.id` |
| role / profile | `useProfile()` | fetched from `GET /api/profile`; the role is not a JWT claim |
| subscription | `useSubscription()` | all `useState`, shared across the app |

`app/plugins/session.client.ts` loads the profile and the subscription once when a session
appears and clears both on sign-out. Pages no longer fetch subscription state themselves —
`/pricing` used to forget, which showed paying subscribers an enabled **Subscribe** button.

`useAuth()` is a thin facade over the above and keeps the API the app already imported
(`session`, `role`, `login`, `logout`, `getAccessToken`), plus `signup`, `resendConfirmation`
and `sendPasswordReset`.

**Signup collects email and password only.** Name and phone are optional fields on `/account`.
Anything passed through `signUp({ options: { data } })` still lands in `raw_user_meta_data` and
is picked up by the trigger.

### Email confirmation

Confirmation is required, and it is verified **server-side**:

`server/routes/auth/confirm.get.ts` is the landing point for every Supabase auth email — signup,
magic link, password recovery, email change. It calls `verifyOtp` with the `token_hash`, which
sets the session cookie on the response, so the user arrives already signed in and is never asked
for details a second time.

The route handles three shapes so nothing breaks mid-migration:
1. `?token_hash=&type=` → `verifyOtp` (preferred — works from any device)
2. `?code=` → `exchangeCodeForSession` (the stock `{{ .ConfirmationURL }}` template under PKCE;
   only works in the browser that started the signup, because PKCE keeps the code verifier there)
3. neither → redirect onward, letting the browser client pick up an implicit-flow hash fragment

It lives at `/auth/confirm`, deliberately **not** `/confirm` (the module's default
`redirectOptions.callback`, where it expects a client page) and **not** under `/api/**` (proxied
to FastAPI by `routeRules`).

**Required Supabase dashboard configuration** — the code cannot set these:
- Authentication → URL Configuration → Redirect URLs: `http://localhost:3000/**`,
  `https://mentionshero.com/**`, `https://www.mentionshero.com/**`
- Authentication → Emails → Confirm signup: replace the `{{ .ConfirmationURL }}` link with
  `{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=signup`
- Same edit for Magic Link (`type=magiclink`), Change Email (`type=email_change`) and
  Reset Password (`type=recovery`)

### Route guard

`supabase.redirect` is **false** in `nuxt.config.ts`. The module ships a `global-auth` middleware
that redirects everything not in an allow-list to `/login`; on a site that is public by default
that is the wrong shape, because one forgotten route silently becomes a login wall.
`app/middleware/auth.global.ts` is the only thing that redirects. Because the session is hydrated
from cookies during SSR, the redirect now happens on the server — no more rendering a protected
page and bouncing a beat later.

### Backend token verification

`backend/core/auth.py` verifies tokens **locally** against the project's JWKS
(`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, ES256). It previously called
`supabase.auth.get_user(token)` on every request — a round-trip to Supabase Auth before any
endpoint could run, on every page load, poll and SSE reconnect.

- The key set is cached in-process (`PyJWKClient`, 10-minute lifespan) and refetched automatically
  on key rotation or an unknown `kid`.
- `SUPABASE_JWT_SECRET` handles projects still on the legacy symmetric HS256 secret. `HS256` is
  never accepted against a JWKS public key — that is algorithm confusion.
- If the JWKS endpoint itself is unreachable, it falls back to the Auth API rather than signing
  everyone out. A token that fails *signature or expiry* is never retried remotely.
- The admin role is read from the database, never from a token claim: `user_metadata` is
  client-writable, so trusting it for authorisation would let any user promote themselves.

**Backend auth dependencies** (`backend/core/auth.py`):
- `require_admin` — admin-only endpoints (all existing `/api/*` routers)
- `require_user_auth` — any authenticated user (Stripe checkout, account)
- `optional_auth` — returns user if logged in, `None` if not (public transcript viewing)

### Row-level security

`profiles` had no RLS, so anyone holding the public anon key could read every user's name and
phone number. It is now enabled with a single **SELECT-only** policy scoped to the owner's row.
There is deliberately no UPDATE policy: `role` lives on this table, and a client-side UPDATE
policy would let any user promote themselves to admin. Profile edits go through
`PUT /api/profile`, which runs on the service key and strips `role` and `stripe_customer_id`.

### Route Structure

**Public pages** (no auth required):
| Route | Page File | Purpose |
|-------|-----------|---------|
| `/` | `pages/index.vue` | Personas grid |
| `/personas/[slug]` | `pages/personas/[slug].vue` | Persona detail with transcript list |
| `/transcripts/[id]` | `pages/transcripts/[id].vue` | Transcript viewer with search |
| `/markets` | `pages/markets/index.vue` | Public markets listing — one section per venue, grouped by persona inside each |
| `/markets/[slug]` | `pages/markets/[slug].vue` | Persona markets detail (premium analysis). Event cards on `/markets` link here as `#event-{event_id}` |
| `/pricing` | `pages/pricing.vue` | Subscription pricing |
| `/blog` | `pages/blog/index.vue` | Blog listing (lead post + hanging-margin rows) |
| `/blog/[...slug]` | `pages/blog/[...slug].vue` | Blog post |
| `/login` | `pages/login.vue` | Sign in, forgot password. `layout: false` |
| `/signup` | `pages/signup.vue` | Sign up + "check your email" step. `layout: false` |

**Auth-required pages**:
| Route | Page File | Purpose |
|-------|-----------|---------|
| `/account` | `pages/account.vue` | Profile, password change, subscription management |
| `/admin/*` | `pages/admin/**` | All admin features |

`/account` is three `lg:grid-cols-[180px_minmax(0,1fr)]` sections — Profile, Password, Subscription
— each with its `type-label` heading hanging in the left margin above a `UCard`. Metadata reads as
`<UiStatRow>` rows; a free plan shows a `<UiUpsellBanner variant="panel">` instead of a price. An
active subscription badge is `color="primary"` (ink), and only `past_due`/`unpaid` get
`color="error"` — green and red are reserved for market outcome and trend.

`/pricing` is a sticky plan rail (Premium `UCard` + a Free box) beside the argument column: a
side-by-side locked/unlocked demonstration built from `<UiTermChip>`, `<UiStatRow>` and
`<UiTallyRail>` and **labelled as an illustration, not live data**; a Free-vs-Premium `<table>`; and
a `UAccordion` FAQ. The FAQ array is the single source for both the accordion and the `FAQPage`
schema, so the two cannot drift. The CTA is wrapped in `<ClientOnly>` with a signed-out fallback,
because pre-hydration the subscription state is unknown.

### Layouts

- `layouts/default.vue` — Public layout, no sidebar. `UHeader` (a `<UiBrandMark>` + wordmark title,
  a `UNavigationMenu variant="pill"` with Transcripts / Markets / Pricing / Blog, and a right
  cluster of `UColorModeButton` + the auth buttons), `UMain > UContainer`, then a `UFooter` that
  does **not** repeat the nav — it states what the site counts, credits Kalshi & Polymarket, and
  links the RSS feed. It also owns the site-wide `Organization` + `WebSite` schema
- `layouts/admin.vue` — Admin layout with sidebar (FileTree, nav)
- **No layout**: `/login` and `/signup` set `definePageMeta({ layout: false })` and render their own
  two-column shell — a night `bg-ink-950` panel stating the product's thesis beside the form
- `app/error.vue` — the branded 404/500. Nuxt renders it outside the page tree, so it mounts
  `<NuxtLayout name="default">` itself; without that a 404 lands on an unbranded stock page

The auth cluster in the header is wrapped in `<ClientOnly>` (it depends on the hydrated session)
with a fallback that reserves the exact `h-8 w-[184px]` strip it will occupy, so the header's right
edge does not jump on load. The colour-mode toggle is visible at every breakpoint, so neither the
mobile drawer nor the footer carries its own.

### UI & Design System

Every public page is built from the shared components in `app/components/ui/` (auto-imported with
the `Ui` prefix) and the colour/type tokens in `app/assets/css/main.css`.
**Read `docs/design-system.md` before editing any public page markup.** In short:

| Concern | Use |
|---------|-----|
| Loading | `<UiLoadingBlock variant="cards\|rows\|text\|spinner\|inline">` |
| Failed request | `UAlert color="error"` with a retry action — **never** an empty state |
| Nothing to show | `<UiEmptyState>` with a next move |
| Bad id/slug | `<UiNotFoundState>` |
| Paywall prompt | `<UiUpsellBanner variant="bar\|panel">` — the caller keeps its own gate |
| A tracked term + its price | `<UiTermChip>` |
| A mention count | `<UiTallyRail>` (real data only) |
| A label/value metadata line | `<UiStatRow>` |
| A segmented filter | `<UiFilterToggle>` (requires a `label`) |
| A persona image/initial | `<UiPersonaAvatar>` |

The admin area has **not** been migrated and still uses raw Tailwind palette classes. Do not copy
admin markup into a public page.

### Middleware
- `middleware/auth.global.ts` — Routes to three zones:
  1. Public routes → pass through
  2. Auth-required routes → check session
  3. Admin routes → check session + `profiles.role === 'admin'`

## Paywall System

### Database Columns
```sql
transcripts.is_public  -- visible on public site (default: false)
transcripts.is_premium -- requires subscription (default: false)
```

### States
| `is_public` | `is_premium` | Behavior |
|-------------|-------------|----------|
| `false` | `false` | Admin-only (not visible publicly) |
| `true` | `false` | Free — anyone can read |
| `true` | `true` | Premium — preview for free users, full for subscribers |

### Admin Controls
- **Transcript detail page** (`/admin/transcripts/[id]`) — "Public" and "Premium" toggles in the header
- **Transcript listing page** (`/admin/transcripts`) — inline "Public" and "Premium" toggles per row for quick bulk management
- **Persona detail page** (`/admin/personas/[id]`) — "Transcripts" section lists all matching transcripts with individual "Public" and "Premium" toggles
- All toggles use `PATCH /api/transcripts/{id}` with `is_public` and `is_premium` fields
- Disabling "Public" automatically disables "Premium"; "Premium" toggle is disabled when "Public" is off

## Public API

Prefix: `/api/public`

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /sitemap-urls` | None | Sitemap-formatted persona URLs (loc, lastmod, changefreq, priority) |
| `GET /personas` | None | List all personas |
| `GET /personas/{slug}` | None | Get persona by slug |
| `GET /personas/{slug}/transcripts` | None | List public transcripts for persona |
| `GET /personas/{slug}/keyword-search` | `optional_auth` | Search keywords across persona's transcripts |
| `GET /markets` | None | List market events grouped by persona |
| `GET /markets/{slug}` | `optional_auth` | Persona markets detail with subscription-gated analysis |
| `GET /transcripts/{id}` | `optional_auth` | View public transcript |
| `GET /transcripts/{id}/neighbors` | None | Previous/next transcript for the same persona (`?persona={slug}`) |

### Query Parameters

**`GET /personas/{slug}/transcripts`**:
- `folder_id` — filter by folder
- `search` — search in transcript text
- `sort_by` — `date` or `name`
- `sort_order` — `asc` or `desc`
- `page`, `page_size` — pagination

**`GET /personas/{slug}/keyword-search`**:
- `q` (required) — keyword to search (1-100 chars)
- Returns matches with context snippets, total counts, and `is_limited` flag
- **Premium-only feature.** For non-subscribers the search input is **not rendered at all** — a
  `<UiUpsellBanner variant="panel">` stands in for the feature itself, with a "Sign in" secondary
  link offered only when there is no session. Subscribers get full results (up to 100 matches)
- Results are grouped one card per transcript, and each card links to the transcript viewer with
  `?search=` for highlighting. See `docs/personas.md` for the full markup

**`GET /transcripts/{id}`**:
- `search` — highlight search term, returns per-speaker frequency breakdown in `speakerFrequencies`

### Access Control
- Public transcripts: `is_public = true`
- Premium transcripts return truncated preview (75-word limit, breaking at last newline) with `is_locked = true` if user not subscribed
- Subscription checked via `subscriptions` table
- Locked transcripts hide the sticky search bar, the pagination and the prev/next navigation on the
  frontend to prevent interaction with restricted content. The preview text fades into the page
  ground under a `bg-linear-to-t from-default to-transparent` overlay, and a
  `<UiUpsellBanner variant="panel">` sits below it

## Public Transcript Reader (`app/pages/transcripts/[id].vue`)

The reading surface. `noindex, nofollow` — it exists for readers, not for search engines.

- **Header**: `UBreadcrumb` (Transcripts → persona → transcript), a `type-title measure-wide` `<h1>`,
  then a meta row of date (`type-figure`), a persona link with an `xs` `<UiPersonaAvatar>`, a
  "Watch on YouTube" external link, and a `Premium` `UBadge color="primary"` — premium is ink, never
  amber
- **Sticky search bar** at `top-(--ui-header-height)`: a mono `UInput`, a match-count `UBadge
  color="secondary"`, a clear button, and a `USwitch` for timestamps. Hidden entirely when
  `is_locked`
- **Segments**: parsed client-side into speaker/timestamp/content. At `sm+` each segment is a
  `grid-cols-[8.5rem_minmax(0,1fr)]` — the speaker (`type-label`) and timestamp hang right-aligned
  in the margin, with the body in a `measure` column at `leading-[1.75]`. Rows are separated by
  `divide-dotted`
- **One parser, two dialects**: plain text arrives when no search is active; when the API
  highlights a term it returns HTML with the speaker name HTML-escaped, so the speaker pattern must
  additionally allow `&#;` and permit a longer name. `PLAIN_SPEAKER_PATTERN` and
  `HTML_SPEAKER_PATTERN` differ only in that. If the pattern matches nothing, the page falls back to
  rendering the raw text in a `measure-wide whitespace-pre-wrap` block
- **Pagination**: 50 segments per page, with a windowed page-number nav. A shorter result set
  clamps `currentPage` so a search can never strand the reader on a page that no longer exists
- **Locked state**: the preview fades under a `bg-linear-to-t from-default to-transparent` overlay
  into a `<UiUpsellBanner variant="panel">`. Search, pagination and prev/next are all suppressed
- **Speaker rail**: when the API returns `speakerFrequencies`, a sticky `<aside>` holds a `UCard`
  headed "Who said it" with a `<UiStatRow tone="mark">` total and one `<UiTallyRail>` per speaker
- **Prev/next briefing** from `GET /api/public/transcripts/{id}/neighbors?persona={slug}`; a failure
  there is non-critical and swallowed
- The page carries a third copy of the `<mark>` guard in a scoped `:deep(mark)` rule, because this
  is the one surface that renders API HTML with `v-html`

## Stripe Integration

### Profile Endpoints (`/api/profile`)

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /` | `require_user_auth` | Get the current user's profile, creating the row if missing |
| `PUT /` | `require_user_auth` | Update `first_name`, `last_name`, `phone` |

`POST /init` was removed. Profile rows come from the `on_auth_user_created` trigger, with
`profile_service.ensure_profile()` as a fallback. `PUT` strips `role` and `stripe_customer_id`;
neither is user-editable.

### Endpoints (`/api/stripe`)

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /checkout` | `require_user_auth` | Create Checkout session |
| `POST /webhook` | None (Stripe signature) | Handle subscription events |
| `GET /subscription` | `require_user_auth` | Get subscription status |
| `POST /portal` | `require_user_auth` | Create Customer Portal session |

### Database Tables
```sql
subscriptions (user_id, stripe_customer_id, stripe_subscription_id, status, current_period_start/end)
profiles (id, role, stripe_customer_id, first_name, last_name, phone, created_at, updated_at)
```

### Webhook Events
- `checkout.session.completed` — create subscription record
- `customer.subscription.updated` — update status/period
- `customer.subscription.deleted` — mark inactive

### Frontend Composables
- `useAuth()` — facade over @nuxtjs/supabase: `login`, `signup`, `logout`, `resendConfirmation`,
  `sendPasswordReset`, `role`, `getAccessToken`
- `useProfile()` — the `profiles` row and the role; `ensureLoaded()` is safe to await in middleware
- `usePublicApi()` — fetch wrapper that attaches the token if logged in
- `useSubscription()` — subscription state, `startCheckout()`, `openPortal()`. `loading` covers the
  status fetch, `checkoutPending` covers checkout/portal redirects
- `useSupabaseClient()` / `useSupabaseSession()` / `useSupabaseUser()` — auto-imported by the module

## Persona Discovery

Transcripts are associated with personas via **speaker-based matching**:
1. Each persona has aliases (`persona_aliases` table)
2. Aliases are matched against speaker names in the `speakers` table (case-insensitive via `ilike`)
3. Matching speakers are joined through `transcript_speakers` to find transcripts where the persona was an actual speaker
4. Shared helper `_find_transcript_ids_by_aliases()` in `public_service.py` is used by both public and admin endpoints
5. Personas identified by `slug` field on public routes

## SEO

Full detail lives in **`docs/seo.md`** — OG image templates, canonical overrides, schema.org
per page, robots, sitemap and the blog. Only the parts specific to the public site are repeated here.

### SSR Data Fetching

Public pages use `useFetch` (not `onMounted` + `$fetch`) for anything a meta tag depends on, so the
tags are rendered during SSR. Without it Google sees an empty `<title>` and `<meta description>`.

| Page | SSR fetch | Client-side |
|------|-----------|-------------|
| `index.vue` | `/api/public/personas` (the grid is also indexable content) | — |
| `personas/[slug].vue` | `/api/public/personas/{slug}` | transcript list, keyword search |
| `markets/index.vue` | `/api/public/markets` | — |
| `markets/[slug].vue` | `/api/public/personas/{slug}` (for the meta tags) | `/api/public/markets/{slug}` |
| `transcripts/[id].vue` | — (page is `noindex, nofollow`) | everything |

`markets/[slug].vue` tracks the two fetches separately on purpose: without a distinct
`personaMissing` state the page would spin forever whenever the persona 404s while the markets call
succeeds.

### Dynamic Sitemap

The sitemap uses `@nuxtjs/sitemap`'s `sources` config to fetch persona *and* markets URLs from the
backend's `/api/public/sitemap-urls` endpoint (bypassing Nitro's `/api/**` proxy). Static pages are
added via the `urls` config. The `BACKEND_URL` env var controls the backend base URL (defaults to
`http://localhost:8001`).

**Most personas have a NULL `slug`**, and the UI links them as `slug || id`. Anything enumerating
persona URLs must use the same fallback or it silently drops nearly every persona.

### Database SEO Fields

```sql
personas.meta_title       -- Custom SEO title (optional, falls back to name)
personas.meta_description -- Custom SEO description (optional, falls back to description)
personas.slug             -- URL-friendly identifier for persona routes (usually NULL)
personas.image_url        -- Feeds the OgImagePersona template and UiPersonaAvatar
```

## Key Files

### Backend
| File | Purpose |
|------|---------|
| `backend/core/auth.py` | Auth dependencies (require_admin, optional_auth, etc.) |
| `backend/routers/profile.py` | User profile CRUD endpoints |
| `backend/routers/public.py` | Public API endpoints |
| `backend/routers/stripe_router.py` | Stripe integration endpoints |
| `backend/services/public_service.py` | Public data access |
| `backend/services/stripe_service.py` | Stripe API calls |
| `backend/models/public.py` | Public response models |

### Frontend
| File | Purpose |
|------|---------|
| `app/layouts/default.vue` | Public layout (top nav) |
| `app/layouts/admin.vue` | Admin layout (sidebar) |
| `app/middleware/auth.global.ts` | Route protection (public / user / admin zones) |
| `app/plugins/session.client.ts` | Loads profile + subscription once per session |
| `server/routes/auth/confirm.get.ts` | Server-side email confirmation (`verifyOtp`) |
| `app/composables/useAuth.ts` | Auth facade over @nuxtjs/supabase |
| `app/composables/useProfile.ts` | Profile + role state |
| `app/composables/usePublicApi.ts` | Public fetch wrapper |
| `app/composables/useSubscription.ts` | Subscription management |
| `app/error.vue` | Branded 404/500; mounts `<NuxtLayout name="default">` itself |
| `app/assets/css/main.css` | Colour scales, type scale, surface tokens, the global `<mark>` rule |
| `app/app.config.ts` | Nuxt UI colour aliases + the lucide icon map |
| `app/components/ui/*.vue` | The ten shared components — see `docs/design-system.md` |
| `app/pages/index.vue` | Hero (thesis + the transcribe/count/compare sequence) then the speaker grid, with a client-side name/description filter |
| `app/pages/personas/[slug].vue` | Persona detail: premium keyword search + paginated transcript list |
| `app/pages/transcripts/[id].vue` | Public transcript viewer: sticky search bar, hanging speaker/timestamp margin, speaker-frequency rail |
| `app/pages/markets/index.vue` | Public markets listing |
| `app/pages/markets/[slug].vue` | Persona markets detail |
| `app/pages/blog/index.vue`, `app/pages/blog/[...slug].vue` | Blog listing and post — see `docs/seo.md` |
| `app/composables/usePublicMarkets.ts` | **Unused** — neither markets page imports it |
| `app/pages/login.vue` | Sign in, forgot-password |
| `app/pages/signup.vue` | Sign up (email + password only) |
| `app/pages/pricing.vue` | Pricing page |
| `app/pages/account.vue` | Account/subscription management |
| `backend/routers/public.py` (`/sitemap-urls`) | Dynamic sitemap endpoint for persona pages |
| `backend/services/profile_service.py` | Profile reads/writes with self-healing `ensure_profile` |
| `supabase/migrations/20260830_auth_rebuild_profiles.sql` | Trigger, backfill, RLS |

## Environment Variables
```
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...
```
