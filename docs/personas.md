# Personas

A persona is a unified speaker identity that groups name variations (aliases) together. This enables accurate analysis across transcripts where the same person may be referred to differently (e.g., "John Smith", "J. Smith", "Mr. Smith").

## Core Concepts

- **Persona**: Has a name, optional description, and list of aliases
- **Aliases**: Unique text strings mapped to a persona. Used for transcript matching
- **Transcript matching**: Finds transcripts containing ANY of the persona's aliases via case-insensitive text search
- **Series linking**: Personas can be linked to Polymarket series for market analysis (see `docs/events.md`)

## Data Flow

```
Create persona with aliases
  → persona + persona_aliases rows in DB
  → Link to Polymarket series (optional, with folder scoping)
  → View persona's transcripts (alias-matched)
  → Market analysis uses persona's aliases as speaker filter
```

### Alias Changes Trigger Reprocessing
When aliases are added/removed, `polymarket_service.reprocess_persona_markets()` runs as a background task. This recalculates term frequencies in all linked market analyses for the affected persona.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/personas` | List all personas with aliases |
| `GET` | `/api/personas/{id}` | Get single persona with aliases |
| `POST` | `/api/personas` | Create persona (with optional initial aliases) |
| `PATCH` | `/api/personas/{id}` | Update name/description |
| `DELETE` | `/api/personas/{id}` | Delete persona (aliases cascade) |
| `POST` | `/api/personas/{id}/aliases` | Add aliases (filters duplicates) |
| `DELETE` | `/api/personas/{id}/aliases` | Remove aliases |
| `GET` | `/api/personas/{id}/transcripts` | Get transcripts matching persona's aliases (optional `?folder_id=`) |

## File Map

| Layer | File | Purpose |
|-------|------|---------|
| Page | `app/pages/personas/index.vue` | Persona listing, create/edit/delete modals |
| Page | `app/pages/personas/[id].vue` | Persona detail, linked series, alias management |
| Composable | `app/composables/usePersonas.ts` | All persona API calls |
| Router | `backend/routers/personas.py` | Persona endpoints |
| Service | `backend/services/persona_service.py` | Persona DB operations, alias management, transcript matching |
| Model | `backend/models/persona.py` | `Persona`, `PersonaCreate`, `PersonaUpdate`, `AddAliasesRequest`, `RemoveAliasesRequest` |

## Key Functions

### persona_service.py

- `get_all_personas()` → Fetches personas, groups aliases by persona_id
- `create_persona(name, description?, aliases?)` → Atomic create with optional aliases
- `add_aliases(persona_id, aliases[])` → Filters duplicates and existing, triggers market reprocessing
- `remove_aliases(persona_id, aliases[])` → Removes aliases, triggers market reprocessing
- `get_transcripts_for_persona(persona_id, folder_id?)` → Searches transcript text for any alias (case-insensitive), optionally scoped to folder tree
- `get_all_aliases()` → Returns `{ alias_name: persona_id }` mapping for bulk lookups

## Database Tables

**personas**
- `id` (uuid PK), `name` (text NOT NULL), `description` (text), `created_at`, `updated_at`

**persona_aliases**
- `id` (uuid PK), `persona_id` (uuid FK → personas CASCADE), `alias` (text UNIQUE), `created_at`

**persona_polymarket_series** (junction — see `docs/events.md`)
- `persona_id` (uuid FK → personas CASCADE), `polymarket_series_id` (uuid FK), `folder_id` (uuid FK → folders SET NULL)
- UNIQUE(persona_id, polymarket_series_id)

**persona_polymarket_events** (legacy junction — backward compat)
- `persona_id` (uuid FK → personas CASCADE), `polymarket_event_id` (uuid FK)
- UNIQUE(persona_id, polymarket_event_id)
