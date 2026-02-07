<template>
  <div
    class="file-tree-item group flex items-center gap-2 px-2 py-1.5 rounded-md text-sm cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
    :class="{ 'bg-primary-100 dark:bg-primary-900/50': isActive }"
    :data-id="transcript.id"
    data-type="transcript"
    draggable="true"
    @dragstart="onDragStart"
    tabindex="0"
  >
    <UIcon name="i-heroicons-document-text" class="size-4 text-gray-500 shrink-0" />

    <NuxtLink
      :to="`/transcripts/${transcript.id}`"
      class="flex-1 truncate"
      draggable="false"
      @click.stop
    >
      {{ transcript.name || 'Untitled' }}
    </NuxtLink>

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
      @click.stop="onDelete"
    >
      <UIcon name="i-heroicons-trash" class="size-4" />
    </button>
  </div>
</template>

<script setup lang="ts">
import type { Transcript } from '~/composables/useFileTree'

const props = defineProps<{
  transcript: Transcript
}>()

const emit = defineEmits<{
  'request-rename': [payload: { id: string; type: 'transcript'; currentName: string }]
  'delete': [id: string]
}>()

const route = useRoute()

const isActive = computed(() => route.params.id === props.transcript.id)

function onRename() {
  emit('request-rename', {
    id: props.transcript.id,
    type: 'transcript',
    currentName: props.transcript.name || 'Untitled'
  })
}

function onDelete() {
  if (confirm('Are you sure you want to delete this transcript?')) {
    emit('delete', props.transcript.id)
  }
}

function onDragStart(e: DragEvent) {
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('application/json', JSON.stringify({
      type: 'transcript',
      id: props.transcript.id
    }))
  }
}
</script>
