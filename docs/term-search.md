# Term Search

Analyzes term frequency and provides contextual search across transcripts. Supports filtering by speaker, folder, and persona.

## Feature Overview

The Term Search page (`/term-search`) has two main modes:

1. **Frequency Tab**: How often does a term appear? Returns total mentions, percentage of briefings containing it, trend (rising/falling/stable), and mentions-by-date breakdown.
2. **Context Tab**: Where does a term appear? Returns matching snippets with surrounding context (configurable window, default 200 chars).

Additional analysis endpoints:
- **All Terms**: Top N terms above a frequency threshold (cached 1hr)
- **N-grams**: Top 2-3 word phrases above a frequency threshold (cached 1hr)
- **Speakers**: Aggregated speaker list with segment counts and briefing counts

## Data Flow

```
User enters search term on /term-search
  → TermSearch.vue component
  → useAnalysis composable calls API
  → backend/routers/analysis.py
  → backend/utils/nlp.py performs calculation
  → Results returned (optionally cached in analysis_cache)
```

### Filtering

- **Folder**: Restricts to transcripts in folder tree (recursive via `get_transcripts_in_folder_tree()`)
- **Speakers**: Comma-separated list — only searches content spoken by those speakers
- **Persona**: Auto-fills speaker list from persona aliases, restricts to persona's transcripts
- **Case sensitivity**: Toggle for frequency analysis (context search is always case-insensitive)

## Search Algorithms

### Term Frequency (`calculate_term_frequency()`)
1. Filter transcripts by folder/speakers
2. Clean text: remove speaker labels and timestamps via `clean_text()`
3. Whole-word regex matching: `\bterm\b`
4. Count total mentions per transcript, track by date
5. Calculate trend: compare first half vs second half of chronological mentions
6. Return: `{ term, total_mentions, briefings_with_term, percentage, trend, mentions_by_date }`

### All Terms (`calculate_all_term_frequencies()`)
1. Tokenize all transcript text with NLTK `word_tokenize`
2. Remove stop words, filter: length > 2, alphabetic only
3. Count frequency and briefing coverage
4. Return top N terms above `min_frequency`
5. Cached for 1 hour

### N-grams (`extract_ngrams()`)
1. NLTK `ngrams()` to extract 2-3 word phrases
2. Count frequency across transcripts
3. Filter by `min_frequency`, return top N
4. Cached for 1 hour

### Context Search (`search_term_in_context()`)
1. Regex with word boundary: `\bterm\b`
2. Extract `context_chars` before and after each match
3. Return: `{ query, total_matches, transcripts_with_matches, matches[] }`
4. Not cached (real-time)

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/analysis/term/{term}` | Frequency for specific term (supports `?speakers=`, `?folder_id=`, `?persona_id=`, `?case_sensitive=`) |
| `POST` | `/api/analysis/term-frequency` | Frequency analysis (POST body) |
| `GET` | `/api/analysis/terms` | All terms above threshold (cached) |
| `POST` | `/api/analysis/all-terms` | All terms (POST body, cached) |
| `GET` | `/api/analysis/ngrams` | N-gram phrases (cached) |
| `POST` | `/api/analysis/ngrams` | N-grams (POST body, cached) |
| `POST` | `/api/analysis/search` | Context search with matches |
| `GET` | `/api/analysis/speakers` | Speaker list with stats |
| `GET` | `/api/analysis/speakers/search` | Search speakers by name |
| `POST` | `/api/analysis/speakers/migrate` | One-time speaker migration |

## File Map

| Layer | File | Purpose |
|-------|------|---------|
| Page | `app/pages/term-search.vue` | Term Search page |
| Component | `app/components/TermSearch.vue` | Core search UI (Frequency + Context tabs) |
| Component | `app/components/SpeakerSelector.vue` | Multi-select speaker picker |
| Composable | `app/composables/useAnalysis.ts` | API calls: `getTermFrequency()`, `searchTerm()`, `getAllTerms()`, `getNgrams()` |
| Router | `backend/routers/analysis.py` | All `/api/analysis/*` endpoints |
| Service | `backend/services/transcript_service.py` | `get_all_transcripts()`, `get_transcripts_in_folder_tree()`, `get_transcripts_by_ids()` |
| Service | `backend/services/speaker_service.py` | `get_all_speakers()`, `search_speakers()` |
| Model | `backend/models/analysis.py` | Request/response models: `TermFrequencyResponse`, `SearchResponse`, `AllTermsResponse`, `NgramsResponse` |
| Util | `backend/utils/nlp.py` | `calculate_term_frequency()`, `calculate_all_term_frequencies()`, `extract_ngrams()`, `search_term_in_context()`, `clean_text()` |
| Util | `backend/utils/transcript_filter.py` | `highlight_transcript()`, `calculate_speaker_frequencies()` |

## Database Tables

**analysis_cache**
- `cache_key` (text UNIQUE), `result` (jsonb), `expires_at` (timestamptz)
- Used for all-terms and n-gram queries (1 hour TTL)
- Keyed by: `"{type}:{folder_id}:{speakers}:{params}"`

Reads from: `transcripts`, `folders`, `speakers`, `transcript_speakers`
