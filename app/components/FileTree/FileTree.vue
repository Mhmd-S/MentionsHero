<template>
  <div class="file-tree">
    <div class="flex items-center justify-between mb-2">
      <span class="text-xs font-semibold uppercase text-gray-500">Files</span>
      <button
        class="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
        title="New Folder"
        @click="() => createFolder()"
      >
        <UIcon name="i-heroicons-folder-plus" class="size-4" />
      </button>
    </div>

    <div class="relative mb-2">
      <UIcon
        name="i-heroicons-magnifying-glass"
        class="absolute left-2 top-1/2 -translate-y-1/2 size-4 text-gray-400"
      />
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Search files..."
        class="w-full pl-8 pr-8 py-1.5 text-sm rounded-md border border-gray-200 dark:border-gray-700 bg-transparent focus:outline-none focus:ring-2 focus:ring-primary-500"
      />
      <button
        v-if="searchQuery"
        class="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
        @click="searchQuery = ''"
      >
        <UIcon name="i-heroicons-x-mark" class="size-4" />
      </button>
    </div>

    <div
      class="space-y-0.5 min-h-[40px] rounded transition-colors"
      :class="{ 'ring-2 ring-primary ring-offset-1 bg-primary-50 dark:bg-primary-900/30': isRootDragOver }"
      @dragover.prevent="onRootDragOver"
      @dragleave="onRootDragLeave"
      @drop.prevent="onRootDrop"
    >
      <!-- Root-level folders -->
      <FileTreeFolder
        v-for="folder in filteredRootFolders"
        :key="folder.id"
        :folder="folder"
        :folders="folders"
        :transcripts="transcripts"
        :search-query="searchQuery"
        class="group"
        @request-rename="handleRename($event)"
        @delete="deleteFolder"
        @delete-transcript="deleteTranscript"
        @move="handleMove"
      />

      <!-- Root-level transcripts -->
      <FileTreeItem
        v-for="transcript in filteredRootTranscripts"
        :key="transcript.id"
        :transcript="transcript"
        @request-rename="handleRename($event)"
        @delete="deleteTranscript"
      />

      <div
        v-if="loading"
        class="px-2 py-4 text-sm text-gray-400 text-center"
      >
        Loading...
      </div>

      <div
        v-else-if="searchQuery && filteredRootFolders.length === 0 && filteredRootTranscripts.length === 0"
        class="px-2 py-4 text-sm text-gray-400 text-center"
      >
        No results found
      </div>

      <div
        v-else-if="!searchQuery && folders.length === 0 && transcripts.length === 0"
        class="px-2 py-4 text-sm text-gray-400 text-center"
      >
        No transcripts yet
      </div>
    </div>

  </div>
</template>

<script setup lang="ts">
import { useFileTree } from '~/composables/useFileTree'

const {
  folders,
  transcripts,
  loading,
  fetchAll,
  createFolder,
  renameFolder,
  deleteFolder,
  deleteTranscript,
  renameTranscript,
  moveFolder,
  moveTranscript
} = useFileTree()

const isRootDragOver = ref(false)
const searchQuery = ref('')

const rootFolders = computed(() => folders.value.filter(f => !f.parent_id))
const rootTranscripts = computed(() => transcripts.value.filter(t => !t.folder_id))

function matchesSearch(name: string): boolean {
  if (!searchQuery.value.trim()) return true
  return name.toLowerCase().includes(searchQuery.value.toLowerCase().trim())
}

function folderHasMatchingDescendants(folderId: string): boolean {
  // Check if any direct child transcripts match
  const childTranscripts = transcripts.value.filter(t => t.folder_id === folderId)
  if (childTranscripts.some(t => matchesSearch(t.name || ''))) return true

  // Check child folders recursively
  const childFolders = folders.value.filter(f => f.parent_id === folderId)
  return childFolders.some(f => matchesSearch(f.name) || folderHasMatchingDescendants(f.id))
}

const filteredRootFolders = computed(() => {
  if (!searchQuery.value.trim()) return rootFolders.value
  return rootFolders.value.filter(f =>
    matchesSearch(f.name) || folderHasMatchingDescendants(f.id)
  )
})

const filteredRootTranscripts = computed(() => {
  if (!searchQuery.value.trim()) return rootTranscripts.value
  return rootTranscripts.value.filter(t => matchesSearch(t.name || ''))
})

function handleRename(item: { id: string; type: 'folder' | 'transcript'; currentName: string }) {
  const newName = window.prompt('Enter new name:', item.currentName)
  if (newName && newName.trim()) {
    if (item.type === 'folder') {
      renameFolder(item.id, newName.trim())
    } else {
      renameTranscript(item.id, newName.trim())
    }
  }
}

function handleMove(payload: { type: 'folder' | 'transcript'; id: string; targetFolderId: string | null }) {
  if (payload.type === 'folder') {
    moveFolder(payload.id, payload.targetFolderId)
  } else {
    moveTranscript(payload.id, payload.targetFolderId)
  }
}

function onRootDragOver(e: DragEvent) {
  // Only highlight root if not over a folder
  const target = e.target as HTMLElement
  if (!target.closest('.file-tree-folder')) {
    isRootDragOver.value = true
  }
}

function onRootDragLeave(e: DragEvent) {
  // Check if we're leaving to outside the container
  const relatedTarget = e.relatedTarget as HTMLElement | null
  if (!relatedTarget || !e.currentTarget || !(e.currentTarget as HTMLElement).contains(relatedTarget)) {
    isRootDragOver.value = false
  }
}

function onRootDrop(e: DragEvent) {
  isRootDragOver.value = false

  // Don't handle if dropped on a folder
  const target = e.target as HTMLElement
  if (target.closest('.file-tree-folder')) return

  const data = e.dataTransfer?.getData('application/json')
  if (!data) return

  try {
    const { type, id } = JSON.parse(data)
    handleMove({ type, id, targetFolderId: null })
  } catch (err) {
    console.error('Failed to parse drop data:', err)
  }
}

onMounted(() => {
  fetchAll()
})
</script>
