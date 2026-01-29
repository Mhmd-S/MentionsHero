<template>
  <div class="file-tree-folder" :data-id="folder.id" data-type="folder">
    <div
      class="flex items-center gap-1 px-2 py-1.5 rounded-md text-sm cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      :class="{ 'ring-2 ring-primary ring-offset-1 bg-primary-50 dark:bg-primary-900/30': isDragOver }"
      draggable="true"
      @dragstart="onDragStart"
      @dragover.prevent="onDragOver"
      @dragleave="onDragLeave"
      @drop.prevent="onDrop"
      @click="toggle"
      tabindex="0"
    >
      <UIcon
        :name="isExpanded ? 'i-heroicons-chevron-down' : 'i-heroicons-chevron-right'"
        class="size-4 text-gray-400 shrink-0"
      />
      <UIcon name="i-heroicons-folder" class="size-4 text-yellow-500 shrink-0" />

      <span class="flex-1 truncate">{{ folder.name }}</span>

      <button
        class="opacity-0 group-hover:opacity-100 hover:text-primary-500 transition-opacity p-0.5"
        title="Rename"
        @click.stop="onRename"
      >
        <UIcon name="i-heroicons-pencil-square" class="size-4" />
      </button>
      <button
        class="opacity-0 group-hover:opacity-100 hover:text-red-500 transition-opacity p-0.5"
        title="Delete"
        @click.stop="$emit('delete', folder.id)"
      >
        <UIcon name="i-heroicons-trash" class="size-4" />
      </button>
    </div>

    <div v-show="isExpanded" class="pl-4">
      <FileTreeFolder
        v-for="child in childFolders"
        :key="child.id"
        :folder="child"
        :folders="folders"
        :transcripts="transcripts"
        class="group"
        @request-rename="$emit('request-rename', $event)"
        @delete="$emit('delete', $event)"
        @move="$emit('move', $event)"
      />

      <FileTreeItem
        v-for="transcript in childTranscripts"
        :key="transcript.id"
        :transcript="transcript"
        @request-rename="$emit('request-rename', $event)"
      />

      <div
        v-if="childFolders.length === 0 && childTranscripts.length === 0"
        class="px-2 py-1 text-xs text-gray-400 italic"
      >
        Empty folder
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Folder, Transcript } from '~/composables/useFileTree'

const props = defineProps<{
  folder: Folder
  folders: Folder[]
  transcripts: Transcript[]
}>()

const emit = defineEmits<{
  'request-rename': [payload: { id: string; type: 'folder' | 'transcript'; currentName: string }]
  'delete': [id: string]
  'move': [payload: { type: 'folder' | 'transcript'; id: string; targetFolderId: string | null }]
}>()

const isExpanded = ref(true)
const isDragOver = ref(false)

const childFolders = computed(() => props.folders.filter(f => f.parent_id === props.folder.id))
const childTranscripts = computed(() => props.transcripts.filter(t => t.folder_id === props.folder.id))

function toggle() {
  isExpanded.value = !isExpanded.value
}

function onRename() {
  emit('request-rename', {
    id: props.folder.id,
    type: 'folder',
    currentName: props.folder.name
  })
}

function onDragStart(e: DragEvent) {
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('application/json', JSON.stringify({
      type: 'folder',
      id: props.folder.id
    }))
  }
}

function onDragOver() {
  isDragOver.value = true
}

function onDragLeave() {
  isDragOver.value = false
}

function onDrop(e: DragEvent) {
  isDragOver.value = false

  const data = e.dataTransfer?.getData('application/json')
  if (!data) return

  try {
    const { type, id } = JSON.parse(data)

    // Don't drop folder into itself
    if (type === 'folder' && id === props.folder.id) return

    // Don't drop folder into its own descendant
    if (type === 'folder' && isDescendant(id, props.folder.id)) return

    emit('move', { type, id, targetFolderId: props.folder.id })
  } catch (err) {
    console.error('Failed to parse drop data:', err)
  }
}

function isDescendant(folderId: string, potentialDescendantId: string): boolean {
  let current = props.folders.find(f => f.id === potentialDescendantId)
  while (current) {
    if (current.parent_id === folderId) return true
    current = props.folders.find(f => f.id === current!.parent_id)
  }
  return false
}
</script>
