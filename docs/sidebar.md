# Transcripts Sidebar & Directory

The sidebar provides navigation and a hierarchical file tree for organizing transcripts into folders.

## Layout Structure

**File**: `app/layouts/default.vue`

```
┌──────────────────┬──────────────────────────────────────────┐
│  Sidebar (264px) │  Main Content (flex-1, ml-64)            │
│  fixed, h-screen │                                          │
│                  │  <slot /> (page content)                  │
│  Logo + Logout   │                                          │
│  ─────────────── │                                          │
│  Nav Links:      │                                          │
│    New Transcript│                                          │
│    Term Search   │                                          │
│    Personas      │                                          │
│    Events        │                                          │
│  ─────────────── │                                          │
│  <FileTree />    │                                          │
│  ─────────────── │                                          │
│  <JobsSidebar /> │                                          │
└──────────────────┴──────────────────────────────────────────┘
```

- Sidebar: `fixed top-0 left-0 h-screen overflow-y-auto`, width `w-64`
- Main content: `flex-1 p-8 ml-64`
- Navigation uses `<NuxtLink>` with `active-class` for highlighting current route

## FileTree Component

A recursive component that renders folders and transcripts in a tree structure.

### Component Hierarchy

```
FileTree.vue (root)
  ├─ Search input
  ├─ "New Folder" button
  ├─ FileTreeFolder.vue (recursive, for each root folder)
  │   ├─ Folder header (expand/collapse, rename, delete)
  │   ├─ FileTreeFolder.vue (child folders, recursive)
  │   └─ FileTreeItem.vue (transcripts in this folder)
  └─ FileTreeItem.vue (root-level transcripts, no folder)
```

### Key Behaviors

- **Expand/Collapse**: Folders toggle open/closed on click
- **Search**: Filters folders by name OR if any descendant matches; filters transcripts by name. Auto-expands matching folders
- **Active State**: `FileTreeItem` highlights when `route.params.id === transcript.id` (uses `bg-primary-100`)
- **Drag-and-Drop**: Transcripts and folders can be dragged between folders. Drop target highlighted via `dropTargetId` state
- **Context Actions**: Right-click or button menu for rename, move, delete operations

### Root-Level Filtering

```
rootFolders = folders where parent_id === null
rootTranscripts = transcripts where folder_id === null
```

## Folder Operations

- **Create**: `POST /api/folders` with optional `parent_id`
- **Rename**: `PATCH /api/folders/{id}` with new `name`
- **Move**: `PATCH /api/folders/{id}` with new `parent_id`
- **Delete**: `DELETE /api/folders/{id}` — moves children to parent folder

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/folders` | List all folders |
| `POST` | `/api/folders` | Create folder (optional parent_id) |
| `PATCH` | `/api/folders/{id}` | Update folder (rename/move) |
| `DELETE` | `/api/folders/{id}` | Delete folder |
| `GET` | `/api/folders/{id}/transcripts` | Get transcripts in folder |

Transcript move/rename uses the transcript endpoints:
| `PATCH` | `/api/transcripts/{id}` | Update name or folder_id |
| `DELETE` | `/api/transcripts/{id}` | Delete transcript |

## File Map

| Layer | File | Purpose |
|-------|------|---------|
| Layout | `app/layouts/default.vue` | Fixed sidebar + main content area |
| Component | `app/components/FileTree/FileTree.vue` | Root file tree with search and folder creation |
| Component | `app/components/FileTree/FileTreeFolder.vue` | Recursive folder rendering |
| Component | `app/components/FileTree/FileTreeItem.vue` | Individual transcript item with active state |
| Composable | `app/composables/useFileTree.ts` | State management: `folders`, `transcripts`, CRUD operations, drag-and-drop state |
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
