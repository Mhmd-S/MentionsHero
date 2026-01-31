<template>
  <div class="space-y-4">
    <!-- Loading state -->
    <div v-if="loading" class="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
      <div class="flex items-center gap-3">
        <div class="animate-spin">
          <UIcon name="i-heroicons-arrow-path" class="size-5" />
        </div>
        <span class="text-sm text-gray-600 dark:text-gray-400">Loading playlist...</span>
      </div>
    </div>

    <!-- Error state -->
    <div v-else-if="error" class="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
      <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
      <UButton size="sm" variant="ghost" class="mt-2" @click="$emit('back')">
        Go back
      </UButton>
    </div>

    <!-- Playlist loaded -->
    <div v-else-if="playlist" class="space-y-4">
      <!-- Playlist header -->
      <div class="flex items-start justify-between p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
        <div>
          <h3 class="font-medium">{{ playlist.title }}</h3>
          <p class="text-sm text-gray-500 dark:text-gray-400">
            {{ playlist.channel }} &bull; {{ playlist.videoCount }} videos
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
          {{ selected.length }} of {{ playlist.videos.length }} selected
        </span>
      </div>

      <!-- Video list -->
      <div class="space-y-2 max-h-96 overflow-y-auto">
        <div
          v-for="(video, index) in playlist.videos"
          :key="video.id"
          class="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors cursor-pointer"
          @click="toggleSelection(video)"
        >
          <UCheckbox
            :model-value="isSelected(video)"
            @update:model-value="toggleSelection(video)"
            @click.stop
          />
          <span class="text-xs text-gray-400 w-6 text-right">{{ index + 1 }}</span>
          <img
            :src="video.thumbnail"
            :alt="video.title"
            class="w-20 h-12 object-cover rounded flex-shrink-0"
          />
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium truncate" :title="video.title">{{ video.title }}</p>
            <p class="text-xs text-gray-500 dark:text-gray-400">{{ video.durationFormatted }}</p>
          </div>
        </div>
      </div>

      <!-- Total duration -->
      <p class="text-xs text-gray-500 text-right">
        Total duration: {{ totalDuration }}
      </p>
    </div>
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

interface PlaylistInfo {
  id: string
  title: string
  channel: string
  videoCount: number
  videos: VideoInfo[]
}

const props = defineProps<{
  playlist: PlaylistInfo | null
  loading?: boolean
  error?: string | null
  selected: VideoInfo[]
}>()

const emit = defineEmits<{
  'update:selected': [videos: VideoInfo[]]
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
  if (props.playlist) {
    emit('update:selected', [...props.playlist.videos])
  }
}

function selectNone() {
  emit('update:selected', [])
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
