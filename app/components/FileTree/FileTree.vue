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

    <div
      class="space-y-0.5 min-h-[40px] rounded transition-colors"
      :class="{ 'ring-2 ring-primary ring-offset-1 bg-primary-50 dark:bg-primary-900/30': isRootDragOver }"
      @dragover.prevent="onRootDragOver"
      @dragleave="onRootDragLeave"
      @drop.prevent="onRootDrop"
    >
      <!-- Root-level folders -->
      <FileTreeFolder
        v-for="folder in rootFolders"
        :key="folder.id"
        :folder="folder"
        :folders="folders"
        :transcripts="transcripts"
        class="group"
        @request-rename="handleRename($event)"
        @delete="deleteFolder"
        @move="handleMove"
      />

      <!-- Root-level transcripts -->
      <FileTreeItem
        v-for="transcript in rootTranscripts"
        :key="transcript.id"
        :transcript="transcript"
        @request-rename="handleRename($event)"
      />

      <div
        v-if="loading"
        class="px-2 py-4 text-sm text-gray-400 text-center"
      >
        Loading...
      </div>

      <div
        v-else-if="folders.length === 0 && transcripts.length === 0"
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
  renameTranscript,
  moveFolder,
  moveTranscript
} = useFileTree()

const isRootDragOver = ref(false)

const rootFolders = computed(() => folders.value.filter(f => !f.parent_id))
const rootTranscripts = computed(() => transcripts.value.filter(t => !t.folder_id))

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
