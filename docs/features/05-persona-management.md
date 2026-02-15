# Persona Management

## Purpose
Create and manage named entities (people/speakers) with aliases that map to speaker names in transcripts. Aliases enable persona-scoped analysis across Polymarket and term search features. Alias changes trigger automatic market analysis reprocessing.

## User Flow
1. User navigates to `/personas`
2. Views list of personas with alias badges
3. Creates a new persona with name, description, and initial aliases
4. Opens persona detail page
5. Adds aliases from existing speakers (searched by folder) or as custom text
6. Removes aliases by clicking X on badge
7. Views linked Polymarket series
8. Links/unlinks series to persona (with optional folder scoping)
9. Navigates to ML training for this persona

## Data Flow

```
personas/index.vue
  → usePersonas().fetchPersonas()
    → GET /api/personas
      → persona_service.get_all_personas()
        → SELECT personas + GROUP persona_aliases by persona_id
      → Returns Persona[] with aliases[]

  → usePersonas().createPersona(name, description, aliases)
    → POST /api/personas { name, description, aliases }
      → persona_service.create_persona()
        → INSERT personas + INSERT persona_aliases for each alias

personas/[id].vue
  → usePersonas().addAliases(personaId, aliases)
    → POST /api/personas/{id}/aliases { aliases }
      → persona_service.add_aliases() — deduplicates, inserts new
      → BackgroundTask: reprocess_persona_markets(persona_id)

  → usePersonas().removeAliases(personaId, aliases)
    → DELETE /api/personas/{id}/aliases { aliases }
      → persona_service.remove_aliases()
      → BackgroundTask: reprocess_persona_markets(persona_id)

  → authFetch GET /api/personas/{id}/transcripts?folder_id=X
    → persona_service.get_transcripts_for_persona()
      → Gets aliases → searches transcript text for matches (case-insensitive)
```

## Key Files

### Frontend
| File | Purpose |
|------|---------|
| `app/pages/personas/index.vue` | Persona list, create modal, alias management |
| `app/pages/personas/[id].vue` | Persona detail — aliases, linked series, ML model link |
| `app/composables/usePersonas.ts` | `fetchPersonas()`, `createPersona()`, `addAliases()`, `removeAliases()`, `getPersonaTranscripts()` |

### Backend
| File | Purpose |
|------|---------|
| `backend/routers/personas.py` | CRUD + alias endpoints, transcript search by persona |
| `backend/services/persona_service.py` | `get_all_personas()`, `create_persona()`, `add_aliases()`, `remove_aliases()`, `get_transcripts_for_persona()`, `get_all_aliases()`, `find_affected_persona_ids()` |
| `backend/models/persona.py` | Persona, PersonaCreate, PersonaUpdate, AddAliasesRequest, RemoveAliasesRequest |

## Database Tables
- **personas** — id, name, description, youtube_channel_url, has_model, last_trained_at
- **persona_aliases** — persona_id (FK), alias (UNIQUE). Alias changes trigger market reprocessing.
- **persona_polymarket_series** — links personas to Polymarket series with optional folder_id scope and auto_trade flag

## Key Implementation Details

**Alias uniqueness:** The `alias` column has a UNIQUE constraint. Duplicate alias attempts return a 409 error (caught via PostgreSQL error code 23505).

**Market reprocessing:** Adding or removing aliases triggers `reprocess_persona_markets()` as a background task. This re-runs `update_market_analysis()` for every event linked to the persona, ensuring term search results reflect current aliases.

**Transcript matching:** `get_transcripts_for_persona()` fetches all persona aliases, then searches transcript text for case-insensitive substring matches. Optionally scoped to a folder tree via `get_folder_ids_in_tree()`.

**Bulk alias from speakers:** The UI allows selecting speakers from a folder and adding them as aliases in bulk, streamlining the process of mapping speaker names across transcripts.

**YouTube Channel URL:** Each persona can have a `youtube_channel_url` field. This is used by the trading bot's channel monitor to auto-detect new video uploads. Set via the persona detail page (`/personas/:id`). The channel monitor polls these URLs every ~45 seconds and auto-starts trading sessions when new videos are detected (requires `auto_trade` enabled on a linked series).

**Auto-Trade per Series:** The `persona_polymarket_series` junction table has an `auto_trade` boolean flag. When enabled, the channel monitor will auto-start trading sessions for new videos from the persona's YouTube channel, using markets from the newest event in that series. Toggle via the persona detail page or the `/api/trading/channel-monitor/auto-trade` endpoint.
