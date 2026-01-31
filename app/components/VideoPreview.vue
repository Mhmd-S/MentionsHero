<template>
  <div v-if="loading" class="flex items-center gap-3 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
    <div class="w-32 h-18 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
    <div class="flex-1 space-y-2">
      <div class="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4 animate-pulse" />
      <div class="h-3 bg-gray-200 dark:bg-gray-700 rounded w-1/2 animate-pulse" />
    </div>
  </div>

  <div v-else-if="error" class="p-4 bg-red-50 dark:bg-red-900/20 rounded-lg">
    <p class="text-sm text-red-600 dark:text-red-400">{{ error }}</p>
  </div>

  <div v-else-if="video" class="flex items-start gap-4 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
    <img
      :src="video.thumbnail"
      :alt="video.title"
      class="w-32 h-18 object-cover rounded flex-shrink-0"
    />
    <div class="flex-1 min-w-0">
      <h3 class="font-medium text-sm truncate" :title="video.title">{{ video.title }}</h3>
      <p class="text-xs text-gray-500 dark:text-gray-400 mt-1">{{ video.channel }}</p>
      <div class="flex items-center gap-3 mt-2 text-xs text-gray-500 dark:text-gray-400">
        <span class="flex items-center gap-1">
          <UIcon name="i-heroicons-clock" class="size-3" />
          {{ video.durationFormatted }}
        </span>
        <span v-if="video.viewCount" class="flex items-center gap-1">
          <UIcon name="i-heroicons-eye" class="size-3" />
          {{ formatViewCount(video.viewCount) }}
        </span>
      </div>
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
  viewCount?: number
  uploadDate?: string
  url: string
}

const props = defineProps<{
  video: VideoInfo | null
  loading?: boolean
  error?: string | null
}>()

function formatViewCount(count: number): string {
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M views`
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}K views`
  }
  return `${count} views`
}
</script>
