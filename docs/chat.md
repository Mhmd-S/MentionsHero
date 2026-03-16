# AI Chat Agent

Interactive chat interface that replaces the old Term Search page. Powered by a Gemini agent that can query transcripts, analyze terms, and browse prediction markets.

## Architecture

- **Backend agent loop**: FastAPI hosts the Gemini agent loop (`agent_service.py`). Frontend sends chat messages, backend runs tool-calling loop, streams responses via SSE.
- **Gemini function calling**: Tools are declared as `types.FunctionDeclaration` objects and map directly to existing service functions (no HTTP round-trips).
- **SSE streaming**: POST `/api/chat/conversations/{id}/messages` returns a `StreamingResponse`. Frontend reads via `fetch()` + `ReadableStream` (not EventSource, since it's a POST).
- **Persistent history**: Conversations and messages saved to Supabase `chat_conversations` / `chat_messages` tables.

## Database Tables

| Table | Purpose |
|-------|---------|
| `chat_conversations` | Conversation metadata (id, title, created_at, updated_at) |
| `chat_messages` | Messages (id, conversation_id, role, content, tool_calls JSONB, created_at) |

Messages have `role` = `user` or `assistant`. Assistant messages may include `tool_calls` JSONB array storing `{id, name, args, result}` for each tool invocation.

## Backend Files

| File | Purpose |
|------|---------|
| `backend/models/chat.py` | Pydantic request models |
| `backend/services/chat_service.py` | CRUD for conversations and messages |
| `backend/services/agent_tools.py` | Gemini tool declarations + executor functions |
| `backend/services/agent_service.py` | Agent loop with SSE streaming |
| `backend/routers/chat.py` | API endpoints |

## API Endpoints

All admin-authed via `require_admin` dependency.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/chat/conversations` | List conversations |
| `POST` | `/api/chat/conversations` | Create conversation |
| `GET` | `/api/chat/conversations/{id}` | Get conversation + messages |
| `DELETE` | `/api/chat/conversations/{id}` | Delete conversation |
| `PATCH` | `/api/chat/conversations/{id}` | Update title |
| `POST` | `/api/chat/conversations/{id}/messages` | Send message → SSE stream |

## Available Tools

All read-only. Defined in `agent_tools.py`. 16 tools total.

### Lookup & Navigation

| Tool | Description | Calls |
|------|-------------|-------|
| `search_folders` | Find folders by name (case-insensitive) | `folder_service.get_all_folders()` + filter |
| `search_personas` | Find persona by name/alias | `persona_service.search_personas()` |
| `list_folders` | List all folders | `folder_service.get_all_folders()` |
| `list_personas` | All personas + aliases | `persona_service.get_all_personas()` |
| `get_persona` | Single persona detail | `persona_service.get_persona_by_id()` |

### Transcript Access

| Tool | Description | Calls |
|------|-------------|-------|
| `list_transcripts` | List transcripts (metadata only, sorted by date) | `transcript_service.get_all_transcripts()` |
| `get_transcript_content` | Read transcript text (with section-based truncation) | `transcript_service.get_transcript_by_id()` |
| `list_speakers` | Speakers with counts | `speaker_service.get_all_speakers()` |

### Term Analysis

| Tool | Description | Calls |
|------|-------------|-------|
| `search_term` | Term frequency + trend | `nlp.calculate_term_frequency()` |
| `search_term_in_context` | Context snippets | `nlp.search_term_in_context()` |
| `get_top_terms` | Most frequent terms | `nlp.calculate_all_term_frequencies()` |
| `get_ngrams` | Common 2/3-word phrases | `nlp.extract_ngrams()` |

### Markets

| Tool | Description | Calls |
|------|-------------|-------|
| `browse_kalshi_events` | Open Kalshi events | `kalshi_service.browse_events()` |
| `get_kalshi_event` | Event detail + markets | `kalshi_service.get_event_detail_by_ticker()` |
| `search_polymarket` | Search Polymarket | `polymarket_service.search_events()` |
| `get_polymarket_event` | Event detail + markets | `polymarket_service.get_event_detail()` |

### Multi-Step Reasoning

The system prompt guides the agent to chain tools for complex questions. Example flow for *"How will the latest PMQ transcript affect the Polymarket PMQ market?"*:

1. `search_folders(query="PMQ")` → folder_id
2. `list_transcripts(folder_id=X, limit=1, sort="latest")` → transcript ID
3. `search_personas(query="Keir Starmer")` → persona_id
4. `get_transcript_content(transcript_id=Y)` → reads the transcript
5. `search_polymarket(query="PMQ")` → finds relevant market
6. `get_polymarket_event(event_id=Z, persona_id=P)` → prices + mention analysis

The agent then synthesizes transcript content with market data for an analytical answer.

## SSE Event Format

```
event: tool_call_start
data: {"id": "abc", "name": "search_term", "args": {"term": "tariff"}}

event: tool_call_result
data: {"id": "abc", "name": "search_term", "result": {"total_mentions": 47, ...}}

event: text_delta
data: {"text": "partial response text..."}

event: done
data: {"message_id": "uuid"}

event: error
data: {"message": "error description"}
```

## Frontend Files

| File | Purpose |
|------|---------|
| `app/composables/useChat.ts` | Chat state + API + SSE streaming |
| `app/pages/admin/transcript-analysis.vue` | Chat page using Nuxt UI chat components |

### UI Components Used (Nuxt UI v4)

- **`UChatMessages`** — Message container with built-in auto-scroll, scroll-to-bottom button, typing indicator
- **`UChatMessage`** — Single message with avatar, variant (soft/naked), side (left/right), action buttons
- **`UChatPrompt`** — Auto-resizing textarea with Enter-to-send, outline variant
- **`UChatPromptSubmit`** — Status-aware submit/stop/reload button

Custom `app/components/chat/` components (ChatMessage, ChatToolCall, ChatInput) are no longer used — replaced by Nuxt UI built-ins with `#content` slot for markdown rendering and tool invocation display.

### Composable State

| State | Type | Purpose |
|-------|------|---------|
| `conversations` | `Conversation[]` | Sidebar list |
| `currentConversation` | `Conversation \| null` | Active conversation |
| `messages` | `ChatMessage[]` | Messages with parts-based format |
| `status` | `ChatStatus` | `ready \| streaming \| submitted \| error` |
| `loading` | `boolean` | Conversation loading (messages area) |
| `sidebarLoading` | `boolean` | Initial conversation list fetch |
| `deletingId` | `string \| null` | Conversation being deleted (spinner) |
| `error` | `string \| null` | Error message |

## Agent Loop Flow

1. User sends message via POST
2. Backend loads conversation history (last 20 messages)
3. Builds Gemini `contents` from history + new user message
4. Saves user message to DB
5. Loops: call Gemini → if function calls, execute tools and yield SSE events → continue
6. Final text response chunked into `text_delta` SSE events
7. Saves complete assistant message (text + tool_calls) to DB
8. Yields `done` SSE

## Key Details

- **Model**: `gemini-2.5-flash`
- **Max history**: Last 20 messages sent to Gemini
- **Max tool loops**: 10 iterations before forcing a text response
- **Tool result truncation**: Large results capped at ~3000 chars to manage token limits
- **Auto-title**: First user message becomes conversation title (truncated to 50 chars)
