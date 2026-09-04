# Public Website

## Overview

The platform has two distinct areas:

- **Public site** (`/`, `/personas/*`, `/transcripts/*`, `/blog/*`) — free, anonymous, complete.
  No account, no subscription, no paywall. Every `is_public` transcript is served in full to
  whoever asks.
- **Admin area** (`/admin/*`) — the whole production toolchain, behind an admin session.

There are no visitor accounts. The only session that exists on this site is an admin's, and
`/login` exists solely to create it.

## Architecture

### Auth Model

Auth is the official **`@nuxtjs/supabase`** module. It owns the browser and server clients,
cookie-based sessions and SSR hydration; the app adds only what the module cannot know about.

Role-based access lives in the `profiles` table:
- `profiles.role = 'admin'` — full admin access
- `profiles.role = 'client'` — a signed-in non-admin. Sees exactly what an anonymous visitor sees

**Admin accounts are created in the Supabase dashboard.** There is no self-signup, no email
confirmation flow and no password reset in the app — the pages and the `/auth/confirm` Nitro route
that served them were removed with the paywall. To reset an admin password, use the Supabase
dashboard.

**The database creates profile rows, not the browser.** `on_auth_user_created` fires on every
`auth.users` insert and writes the matching `public.profiles` row
(`supabase/migrations/20260830_auth_rebuild_profiles.sql`).
`backend/services/profile_service.ensure_profile()` is the second, independent guarantee: any read
repairs a missing row instead of 500ing. Never use `.single()` on `profiles`.

**Session state**
| Piece | Source | Notes |
|-------|--------|-------|
| session | `useSupabaseSession()` | `Omit<Session, 'user'>`, hydrated from cookies during SSR |
| user | `useSupabaseUser()` | **JWT claims, not a `User`** — the id is `user.sub`, not `user.id` |
| role / profile | `useProfile()` | fetched from `GET /api/profile`; the role is not a JWT claim |

There is no session plugin. `useProfile().ensureLoaded()` is called by the `/admin` guard and
nowhere else, so an anonymous visitor — which is nearly all traffic — never makes the request.

`useAuth()` is a thin facade over the above: `session`, `user`, `isLoggedIn`, `loading`, `error`,
`role`, `isAdmin`, `login`, `logout`, `getAccessToken`, `ensureProfileLoaded`. That is the whole
surface.

### Route guard

`supabase.redirect` is **false** in `nuxt.config.ts`. The module ships a `global-auth` middleware
that redirects everything not in an allow-list to `/login`; on a site that is entirely public that
is the wrong shape. `app/middleware/auth.global.ts` is the only thing that redirects, and it is a
one-entry deny-list: `/admin`. Anything else falls through to a real 404 rather than a login wall.
Because the session is hydrated from cookies during SSR, the redirect happens on the server.

### Backend token verification

`backend/core/auth.py` verifies tokens **locally** against the project's JWKS
(`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`, ES256). Never reintroduce a per-request
`supabase.auth.get_user(token)`.

- The key set is cached in-process (`PyJWKClient`, 10-minute lifespan) and refetched automatically
  on key rotation or an unknown `kid`.
- `SUPABASE_JWT_SECRET` handles projects still on the legacy symmetric HS256 secret. `HS256` is
  never accepted against a JWKS public key — that is algorithm confusion.
- If the JWKS endpoint itself is unreachable, it falls back to the Auth API rather than signing
  everyone out. A token that fails *signature or expiry* is never retried remotely.
- The admin role is read from the database, never from a token claim: `user_metadata` is
  client-writable, so trusting it for authorisation would let any user promote themselves.

**Backend auth dependencies**:
- `require_admin` — every `/api/*` router except `/api/public` and `/api/profile`
- `require_user_auth` — any authenticated user. Its only consumer is `GET /api/profile`
- `require_auth` — the shared primitive behind both; also accepts `?token=` for SSE

There is no `optional_auth` any more. It existed to widen a response for subscribers; nothing
widens now.

### Row-level security

`profiles` has RLS enabled with a single **SELECT-only** policy scoped to the owner's row. There is
deliberately no UPDATE policy: `role` lives on this table, and a client-side UPDATE policy would let
any user promote themselves to admin.

### Route Structure

**Public pages** (no auth, no account, nothing gated):
| Route | Page File | Purpose |
|-------|-----------|---------|
| `/` | `pages/index.vue` | Speaker list with a client-side filter |
| `/personas/[slug]` | `pages/personas/[slug].vue` | Persona detail: keyword search + paginated transcript list |
| `/transcripts/[id]` | `pages/transcripts/[id].vue` | Transcript viewer with search |
| `/blog` | `pages/blog/index.vue` | Blog listing (lead post + hanging-margin rows) |
| `/blog/[...slug]` | `pages/blog/[...slug].vue` | Blog post |
| `/login` | `pages/login.vue` | Admin sign in. `layout: false`, `noindex` |

