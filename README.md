# MentionsHero

A searchable archive of what public figures actually said.

MentionsHero transcribes YouTube videos — press briefings, interviews, podcasts — with speaker
diarization, attributes every line to a person, and makes the whole corpus searchable word by
word. The public site is free and anonymous: no accounts, no paywall, no rate limit. Behind an
admin login sits the production toolchain that transcribes new videos and tracks the Kalshi and
Polymarket "mentions" contracts written on the same words.

**The public site is transcripts.** Prediction-market tooling exists, but it is admin-only.

---

## How it works

```
YouTube URL ──▶ yt-dlp ──▶ audio ──▶ Gemini 2.0 Flash ──▶ diarized transcript
                                                               │
                                                               ▼
                                        speakers ◀── parsed ──▶ transcripts
                                            │                       │
                                            └──── matched by ───────┘
                                              persona_aliases
                                                    │
                                                    ▼
                                          /personas/{slug}
```

A transcript reaches a persona page only by speaker attribution. `persona_aliases` holds the
names a person is labelled with in transcripts ("Donald Trump", "President Trump", "Donald J.
Trump"); those are matched case-insensitively against the `speakers` table, which is joined to
transcripts through `transcript_speakers`. **A persona with no aliases can never show a
transcript** — the most common way to end up with a mysteriously empty page.

Two visibility rules govern the public site:

- A transcript appears only if `is_public = true` **and** it has speaker links. No links, no page.
- A persona is listed only if it has at least one public transcript. Empty personas are dropped
  from the homepage and the sitemap; their pages still resolve by direct URL.

## Stack

| Layer | Choice |
|---|---|
| Frontend | Nuxt 4 (Vue 3, TypeScript), Nuxt UI, Tailwind 4 |
| Backend | FastAPI (Python 3.13) |
| Database | Supabase (PostgreSQL) |
| Auth | `@nuxtjs/supabase` cookie sessions + local JWKS verification in FastAPI |
| Transcription | Google Gemini 2.0 Flash (speaker diarization) |
| Audio | yt-dlp + ffmpeg |
| Content | `@nuxt/content` v3 for the blog |
| SEO | `@nuxtjs/seo` — sitemap, robots, schema.org, OG images |

Both processes ship in **one container**: FastAPI on `:8001`, Nuxt on `:$PORT`, with Nuxt
proxying `/api/**` to the backend via `routeRules`.

## Quick start

**Node 22+ is required.** `@supabase/supabase-js` needs a native `WebSocket`, which Node 20 does
not have — on Node 20 every SSR page returns a bare 500 with nothing in the logs.

```bash
# 1. Dependencies
pnpm install
python3 -m venv backend/venv && ./backend/venv/bin/pip install -r backend/requirements.txt

# 2. Configure
cp .env.example .env      # then fill in the values below

# 3. Run both processes
./start_dev.sh            # Nuxt :3000, FastAPI :8001
```

Or separately:

```bash
pnpm dev                                                        # :3000
./backend/venv/bin/python -m uvicorn backend.main:app --reload --port 8001
```

If you switch Node versions, run `pnpm rebuild better-sqlite3` — otherwise `@nuxt/content`
fails at startup with a `NODE_MODULE_VERSION` mismatch.

### Environment

```bash
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_SERVICE_KEY=...     # service role — server-side only, never shipped to the browser
SUPABASE_KEY=...             # anon/publishable key — this is the one the browser gets
GEMINI_API_KEY=...           # required to transcribe
CORS_ORIGINS=https://example.com,https://www.example.com
```

`SUPABASE_URL` and `SUPABASE_SERVICE_KEY` are required — the app will not boot without them.
`SUPABASE_KEY` is a *different* value from `SUPABASE_SERVICE_KEY` and the two do not substitute
for each other.

### Database

Schema lives in [`supabase/setup_new_project.sql`](supabase/setup_new_project.sql), with
incremental changes in [`supabase/migrations/`](supabase/migrations/).
[`utils/db_refrence.sql`](utils/db_refrence.sql) is a read-only reference dump of the current
shape.

## Layout

```
app/                    Nuxt frontend
  pages/                public routes at root, admin under pages/admin/
  composables/          every API call goes through one of these, never $fetch from a page
  components/ui/        the nine shared primitives — see docs/design-system.md
  middleware/           auth.global.ts guards exactly one prefix: /admin
backend/
  routers/              FastAPI routes, one per domain
  services/             business logic
  utils/nlp.py          term frequency, n-grams, context search, segment parsing
  scripts/              one-off imports and backfills
content/blog/           markdown blog posts
docs/                   feature documentation — read before changing a feature
supabase/migrations/    SQL migrations
```

## Access model

There are no visitor accounts. `/login` exists solely to unlock `/admin`, and admin users are
created in the Supabase dashboard — there is no self-signup, email confirmation or password
reset in the app.

- `/api/public/**` — unauthenticated, always. Nothing widens for a signed-in visitor.
- `/api/profile` — any authenticated user. Its only job is telling the admin UI your role.
- everything else — `require_admin`.

The admin role is read from the `profiles` table on every request, **never** from a token claim:
`user_metadata` is client-writable, so trusting it would let any user promote themselves. Tokens
are verified locally against the project JWKS (ES256), cached in-process.

## Deployment

Single container via [`Dockerfile`](Dockerfile) → [`start.sh`](start.sh), currently on Railway.
`start.sh` supervises both processes: if either exits, the container exits non-zero so the
platform restarts it. Never let Nuxt outlive FastAPI — it serves every page normally while all
`/api/**` requests 502, which passes any health check that only hits `/`.

## Gotchas worth knowing before you change something

- **PostgREST caps unbounded selects at 1000 rows and reports no error.** Whole-table reads in
  `public_service.py` go through `_select_all()`, which pages. An unpaged read of a 1073-row
  table silently returned 1000 and made a dozen healthy transcripts look broken.
- **Most personas have a NULL `slug`** and are linked as `slug || id`. Anything enumerating
  persona URLs must use the same fallback or it drops nearly every persona.
- **FastAPI route ordering**: static routes (`/series/search`) must be declared before
  parameterized ones (`/series/{id}`).
- **Icons are lucide only**, and the icon endpoint is `/_nuxt_icon` — *not* under `/api`, which
  is proxied to FastAPI.
- **Never write a raw Tailwind palette class.** See [`docs/design-system.md`](docs/design-system.md).

## Documentation

| Topic | File |
|---|---|
| Public site, auth model, visibility rules | [`docs/public-site.md`](docs/public-site.md) |
| Transcription pipeline | [`docs/transcripts.md`](docs/transcripts.md) |
| Term search & analysis | [`docs/term-search.md`](docs/term-search.md) |
| Personas & aliases | [`docs/personas.md`](docs/personas.md) |
| Markets (admin-only) | [`docs/markets.md`](docs/markets.md) |
| Auto-transcription | [`docs/auto-transcription.md`](docs/auto-transcription.md) |
| SEO, blog, sitemap | [`docs/seo.md`](docs/seo.md) |
| Design system | [`docs/design-system.md`](docs/design-system.md) |
| Sidebar & folders | [`docs/sidebar.md`](docs/sidebar.md) |

[`CLAUDE.md`](CLAUDE.md) is the conventions file for AI coding agents working in this repo; it
doubles as a dense summary of the architecture.

## A note on the transcripts

Transcripts are machine-generated by an LLM from public video and are **not** certified records.
Speaker attribution and wording can both be wrong. Check the linked source video before quoting
anything that matters.
