# Transcript Viewer

## Purpose
Browse, search, filter, and read transcripts. Provides a list view with search highlighting and a detail view with speaker frequency analysis.

## User Flow
1. User navigates to a transcript list (via folder tree in sidebar or direct link)
2. List shows transcript cards with name, date, speakers
3. User can search — results highlight matching text with debounce
4. User can filter by speakers (multi-select)
5. Clicking a transcript opens the detail view
6. Detail view shows full transcript text, speaker frequency sidebar chart
7. User can copy transcript to clipboard or delete it

## Data Flow

```
transcripts/index.vue
  → authFetch('/api/transcripts', { params: { folder_id, search, speakers } })
    → transcripts.py router → transcript_service.get_transcripts()
      → Supabase query with optional folder/search/speaker filters
    → Returns TranscriptWithHighlights[] (includes match_count, speaker_frequencies)

transcripts/[id].vue
  → authFetch('/api/transcripts/{id}')
    → transcript_service.get_transcript_by_id()
      → Supabase select + speaker frequency calculation
    → Returns full transcript with available_speakers list
```

## Key Files

### Frontend
| File | Purpose |
|------|---------|
| `app/pages/transcripts/index.vue` | Transcript list with search, speaker filter, folder context |
| `app/pages/transcripts/[id].vue` | Full transcript detail view with speaker chart |
| `app/composables/useAuthFetch.ts` | Authenticated API calls |

### Backend
| File | Purpose |
|------|---------|
| `backend/routers/transcripts.py` | CRUD endpoints, search with highlighting, speaker filtering |
| `backend/services/transcript_service.py` | Transcript queries, speaker extraction, folder-scoped filtering |
| `backend/models/transcript.py` | Transcript, TranscriptWithHighlights, SpeakerFrequency models |

## Database Tables
- **transcripts** — full text content, folder_id, upload_date
- **speakers** — deduplicated speaker names
- **transcript_speakers** — junction with segment_count

## Key Implementation Details

**Search:** Case-insensitive text search across transcript content. Results include `match_count` and `has_highlights` for UI rendering.

**Speaker filtering:** Multi-select speaker names filter transcripts to those containing selected speakers via `transcript_speakers` join.

**Speaker frequencies:** Calculated per transcript from `transcript_speakers.segment_count`.
