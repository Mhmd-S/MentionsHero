# Term Search

## Purpose
NLP-powered analysis tool for searching terms, n-grams, and phrases across transcripts. Supports folder scoping, persona/speaker filtering, and caches results for performance.

## User Flow
1. User navigates to `/term-search`
2. Selects a folder (scopes which transcripts to analyze)
3. Optionally selects a persona and/or specific speakers
4. Views top terms and n-grams automatically calculated
5. Enters a search term for in-context results
6. Results show term frequency, trend, and highlighted context snippets

## Data Flow

```
term-search.vue
  → useAnalysis composable
    → authFetch('/api/analysis/top-terms', { params: { folder_id, persona_id, speakers } })
      → analysis.py router
        → Checks analysis_cache (24h TTL by cache_key)
        → If miss: nlp.py calculate_top_terms() over filtered transcripts
        → Caches result → returns
    → authFetch('/api/analysis/search', { params: { term, folder_id, persona_id, speakers } })
      → nlp.py search_term_in_context() + calculate_term_frequency()
      → Returns frequency stats + context snippets
```

## Key Files

### Frontend
| File | Purpose |
|------|---------|
| `app/pages/term-search.vue` | Main term search page — folder/persona/speaker selectors, results display |
| `app/components/TermSearch.vue` | Search input and results rendering with context highlighting |
| `app/components/SpeakerSelector.vue` | Multi-select speaker filter dropdown |
| `app/composables/useAnalysis.ts` | API wrapper for analysis endpoints |

### Backend
| File | Purpose |
|------|---------|
| `backend/routers/analysis.py` | Analysis endpoints — top terms, n-grams, search-in-context |
| `backend/utils/nlp.py` | `calculate_term_frequency()`, `calculate_top_terms()`, `search_term_in_context()`, n-gram extraction |
| `backend/services/speaker_service.py` | Speaker lookup and filtering |
| `backend/utils/transcript_filter.py` | Transcript filtering by folder tree, speakers |
| `backend/core/database.py` | `get_cached_analysis()`, `set_cached_analysis()` — analysis cache helpers |

## Database Tables
- **transcripts** — source text for analysis
- **speakers** — speaker name lookup
- **transcript_speakers** — filter transcripts by speaker
- **analysis_cache** — cached results with `cache_key` (UNIQUE), `result` (JSONB), `expires_at` (24h default TTL)

## Key Implementation Details

**Caching:** Results cached in `analysis_cache` table with composite cache key (folder_id + persona_id + speakers + term). Default TTL is 24 hours. Cache checked before computation; results stored after.

**NLP functions** (in `backend/utils/nlp.py`):
- `calculate_top_terms()` — NLTK-based term frequency across corpus
- `calculate_term_frequency()` — per-term frequency with trend (mentions_by_date)
- `search_term_in_context()` — returns 300-char context snippets around matches
- N-gram extraction for common phrases

**Speaker filtering:** When persona selected, filters to transcripts containing that persona's aliases. Additional speaker filter narrows within those transcripts.