**Admin-only pages**:
| Route | Page File | Purpose |
|-------|-----------|---------|
| `/admin/*` | `pages/admin/**` | All admin features, including the markets tooling |

### Layouts

- `layouts/default.vue` — Public layout, no sidebar. `UHeader` (a `<UiBrandMark>` + wordmark title,
  a `UNavigationMenu variant="pill"` with **Transcripts / Blog**, and a right cluster of
  `UColorModeButton` plus — only when a session exists — **Sign out**), `UMain > UContainer`,
  then a `UFooter` that does **not** repeat the nav. It also owns the site-wide
  `Organization` + `WebSite` schema. There is deliberately **no Admin link** in the public
  header: `/admin` is reached by typing it
- `layouts/admin.vue` — Admin layout with sidebar (FileTree, nav)
- **No layout**: `/login` sets `definePageMeta({ layout: false })` and renders its own shell
- `app/error.vue` — the branded 404/500. Nuxt renders it outside the page tree, so it mounts
  `<NuxtLayout name="default">` itself; without that a 404 lands on an unbranded stock page

The header's session cluster is wrapped in `<ClientOnly>` because it depends on the hydrated
session. It has **no fallback strip**: a signed-out visitor sees nothing there, so there is nothing
to reserve space for.

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
| A tracked term + its price | `<UiTermChip>` (admin markets pages only) |
| A mention count | `<UiTallyRail>` (real data only) |
| A label/value metadata line | `<UiStatRow>` |
| A segmented filter | `<UiFilterToggle>` (requires a `label`) |
| A persona image/initial | `<UiPersonaAvatar>` |

`UiUpsellBanner` is gone. There is no paywall surface left to render.

The admin area has **not** been migrated and still uses raw Tailwind palette classes. Do not copy
admin markup into a public page.

### Middleware
- `middleware/auth.global.ts` — two zones:
  1. Everything → pass through
  2. `/admin/**` → session + `profiles.role === 'admin'`, else `/login?redirect=…`

## Visibility

### Database Columns
```sql
transcripts.is_public   -- visible on the public site (default: false)
transcripts.is_premium  -- LEGACY. The public API ignores it entirely
```

`is_public` is the only flag that matters. `is_premium` still exists as a column and the admin UI
still toggles it (the admin area was left untouched), but nothing reads it on the public side —
setting it has no effect on what a visitor sees.

| `is_public` | Behavior |
|-------------|----------|
| `false` | Not on the public site at all |
| `true` | Fully readable by anyone, in full, with search |

### Admin Controls
- Toggles on `/admin/transcripts`, `/admin/transcripts/[id]` and `/admin/personas/[id]`
- All use `PATCH /api/transcripts/{id}` with `is_public` / `is_premium` fields

## Public API

Prefix: `/api/public`. **Every endpoint is unauthenticated.** No route on this router takes a user.

| Endpoint | Purpose |
|----------|---------|
| `GET /sitemap-urls` | Sitemap-formatted persona URLs (loc, lastmod, changefreq, priority) |
| `GET /personas` | List all personas |
| `GET /personas/{slug}` | Get persona by slug (falls back to id) |
| `GET /personas/{slug}/transcripts` | List public transcripts for persona |
| `GET /personas/{slug}/keyword-search` | Search keywords across persona's transcripts |
| `GET /transcripts/{id}` | View a public transcript, in full |
| `GET /transcripts/{id}/neighbors` | Previous/next transcript for the same persona (`?persona={slug}`) |

### Query Parameters

**`GET /personas/{slug}/transcripts`**:
- `folder_id` — filter by folder
- `search` — search in transcript text
- `sort_by` — `date` or `name`
- `sort_order` — `asc` or `desc`
- `page`, `page_size` — pagination

**`GET /personas/{slug}/keyword-search`**:
- `q` (required) — keyword to search (1-100 chars)
- Returns `{ query, total_matches, transcripts_with_matches, matches[] }`. There is no
  `is_limited` flag — every match is returned to everyone, up to the API's 100-match cap
- Results are grouped one card per transcript, and each card links to the transcript viewer with
  `?search=` for highlighting. See `docs/personas.md` for the full markup

**`GET /transcripts/{id}`**:
- `search` — highlight search term, returns per-speaker frequency breakdown in `speakerFrequencies`

### Access Control
- Public transcripts: `is_public = true`. That is the entire access model
- Nothing is truncated, faded, locked or counted against a quota

## Public Transcript Reader (`app/pages/transcripts/[id].vue`)

The reading surface. Currently `noindex, nofollow` — a holdover from when it was paywalled. Now
that every transcript is free and complete, this is worth revisiting if the archive should rank.

