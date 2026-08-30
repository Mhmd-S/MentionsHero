# Personas

A persona is a unified speaker identity that groups name variations (aliases) together. This enables accurate analysis across transcripts where the same person may be referred to differently (e.g., "John Smith", "J. Smith", "Mr. Smith").

## Core Concepts

- **Persona**: Has a name, optional description, SEO fields (meta_title, meta_description), and list of aliases
- **Aliases**: Unique text strings mapped to a persona. Used for transcript matching
- **SEO**: Each persona can have custom `meta_title` and `meta_description` for search engine optimization. Falls back to persona name/description when not set. Persona pages are indexed (`index, follow`), transcript pages are not (`noindex, nofollow`)
- **Transcript matching**: Finds transcripts containing ANY of the persona's aliases via case-insensitive text search

## Data Flow

```
Create persona with aliases
  → persona + persona_aliases rows in DB
  → View persona's transcripts (alias-matched)
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/personas` | List all personas with aliases |
| `GET` | `/api/personas/{id}` | Get single persona with aliases |
| `POST` | `/api/personas` | Create persona (with optional initial aliases) |
| `PATCH` | `/api/personas/{id}` | Update name/description/SEO fields |
| `DELETE` | `/api/personas/{id}` | Delete persona (aliases cascade) |
| `POST` | `/api/personas/{id}/aliases` | Add aliases (filters duplicates) |
| `DELETE` | `/api/personas/{id}/aliases` | Remove aliases |
| `GET` | `/api/personas/{id}/transcripts` | Get transcripts matching persona's aliases (optional `?folder_id=`) |

## File Map

| Layer | File | Purpose |
|-------|------|---------|
| Page (admin) | `app/pages/admin/personas/index.vue` | Persona listing, create/edit/delete modals |
| Page (admin) | `app/pages/admin/personas/[id].vue` | Persona detail, alias management, per-transcript Public/Premium toggles |
| Page (public) | `app/pages/personas/[slug].vue` | Public speaker page — keyword search + transcript list (see below) |
| Composable | `app/composables/usePersonas.ts` | Admin persona API calls |
| Router | `backend/routers/personas.py` | Persona endpoints |
| Service | `backend/services/persona_service.py` | Persona DB operations, alias management, transcript matching |
| Model | `backend/models/persona.py` | `Persona`, `PersonaCreate`, `PersonaUpdate`, `AddAliasesRequest`, `RemoveAliasesRequest` |

## Public Persona Page (`app/pages/personas/[slug].vue`)

The public speaker page. Routed as `/personas/{slug || id}` — most personas have a NULL `slug`, so
the id fallback is what makes the link work, and the backend resolves either. Persona data is
fetched with `useFetch` during SSR (the meta tags depend on it); the transcript list and the
keyword search run client-side. Follows `docs/design-system.md`.

**Shell**

- `UBreadcrumb` (Transcripts → persona name), then a `UPageHeader` with `root: 'relative border-b
  border-default pb-8'`. The `#headline` slot is an `i-lucide-mic` + "Speaker" label; the `#links`
  slot holds a `<UiPersonaAvatar size="lg">`. The `title` slot carries the name **and nothing else**
  — it renders inside the `<h1>`
- Below the header, a two-column grid at `lg`: the main column plus a sticky `<aside>` of margin
  metadata

**Keyword search section** (premium)

- A bordered `bg-elevated/40` panel headed "Search what {name} said", with a "Subscribers"
  `UBadge color="primary"` for free users
- **Free users**: the whole search is replaced by `<UiUpsellBanner variant="panel">`. There is no
  disabled input — the panel stands in for the feature. A "Sign in" secondary link is offered only
  when there is no session
- **Subscribers**: a `UInput size="lg"`, debounced 500 ms, minimum two characters, hitting
  `GET /api/public/personas/{slug}/keyword-search`
- Results open with a stat row: two `<UiStatRow layout="stack" size="lg">` blocks (Mentions with
  `tone="mark"`, Transcripts) and, when the data supports it, a per-briefing `<UiTallyRail>` in
  series mode
- Matches are **grouped one card per transcript**, not one card per context window. Each card links
  to `/transcripts/{id}?search={query}`, shows the date, a `<UiTallyRail>` + count, and up to three
  snippets as `border-l-2 border-mark-500/50` quotes with the term wrapped in a bare `<mark>`
  (escaped first — `v-html` is used for this field and no other). Overflow reads
  "+N more passages in this transcript"
- Only the first five groups render; a "Show all N transcripts" toggle expands the rest
- **Completeness guard**: the API caps matches at 100. When the cap bites (`is_limited`, or the
  counted mentions do not equal `total_matches`), no tally rail is drawn at all and a caption says
  "Showing the first N of M mentions" — a rail that under-counts is worse than no rail

**Transcript list**

- Heading with the total as a `type-figure`, a debounced (400 ms) filter input, and a two-button
  sort group (Date / Name) with `aria-pressed` and a chevron showing the direction
- The list is a `<ul>` of `rule-dotted` rows: file icon, name, a "Premium" `UBadge color="primary"`
  (premium is ink, never amber), a two-line preview, then date and folder in `type-caption`
- `UPagination` at 20 per page, with a "Showing 1–20 of N" line in mono
- **A failed request is not an empty result.** A fetch error renders a `UAlert` with a "Load again"
  action; the empty state only appears when the request succeeded and returned nothing. The
  filter-empty copy differs for subscribers vs free users, because premium transcripts are not
  searched on a free account

**Margin aside**

A `<dl>` with a `<UiStatRow semantic>` transcript count, then the persona's aliases as mono
`UBadge`s under an "Also known as" `type-label`, with one line explaining that a transcript line is
attributed to this persona when the speaker label matches one of them.

**States**: `UiLoadingBlock variant="text"` while the persona loads → `<UiNotFoundState>` if it does
not resolve.

SEO for this page (canonical override, page-scoped `definePerson`, OG image) is documented in
`docs/seo.md`.

## Key Functions

### persona_service.py

- `get_all_personas()` → Fetches personas, groups aliases by persona_id
- `create_persona(name, description?, meta_title?, meta_description?, aliases?)` → Atomic create with optional aliases and SEO fields
- `add_aliases(persona_id, aliases[])` → Filters duplicates and existing, triggers market reprocessing
- `remove_aliases(persona_id, aliases[])` → Removes aliases, triggers market reprocessing
- `get_transcripts_for_persona(persona_id, folder_id?)` → Searches transcript text for any alias (case-insensitive), optionally scoped to folder tree
- `get_all_aliases()` → Returns `{ alias_name: persona_id }` mapping for bulk lookups

## Database Tables

**personas**
- `id` (uuid PK), `name` (text NOT NULL), `description` (text), `meta_title` (text), `meta_description` (text), `slug` (text UNIQUE), `image_url` (text), `created_at`, `updated_at`

**persona_aliases**
- `id` (uuid PK), `persona_id` (uuid FK → personas CASCADE), `alias` (text UNIQUE), `created_at`
