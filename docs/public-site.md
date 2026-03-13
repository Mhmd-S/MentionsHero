# Public Website & Stripe Paywall

## Overview

The platform has two distinct areas:
- **Public site** (`/`, `/personas/*`, `/transcripts/*`, `/pricing`, `/account`) — browseable by anyone, with optional paywall
- **Admin area** (`/admin/*`) — existing features behind admin auth

## Architecture

### Auth Model

Uses Supabase auth with role-based access via `profiles` table:
- `profiles.role = 'admin'` — full admin access
- `profiles.role = 'client'` — public user (free or subscribed)

**Email verification** is required. Supabase "Confirm email" must be enabled in the dashboard (Authentication → Settings → Email). After signup, users receive a verification email and must confirm before logging in.

**Profile fields**: `first_name`, `last_name`, `phone` are collected at signup and stored in `profiles` table via `POST /api/profile/init` (backend service key bypasses RLS). Also sent as `user_metadata` in Supabase auth for redundancy. Users can view and edit these fields on the `/account` page via `GET /api/profile` and `PUT /api/profile`.

**Backend auth dependencies** (`backend/core/auth.py`):
- `require_admin` — admin-only endpoints (all existing `/api/*` routers)
- `require_user_auth` — any authenticated user (Stripe checkout, account)
- `optional_auth` — returns user if logged in, `None` if not (public transcript viewing)

### Route Structure

**Public pages** (no auth required):
| Route | Page File | Purpose |
|-------|-----------|---------|
| `/` | `pages/index.vue` | Personas grid |
| `/personas/[slug]` | `pages/personas/[slug].vue` | Persona detail with transcript list |
| `/transcripts/[id]` | `pages/transcripts/[id].vue` | Transcript viewer with search |
| `/pricing` | `pages/pricing.vue` | Subscription pricing |
| `/login` | `pages/login.vue` | Sign in |
| `/signup` | `pages/signup.vue` | Sign up |

**Auth-required pages**:
| Route | Page File | Purpose |
|-------|-----------|---------|
| `/account` | `pages/account.vue` | Subscription management |
| `/admin/*` | `pages/admin/**` | All admin features |

### Layouts
- `layouts/default.vue` — Public layout with top navbar, no sidebar
- `layouts/admin.vue` — Admin layout with sidebar (FileTree, nav)

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
| `GET /transcripts/{id}` | `optional_auth` | View public transcript |

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
- Free users: 3 transcript matches, 1 snippet each; subscribed users: full results (up to 100 matches)
- Links to transcript viewer with `?search=` param for highlighting

**`GET /transcripts/{id}`**:
- `search` — highlight search term, returns per-speaker frequency breakdown in `speakerFrequencies`

### Access Control
- Public transcripts: `is_public = true`
- Premium transcripts return truncated preview (75-word limit, breaking at last newline) with `is_locked = true` if user not subscribed
- Subscription checked via `subscriptions` table
- Locked transcripts hide the search bar and pagination controls on the frontend to prevent interaction with restricted content

## Stripe Integration

### Profile Endpoints (`/api/profile`)

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /init` | None (validates user_id exists) | Create profile during signup |
| `GET /` | `require_user_auth` | Get current user's profile |
| `PUT /` | `require_user_auth` | Update current user's profile |

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
- `usePublicApi()` — fetch wrapper that attaches token if logged in
- `useSubscription()` — subscription state, `startCheckout()`, `openPortal()`

## Persona Discovery

Transcripts are associated with personas via **speaker-based matching**:
1. Each persona has aliases (`persona_aliases` table)
2. Aliases are matched against speaker names in the `speakers` table (case-insensitive via `ilike`)
3. Matching speakers are joined through `transcript_speakers` to find transcripts where the persona was an actual speaker
4. Shared helper `_find_transcript_ids_by_aliases()` in `public_service.py` is used by both public and admin endpoints
5. Personas identified by `slug` field on public routes

## SEO

### Module & Configuration

Uses `@nuxtjs/seo` (unified module bundling sitemap, robots, schema.org, site utils). Configured in `nuxt.config.ts`:

- **Site config**: `site.url = 'https://mentionshero.com'`, `site.name = 'MentionsHero'`
- **Title template**: `%s | MentionsHero` (via `app.head.titleTemplate`)
- **Robots**: Disallows `/admin/` and `/account`; auto-references sitemap
- **Sitemap**: Auto-generated at `/sitemap.xml`, excludes admin/auth/account routes

### Per-Page SEO

| Page | Meta | Structured Data | Indexing |
|------|------|-----------------|----------|
| `/` (landing) | Static title/description targeting "press briefing transcripts" | `WebSite` + `WebPage` schema | Indexed |
| `/personas/[slug]` | Dynamic from `persona.meta_title`/`meta_description` with OG/Twitter tags | `Person` + `BreadcrumbList` schema | Indexed |
| `/transcripts/[id]` | Dynamic title from transcript name, OG tags for social sharing | None | `noindex, nofollow` |
| `/pricing` | Static title/description | None | Indexed |

### SSR Data Fetching

Public pages use `useFetch` (not `onMounted` + `$fetch`) so meta tags are rendered during SSR. This is critical — without SSR, Google sees empty `<title>` and `<meta description>`.

- `index.vue` — `useFetch('/api/public/personas')` for persona grid
- `personas/[slug].vue` — `useFetch('/api/public/personas/${slug}')` for persona data; transcript listing stays client-side (not needed for SEO)

### Dynamic Sitemap

The sitemap uses `@nuxtjs/sitemap`'s `sources` config to fetch persona URLs from the backend's `/api/public/sitemap-urls` endpoint (bypasses Nitro's `/api/**` proxy). Static pages like `/pricing` are added via the `urls` config. The `BACKEND_URL` env var controls the backend base URL (defaults to `http://localhost:8001`).

### Open Graph & Social

All public pages include OG tags (`ogTitle`, `ogDescription`, `ogImage`, `twitterCard`). Persona pages use `persona.image_url` as OG image with `/og-default.png` fallback.

### Database SEO Fields

```sql
personas.meta_title       -- Custom SEO title (optional, falls back to name)
personas.meta_description -- Custom SEO description (optional, falls back to description)
personas.slug             -- URL-friendly identifier for persona routes
personas.image_url        -- Used as OG image on persona pages
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
| `app/middleware/auth.global.ts` | Route protection |
| `app/composables/usePublicApi.ts` | Public fetch wrapper |
| `app/composables/useSubscription.ts` | Subscription management |
| `app/pages/index.vue` | Public personas grid |
| `app/pages/personas/[slug].vue` | Persona detail + transcript list |
| `app/pages/transcripts/[id].vue` | Public transcript viewer |
| `app/pages/signup.vue` | User signup |
| `app/pages/pricing.vue` | Pricing page |
| `app/pages/account.vue` | Account/subscription management |
| `backend/routers/public.py` (`/sitemap-urls`) | Dynamic sitemap endpoint for persona pages |

## Environment Variables
```
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...
```
