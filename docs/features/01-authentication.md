# Authentication

## Purpose
Protects all app routes and API endpoints behind Supabase email/password authentication. Ensures only authenticated users can access transcripts, run analysis, and train models.

## User Flow
1. User navigates to any page
2. Global middleware checks for active session
3. If no session → redirect to `/login`
4. User enters email + password → Supabase Auth signs in
5. JWT session stored in localStorage with auto-refresh
6. User redirected to home page
7. All subsequent API calls include Bearer token automatically
8. Logout clears session and redirects to `/login`

## Data Flow

```
login.vue
  → useAuth().login(email, password)
    → supabase.auth.signInWithPassword()
      → Supabase GoTrue API
    → session stored in useState + localStorage
  → navigateTo('/')

Every API call:
  useAuthFetch().authFetch(url, opts)
    → getToken() from Supabase session
    → $fetch(url, { headers: { Authorization: 'Bearer {token}' } })
    → On 401: attempt token refresh → retry or logout

Backend:
  require_auth(request)
    → Extract token from Authorization header or ?token query param
    → supabase.auth.get_user(token) validates against Supabase
    → Returns { sub: user_id, email } or raises 401
```

## Key Files

| File | Purpose |
|------|---------|
| `app/pages/login.vue` | Login form with UAuthForm, Zod validation |
| `app/composables/useAuth.ts` | `init()`, `login()`, `logout()`, `getAccessToken()`, reactive user/session state |
| `app/composables/useAuthFetch.ts` | `authFetch<T>()` — wraps $fetch with Bearer token, handles 401 refresh |
| `app/middleware/auth.global.ts` | Route guard — redirects to /login if no session, skips /login page |
| `app/plugins/auth.client.ts` | Calls `useAuth().init()` on app mount |
| `app/utils/supabase.ts` | `useSupabaseClient()` singleton factory (publishable key) |
| `backend/core/auth.py` | `require_auth()` FastAPI dependency — validates JWT, supports header + query param |
| `backend/core/database.py` | `get_supabase()` backend client (service key, lru_cached) |
| `backend/config.py` | `Settings` class — supabase_url, supabase_service_key, cors_origins |
| `backend/main.py` | Global `dependencies=[Depends(require_auth)]` on FastAPI app |

## Database Tables
Authentication is handled entirely by Supabase Auth (managed `auth.users` table). No custom auth tables.

## External Integrations
- **Supabase Auth (GoTrue)** — email/password sign-in, JWT issuance, token validation via `supabase.auth.get_user()`
