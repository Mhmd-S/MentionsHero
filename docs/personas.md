# Personas

A persona is a unified speaker identity that groups name variations (aliases) together. This enables accurate analysis across transcripts where the same person may be referred to differently (e.g., "John Smith", "J. Smith", "Mr. Smith").

## Core Concepts

- **Persona**: Has a name, optional description, optional slug (for publishing), optional image_url, and list of aliases
- **Aliases**: Unique text strings mapped to a persona. Used for transcript matching and display-time speaker normalization
- **Transcript matching**: Finds transcripts containing ANY of the persona's aliases via case-insensitive text search
- **Series linking**: Personas can be linked to Kalshi series for market analysis (see `docs/markets.md`)
- **Publishing**: A persona with a non-null `slug` is "published" and appears in the public persona directory at `/`. Personas without a slug are admin-only/draft
- **Speaker normalization**: Raw transcript speaker labels are resolved to canonical persona names at display time using bidirectional substring matching against aliases (see `docs/transcripts.md` "Public Viewer" section)

## Data Flow

```
Create persona with aliases (+ optional slug to publish)
  → persona + persona_aliases rows in DB
  → Link to Kalshi series (optional, with folder scoping)
  → View persona's transcripts (alias-matched)
  → Market analysis uses persona's aliases as speaker filter
  → If slug set: persona appears in public directory at /
  → Public users browse /p/{slug} → view transcript list → /view/{id}
```

### Alias Changes Trigger Reprocessing
When aliases are added/removed, `kalshi_service.reprocess_persona_markets()` runs as a background task. This recalculates term frequencies in all linked market analyses for the affected persona.

## API Endpoints

### Admin Endpoints (authenticated)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/personas` | List all personas with aliases |
| `GET` | `/api/personas/{id}` | Get single persona with aliases |
| `POST` | `/api/personas` | Create persona (with optional aliases, slug, image_url) |
| `PATCH` | `/api/personas/{id}` | Update name/description/slug/image_url |
| `DELETE` | `/api/personas/{id}` | Delete persona (aliases cascade) |
| `POST` | `/api/personas/{id}/aliases` | Add aliases (filters duplicates) |
| `DELETE` | `/api/personas/{id}/aliases` | Remove aliases |
| `GET` | `/api/personas/{id}/transcripts` | Get transcripts matching persona's aliases (optional `?folder_id=`) |

### Public Endpoints (no auth)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/public/personas` | List published personas (slug IS NOT NULL) with transcript counts |
| `GET` | `/api/public/personas/{slug}` | Persona detail + transcript list (metadata only) |

## File Map

### Admin

| Layer | File | Purpose |
|-------|------|---------|
| Page | `app/pages/admin/personas/index.vue` | Persona listing, create/edit/delete modals, slug/image management |
| Page | `app/pages/admin/personas/[id].vue` | Persona detail, linked series, alias management |
| Composable | `app/composables/usePersonas.ts` | All persona API calls (CRUD, aliases, slug/image_url) |
| Router | `backend/routers/personas.py` | Admin persona endpoints |
| Service | `backend/services/persona_service.py` | Persona DB operations, alias management, transcript matching |
| Model | `backend/models/persona.py` | `Persona`, `PersonaCreate`, `PersonaUpdate`, `AddAliasesRequest`, `RemoveAliasesRequest` |

### Public

| Layer | File | Purpose |
|-------|------|---------|
| Page | `app/pages/index.vue` | Landing page with persona directory grid |
| Page | `app/pages/p/[slug].vue` | Persona detail with transcript list |
| Layout | `app/layouts/saas.vue` | Client-facing layout with top nav |
| Router | `backend/routers/public.py` | Public persona + transcript endpoints |
| Service | `backend/services/persona_service.py` | `get_public_personas()`, `get_persona_by_slug()`, `get_public_transcripts_for_persona()` |
| Model | `backend/models/persona.py` | `PublicPersona`, `PublicPersonaDetail`, `PublicPersonaTranscript` |

## Key Functions

### persona_service.py

- `get_all_personas()` → Fetches personas, groups aliases by persona_id
- `create_persona(name, description?, aliases?, slug?, image_url?)` → Atomic create with optional aliases and publishing fields
- `update_persona(persona_id, name?, description?, slug?, image_url?)` → Update persona fields
- `add_aliases(persona_id, aliases[])` → Filters duplicates and existing, triggers market reprocessing
- `remove_aliases(persona_id, aliases[])` → Removes aliases, triggers market reprocessing
- `get_transcripts_for_persona(persona_id, folder_id?)` → Searches transcript text for any alias (case-insensitive), optionally scoped to folder tree
- `get_all_aliases()` → Returns `{ alias_name: persona_id }` mapping for bulk lookups
- `build_alias_to_persona_map()` → Returns `{alias_lower: persona_name}` for display-time speaker normalization
- `resolve_transcript_speakers(segments, alias_map)` → Bidirectional substring matching to resolve raw speaker labels to canonical names
- `get_public_personas()` → Fetches published personas (slug IS NOT NULL) with transcript counts via speaker junction tables
- `get_persona_by_slug(slug)` → Single persona lookup by slug
- `get_public_transcripts_for_persona(persona_id)` → Transcript metadata (no full text) via `transcript_speakers` + `speakers` junction tables

## Database Tables

**personas**
- `id` (uuid PK), `name` (text NOT NULL), `description` (text), `slug` (text UNIQUE, nullable — acts as publish flag), `image_url` (text), `created_at`, `updated_at`

**persona_aliases**
- `id` (uuid PK), `persona_id` (uuid FK → personas CASCADE), `alias` (text UNIQUE), `created_at`

**persona_kalshi_series** (junction — see `docs/markets.md`)
- `persona_id` (uuid FK → personas CASCADE), `kalshi_series_id` (uuid FK), `folder_id` (uuid FK → folders SET NULL)
- UNIQUE(persona_id, kalshi_series_id)
