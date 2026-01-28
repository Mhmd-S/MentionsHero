<template>
  <div v-if="jobs.length > 0" class="mt-8 pt-4 border-t border-gray-200 dark:border-gray-700">
    <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 px-3">
      Active Jobs
    </h3>

    <div class="space-y-2">
      <NuxtLink
        v-for="job in jobs"
        :key="job.id"
        :to="`/?jobId=${job.id}`"
        class="flex items-center gap-3 px-3 py-2 rounded-lg text-sm hover:bg-gray-200 dark:hover:bg-gray-800 transition-colors"
      >
        <UIcon
          :name="statusIcon(job.status)"
          class="size-4 flex-shrink-0"
          :class="statusIconClass(job.status)"
        />
        <span class="truncate flex-1">{{ formatUrl(job.youtube_url) }}</span>
      </NuxtLink>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { JobStatus } from '~/composables/useJobProgress'

interface Job {
  id: string
  youtube_url: string
  status: JobStatus
}

const jobs = ref<Job[]>([])

const fetchJobs = async () => {
  try {
    const response = await $fetch<{ jobs: Job[] }>('/api/jobs')
    jobs.value = response.jobs
  } catch (e) {
    console.error('Failed to fetch jobs:', e)
  }
}

// Poll for active jobs
let pollInterval: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchJobs()
  pollInterval = setInterval(fetchJobs, 5000)
})

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
})

function formatUrl(url: string): string {
  try {
    const urlObj = new URL(url)
    const videoId = urlObj.searchParams.get('v') || urlObj.pathname.slice(1)
    return videoId.slice(0, 11) + (videoId.length > 11 ? '...' : '')
  } catch {
    return url.slice(0, 20) + '...'
  }
}

function statusIcon(status: JobStatus): string {
  const icons: Record<JobStatus, string> = {
    pending: 'i-heroicons-clock',
    downloading: 'i-heroicons-arrow-down-tray',
    transcribing: 'i-heroicons-language',
    cleaning: 'i-heroicons-sparkles',
    saving: 'i-heroicons-cloud-arrow-up',
    completed: 'i-heroicons-check-circle',
    failed: 'i-heroicons-x-circle',
    cancelled: 'i-heroicons-x-mark'
  }
  return icons[status] || 'i-heroicons-question-mark-circle'
}

function statusIconClass(status: JobStatus): string {
  if (status === 'failed') return 'text-red-500'
  if (status === 'completed') return 'text-green-500'
  if (status === 'cancelled') return 'text-yellow-500'
  return 'text-primary animate-pulse'
}
</script>
