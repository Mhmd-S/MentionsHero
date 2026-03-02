<template>
  <div class="space-y-3">
    <!-- Loading state -->
    <div v-if="loading" class="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
      <div class="flex items-center gap-3">
        <div class="animate-spin">
          <UIcon name="i-lucide-refresh-cw" class="size-5" />
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
    <div v-else-if="playlist" class="flex flex-col space-y-3">
      <!-- Playlist header -->
      <div class="flex items-start justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
        <div>
          <h3 class="font-medium">{{ playlist.title }}</h3>
          <p class="text-sm text-gray-500 dark:text-gray-400">
            {{ playlist.channel }} &bull; {{ playlist.videoCount }} videos
          </p>
        </div>
        <UButton size="xs" variant="ghost" @click="$emit('back')">
          <UIcon name="i-lucide-x" class="size-4" />
        </UButton>
      </div>

      <!-- Search and selection controls -->
      <div class="space-y-2">
        <UInput
          v-model="searchQuery"
          placeholder="Search videos..."
          icon="i-lucide-search"
          size="sm"
          class="w-full"
        />
        <div class="flex items-center justify-between">
          <div class="flex gap-2">
            <UButton size="xs" variant="outline" @click="selectAll">Select All</UButton>
            <UButton size="xs" variant="outline" @click="selectNone">Select None</UButton>
          </div>
          <span class="text-sm text-gray-500">
            {{ selected.length }} of {{ playlist.videos.length }} selected
            <template v-if="searchQuery && filteredVideos.length !== playlist.videos.length">
              ({{ filteredVideos.length }} shown)
            </template>
          </span>
        </div>
      </div>

      <!-- Video list -->
      <div class="space-y-1.5 max-h-[calc(100vh-320px)] min-h-64 overflow-y-auto">
        <div
          v-for="video in filteredVideos"
          :key="video.id"
          class="flex items-center gap-3 p-2.5 bg-gray-50 dark:bg-gray-800 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors cursor-pointer"
          @click="toggleSelection(video)"
        >
          <UCheckbox
            :model-value="isSelected(video)"
            @update:model-value="toggleSelection(video)"
            @click.stop
          />
          <span class="text-xs text-gray-400 w-6 text-right">{{ getVideoIndex(video) }}</span>
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
        <p v-if="searchQuery && filteredVideos.length === 0" class="text-sm text-gray-400 text-center py-4">
          No videos match "{{ searchQuery }}"
        </p>
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

const searchQuery = ref('')

const filteredVideos = computed(() => {
  if (!props.playlist || !searchQuery.value.trim()) {
    return props.playlist?.videos ?? []
  }
  const query = searchQuery.value.toLowerCase()
  return props.playlist.videos.filter(v => v.title.toLowerCase().includes(query))
})

function getVideoIndex(video: VideoInfo): number {
  const idx = props.playlist?.videos.indexOf(video) ?? -1
  return idx + 1
}

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
  const visible = filteredVideos.value
  const currentIds = new Set(props.selected.map(v => v.id))
  const toAdd = visible.filter(v => !currentIds.has(v.id))
  emit('update:selected', [...props.selected, ...toAdd])
}

function selectNone() {
  const visibleIds = new Set(filteredVideos.value.map(v => v.id))
  emit('update:selected', props.selected.filter(v => !visibleIds.has(v.id)))
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