- **Header**: `UBreadcrumb` (Transcripts → persona → transcript), a `type-title measure-wide` `<h1>`,
  then a meta row of date (`type-figure`), a persona link with an `xs` `<UiPersonaAvatar>` and a
  "Watch on YouTube" external link
- **Sticky search bar** at `top-(--ui-header-height)`: a mono `UInput`, a match-count `UBadge
  color="secondary"`, a clear button, and a `USwitch` for timestamps
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
- **Speaker rail**: when the API returns `speakerFrequencies`, a sticky `<aside>` holds a `UCard`
  headed "Who said it" with a `<UiStatRow tone="mark">` total and one `<UiTallyRail>` per speaker
- **Prev/next briefing** from `GET /api/public/transcripts/{id}/neighbors?persona={slug}`; a failure
  there is non-critical and swallowed
- The page carries a third copy of the `<mark>` guard in a scoped `:deep(mark)` rule, because this
  is the one surface that renders API HTML with `v-html`

## Profile Endpoint (`/api/profile`)

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `GET /api/profile` | `require_user_auth` | The signed-in user's profile row, self-healing |

`GET` returns `{ first_name, last_name, phone, email, role }` and creates the row via
`profile_service.ensure_profile()` if it is missing. Its only consumer is the admin UI, which reads
`role` from it. There is no `PUT` — profile editing lived on `/account`, which no longer exists.

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
| `index.vue` | `/api/public/personas` (the list is also indexable content) | — |
| `personas/[slug].vue` | `/api/public/personas/{slug}` | transcript list, keyword search |
| `transcripts/[id].vue` | — (page is `noindex, nofollow`) | everything |

### Dynamic Sitemap

The sitemap uses `@nuxtjs/sitemap`'s `sources` config to fetch persona URLs from the backend's
`/api/public/sitemap-urls` endpoint (bypassing Nitro's `/api/**` proxy). Static pages (`/`,
`/blog`) are added via the `urls` config. The `BACKEND_URL` env var controls the backend base URL
(defaults to `http://localhost:8001`).

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
| `backend/core/auth.py` | Auth dependencies (`require_admin`, `require_user_auth`, `require_auth`) |
| `backend/routers/profile.py` | `GET /api/profile` — the admin role lookup |
| `backend/routers/public.py` | Public API endpoints (all anonymous) |
| `backend/services/public_service.py` | Public data access |
| `backend/services/profile_service.py` | Profile reads with self-healing `ensure_profile` |
| `backend/models/public.py` | Public response models (currently unused by the router) |

### Frontend
| File | Purpose |
|------|---------|
| `app/layouts/default.vue` | Public layout (top nav, sign-out button when signed in) |
| `app/layouts/admin.vue` | Admin layout (sidebar) |
| `app/middleware/auth.global.ts` | Route protection — `/admin` only |
| `app/composables/useAuth.ts` | Auth facade over @nuxtjs/supabase (login/logout/role) |
| `app/composables/useProfile.ts` | Profile + role state |
| `app/composables/usePublicApi.ts` | Public fetch wrapper (a plain `$fetch` seam) |
| `app/error.vue` | Branded 404/500; mounts `<NuxtLayout name="default">` itself |
| `app/assets/css/main.css` | Colour scales, type scale, surface tokens, the global `<mark>` rule |
| `app/app.config.ts` | Nuxt UI colour aliases + the lucide icon map |
| `app/components/ui/*.vue` | The shared components — see `docs/design-system.md` |
| `app/pages/index.vue` | Thesis line then the speaker list, with a client-side name/description filter |
| `app/pages/personas/[slug].vue` | Persona detail: keyword search + paginated transcript list |
| `app/pages/transcripts/[id].vue` | Transcript viewer: sticky search bar, hanging speaker/timestamp margin, speaker-frequency rail |
| `app/pages/blog/index.vue`, `app/pages/blog/[...slug].vue` | Blog listing and post — see `docs/seo.md` |
| `app/pages/login.vue` | Admin sign in |
| `supabase/migrations/20260830_auth_rebuild_profiles.sql` | Trigger, backfill, RLS |

### Removed

Deleted when the paywall came out. Do not resurrect a reference to any of these:

`app/pages/pricing.vue`, `app/pages/signup.vue`, `app/pages/account.vue`,
`app/pages/markets/**`, `app/composables/useSubscription.ts`,
`app/composables/usePublicMarkets.ts`, `app/components/ui/UpsellBanner.vue`,
`app/plugins/session.client.ts`, `server/routes/auth/confirm.get.ts`,
`backend/routers/stripe_router.py`, `backend/services/stripe_service.py`,
and `backend/core/auth.optional_auth`.

## Environment Variables

None specific to the public site. The Stripe keys (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
`STRIPE_PRICE_ID`) and the `stripe` Python dependency were removed along with the paywall.
