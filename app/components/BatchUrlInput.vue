<template>
  <div class="space-y-4">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div>
        <h3 class="font-medium">Multiple Videos</h3>
        <p class="text-xs text-gray-500 dark:text-gray-400">
          {{ urls.length }} videos detected
        </p>
      </div>
      <UButton size="xs" variant="ghost" @click="$emit('back')">
        <UIcon name="i-heroicons-x-mark" class="size-4" />
      </UButton>
    </div>

    <!-- Selection controls -->
    <div class="flex items-center justify-between">
      <div class="flex gap-2">
        <UButton size="xs" variant="outline" @click="selectAll">Select All</UButton>
        <UButton size="xs" variant="outline" @click="selectNone">Select None</UButton>
      </div>
      <span class="text-sm text-gray-500">
        {{ selected.length }} of {{ urls.length }} selected
      </span>
    </div>

    <!-- Video list -->
    <div class="space-y-2 max-h-96 overflow-y-auto">
      <div
        v-for="video in urls"
        :key="video.id"
        class="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors cursor-pointer"
        @click="toggleSelection(video)"
      >
        <UCheckbox
          :model-value="isSelected(video)"
          @update:model-value="toggleSelection(video)"
          @click.stop
        />
        <img
          :src="video.thumbnail"
          :alt="video.title"
          class="w-20 h-12 object-cover rounded flex-shrink-0"
        />
        <div class="flex-1 min-w-0">
          <p class="text-sm font-medium truncate" :title="video.title">{{ video.title }}</p>
          <div class="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
            <span>{{ video.channel }}</span>
            <span>&bull;</span>
            <span>{{ video.durationFormatted }}</span>
          </div>
        </div>
        <button
          class="p-1 rounded hover:bg-gray-300 dark:hover:bg-gray-600 transition-colors"
          title="Remove from list"
          @click.stop="removeVideo(video)"
        >
          <UIcon name="i-heroicons-trash" class="size-4 text-gray-400 hover:text-red-500" />
        </button>
      </div>

      <!-- Empty state for removed videos -->
      <div v-if="urls.length === 0" class="py-8 text-center text-gray-500">
        <p>No videos in list</p>
        <UButton size="sm" variant="ghost" class="mt-2" @click="$emit('back')">
          Go back
        </UButton>
      </div>
    </div>

    <!-- Total duration -->
    <p v-if="urls.length > 0" class="text-xs text-gray-500 text-right">
      Total duration: {{ totalDuration }}
    </p>
  </div>
</template>

<script setup lang="ts">
interface VideoInfo {
  id: string
  title: string
  duration: number
  durationFormatted: string
  thumbnail: string
  channel: string
  url: string
}

const props = defineProps<{
  urls: VideoInfo[]
  selected: VideoInfo[]
}>()

const emit = defineEmits<{
  'update:selected': [videos: VideoInfo[]]
  'update:urls': [videos: VideoInfo[]]
  'back': []
}>()

function isSelected(video: VideoInfo): boolean {
  return props.selected.some(v => v.id === video.id)
}

function toggleSelection(video: VideoInfo) {
  if (isSelected(video)) {
    emit('update:selected', props.selected.filter(v => v.id !== video.id))
  } else {
    emit('update:selected', [...props.selected, video])
  }
}

function selectAll() {
  emit('update:selected', [...props.urls])
}

function selectNone() {
  emit('update:selected', [])
}

function removeVideo(video: VideoInfo) {
  emit('update:urls', props.urls.filter(v => v.id !== video.id))
  emit('update:selected', props.selected.filter(v => v.id !== video.id))
}

const totalDuration = computed(() => {
  const totalSeconds = props.selected.reduce((sum, v) => sum + (v.duration || 0), 0)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)

  if (hours > 0) {
    return `${hours}h ${minutes}m`
  }
  return `${minutes}m`
})
</script>
