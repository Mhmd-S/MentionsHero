# Admin Sidebar

The admin sidebar provides top-level navigation and shows in-flight job progress. Folder hierarchy is still tracked in the database and used by other features (FolderPicker, personas, auto-transcription), but is no longer rendered as a tree in the sidebar.

## Layout Structure

**File**: `app/layouts/admin.vue`

The sidebar uses Nuxt UI's `<UDashboardSidebar>` (collapsible, resizable). Contents from top to bottom:

1. Header — logo + "MentionsHero" label
2. `<UNavigationMenu>` — New Transcript, Auto Transcribe, Transcripts, Personas
3. `<JobsSidebar />` — live job progress
4. Footer — sign out + color-mode toggle

## Folder Operations (still available via API + FolderPicker)

- **Create**: `POST /api/folders` with optional `parent_id`
- **Rename**: `PATCH /api/folders/{id}` with new `name`
- **Move**: `PATCH /api/folders/{id}` with new `parent_id`
- **Delete**: `DELETE /api/folders/{id}` — recursively deletes all contents

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/folders` | List all folders |
| `POST` | `/api/folders` | Create folder (optional parent_id) |
| `PATCH` | `/api/folders/{id}` | Update folder (rename/move) |
| `DELETE` | `/api/folders/{id}` | Delete folder |
| `GET` | `/api/folders/{id}/transcripts` | Get transcripts in folder |

Transcript move/rename uses the transcript endpoints:

| Method | Path | Description |
|--------|------|-------------|
| `PATCH` | `/api/transcripts/{id}` | Update name or folder_id |
| `DELETE` | `/api/transcripts/{id}` | Delete transcript |

## File Map

| Layer | File | Purpose |
|-------|------|---------|
| Layout | `app/layouts/admin.vue` | Sidebar shell + nav + jobs panel |
| Component | `app/components/JobsSidebar.vue` | Live job progress list |
| Component | `app/components/FolderPicker.vue` | Folder selector reused across pages |
| Composable | `app/composables/useFileTree.ts` | Folder/transcript state used by FolderPicker and pages (no longer renders a tree) |
| Router | `backend/routers/folders.py` | Folder CRUD endpoints |
| Router | `backend/routers/transcripts.py` | Transcript CRUD (used for move/rename) |
| Service | `backend/services/folder_service.py` | Folder DB operations, hierarchy traversal |
| Service | `backend/services/transcript_service.py` | Transcript DB operations |
| Model | `backend/models/folder.py` | Folder Pydantic models |

## Database Tables

**folders**
- `id` (uuid PK), `name` (text NOT NULL), `parent_id` (uuid FK → folders, self-referencing), `created_at`, `updated_at`
- Root folders have `parent_id = NULL`

**transcripts** (folder relationship)
- `folder_id` (uuid FK → folders) — NULL means root-level transcript
