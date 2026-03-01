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

**Profile fields**: `first_name`, `last_name`, `phone` are collected at signup and stored in `profiles` table. Also sent as `user_metadata` in Supabase auth for redundancy.

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
| `GET /personas` | None | List all personas |
| `GET /personas/{slug}` | None | Get persona by slug |
| `GET /personas/{slug}/transcripts` | None | List public transcripts for persona |
| `GET /transcripts/{id}` | `optional_auth` | View public transcript |

### Query Parameters

**`GET /personas/{slug}/transcripts`**:
- `folder_id` — filter by folder
- `search` — search in transcript text
- `sort_by` — `date` or `name`
- `sort_order` — `asc` or `desc`
- `page`, `page_size` — pagination

**`GET /transcripts/{id}`**:
- `search` — highlight search term, returns per-speaker frequency breakdown in `speakerFrequencies`

### Access Control
- Public transcripts: `is_public = true`
- Premium transcripts return truncated preview (20 lines) with `is_locked = true` if user not subscribed
- Subscription checked via `subscriptions` table

## Stripe Integration

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

Transcripts are associated with personas via **alias-based matching**:
1. Each persona has aliases (`persona_aliases` table)
2. Public transcript listing searches transcript text for any alias match (case-insensitive)
3. Uses existing `get_transcripts_for_persona()` logic in `persona_service.py`
4. Personas identified by `slug` field on public routes

## Key Files

### Backend
| File | Purpose |
|------|---------|
| `backend/core/auth.py` | Auth dependencies (require_admin, optional_auth, etc.) |
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

## Environment Variables
```
STRIPE_SECRET_KEY=sk_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...
```
