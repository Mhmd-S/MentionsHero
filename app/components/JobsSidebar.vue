<template>
  <div v-if="jobs.length > 0" class="mt-8 pt-4 border-t border-gray-200 dark:border-gray-700">
    <h3 class="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-3 px-3">
      Active Jobs
    </h3>

    <div class="space-y-4">
      <!-- Grouped by playlist -->
      <div v-for="group in groupedJobs" :key="group.key" class="space-y-1">
        <!-- Playlist header -->
        <div v-if="group.playlistName" class="flex items-center justify-between px-3 py-1">
          <span class="text-xs font-medium text-gray-600 dark:text-gray-400 truncate flex-1">
            {{ group.playlistName }}
          </span>
          <button
            v-if="group.jobs.some(j => !['completed', 'failed', 'cancelled'].includes(j.status))"
            class="text-xs text-red-500 hover:text-red-600 ml-2"
            title="Cancel all in playlist"
            @click.stop="bulkCancel(group.playlistId!)"
          >
            Cancel all
          </button>
        </div>

        <!-- Jobs in group -->
        <div
          v-for="(job, index) in group.jobs"
          :key="job.id"
          class="group flex items-center gap-2 px-3 py-2 rounded-lg text-sm hover:bg-gray-200 dark:hover:bg-gray-800 transition-colors"
        >
          <NuxtLink
            :to="`/?jobId=${job.id}`"
            class="flex items-center gap-3 flex-1 min-w-0"
          >
            <UIcon
              :name="statusIcon(job.status)"
              class="size-4 flex-shrink-0"
              :class="statusIconClass(job.status)"
            />
            <span class="truncate">{{ formatJobLabel(job, group.jobs.length, index) }}</span>
          </NuxtLink>

          <button
            class="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-gray-300 dark:hover:bg-gray-700 transition-all"
            title="Force cancel this job"
            @click.stop="forceCancel(job.id)"
          >
            <UIcon name="i-heroicons-x-mark" class="size-4 text-red-500" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { JobStatus } from '~/composables/useJobProgress'

interface Job {
  id: string
  youtube_url: string
  status: JobStatus
  playlist_id?: string | null
  playlist_name?: string | null
  playlist_index?: number | null
  video_title?: string | null
}

interface JobGroup {
  key: string
  playlistId: string | null
  playlistName: string | null
  jobs: Job[]
}

const jobs = ref<Job[]>([])

const groupedJobs = computed((): JobGroup[] => {
  const groups: Map<string, JobGroup> = new Map()

  for (const job of jobs.value) {
    const key = job.playlist_id || `single-${job.id}`

    if (!groups.has(key)) {
      groups.set(key, {
        key,
        playlistId: job.playlist_id || null,
        playlistName: job.playlist_name || null,
        jobs: []
      })
    }

    groups.get(key)!.jobs.push(job)
  }

  // Sort jobs within each group by playlist_index
  for (const group of groups.values()) {
    group.jobs.sort((a, b) => (a.playlist_index ?? 0) - (b.playlist_index ?? 0))
  }

  return Array.from(groups.values())
})

const { getAccessToken } = useAuth()
const { authFetch } = useAuthFetch()

let eventSource: EventSource | null = null

function connectJobsStream() {
  if (import.meta.server) return
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  const token = getAccessToken()
  const url = token
    ? `/api/jobs/list/stream?token=${encodeURIComponent(token)}`
    : '/api/jobs/list/stream'
  eventSource = new EventSource(url)
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as { jobs: Job[] }
      jobs.value = data.jobs ?? []
    } catch (e) {
      console.error('Failed to parse jobs stream:', e)
    }
  }
  eventSource.onerror = () => {
    eventSource?.close()
    eventSource = null
  }
}

async function forceCancel(jobId: string) {
  try {
    await authFetch(`/api/jobs/${jobId}/force-cancel`, { method: 'POST' })
    jobs.value = jobs.value.filter(j => j.id !== jobId)
  } catch (e) {
    console.error('Failed to force cancel job:', e)
  }
}

async function bulkCancel(playlistId: string) {
  try {
    await authFetch('/api/jobs/bulk-cancel', {
      method: 'POST',
      body: { playlistId }
    })
    jobs.value = jobs.value.filter(j => j.playlist_id !== playlistId)
  } catch (e) {
    console.error('Failed to bulk cancel jobs:', e)
  }
}

onMounted(() => {
  connectJobsStream()
})

onUnmounted(() => {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
})

function formatJobLabel(job: Job, totalInGroup: number, index: number): string {
  // If it has a video title, use that
  if (job.video_title) {
    const title = job.video_title.length > 25
      ? job.video_title.slice(0, 22) + '...'
      : job.video_title

    if (totalInGroup > 1) {
      return `${index + 1}. ${title}`
    }
    return title
  }

  // Fall back to video ID
  try {
    const urlObj = new URL(job.youtube_url)
    const videoId = urlObj.searchParams.get('v') || urlObj.pathname.slice(1)
    const label = videoId.slice(0, 11) + (videoId.length > 11 ? '...' : '')

    if (totalInGroup > 1) {
      return `${index + 1}. ${label}`
    }
    return label
  } catch {
    return job.youtube_url.slice(0, 20) + '...'
  }
}

function statusIcon(status: JobStatus): string {
  const icons: Record<JobStatus, string> = {
    pending: 'i-heroicons-clock',
    downloading: 'i-heroicons-arrow-down-tray',
    transcribing: 'i-heroicons-language',
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
