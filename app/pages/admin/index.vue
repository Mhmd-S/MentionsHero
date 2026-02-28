<script lang="ts">
definePageMeta({ layout: 'admin' })
</script>

<template>
  <div>
    <div class="mb-8">
      <h1 class="text-2xl font-bold">New Transcript</h1>
      <p class="text-gray-500 mt-1">Enter a YouTube URL to generate a transcript</p>
    </div>

    <!-- Single / detecting / batch mode: single column -->
    <div v-if="inputMode !== 'playlist'" class="max-w-xl space-y-6">
      <!-- URL Input Mode -->
      <div v-if="inputMode === 'single' || inputMode === 'detecting'">
        <UFormField label="YouTube URL">
          <UTextarea
            v-model="youtubeUrl"
            placeholder="https://www.youtube.com/watch?v=...&#10;&#10;Paste a video URL, playlist URL, or multiple URLs (one per line)"
            :rows="3"
            class="w-full"
            :disabled="isProcessing"
          />
        </UFormField>
      </div>

      <!-- Video Preview for single video -->
      <VideoPreview
        v-if="inputMode === 'single' && (videoInfo || videoLoading || videoError)"
        :video="videoInfo"
        :loading="videoLoading"
        :error="videoError"
      />

      <!-- Batch URL Input -->
      <BatchUrlInput
        v-if="inputMode === 'batch'"
        :urls="parsedUrls"
        v-model:selected="selectedVideos"
        @update:urls="parsedUrls = $event"
        @back="clearInput"
      />

      <FolderPicker v-model="selectedFolderId" :disabled="isProcessing" />

      <UFormField
        label="Speaker context (optional)"
        description="Help Gemini identify speakers, e.g. 'PMQ' or 'White House press with Caroline'"
      >
        <UTextarea
          v-model="speakerHint"
          placeholder="e.g. This is PMQ; speakers include the PM and opposition leader"
          :rows="2"
          class="w-full"
          :disabled="isProcessing"
        />
      </UFormField>

      <div class="flex gap-3">
        <UButton
          v-if="!isProcessing && !isCompleted && !isCancelled"
          @click="startJob"
          :loading="isStarting"
          :disabled="!canTranscribe || isStarting"
          size="lg"
        >
          {{ transcribeButtonLabel }}
        </UButton>

        <UButton
          v-if="isProcessing && !isStarting"
          @click="cancelJob"
          :loading="isCancelling"
          :disabled="isCancelling"
          color="error"
          variant="outline"
          size="lg"
        >
          Cancel
        </UButton>
      </div>

      <JobProgress
        v-if="progress"
        :progress="progress"
        :status-label="statusLabel"
        :chunk-info="chunkInfo"
        :substep-label="substepLabel"
        :substep-detail="substepDetail"
      />

      <UAlert
        v-if="error"
        color="error"
        :title="error"
      />

      <div v-if="isCompleted && progress?.transcript_id" class="space-y-4">
        <UAlert color="success" title="Transcript saved successfully!" />

        <div class="flex gap-3">
          <UButton
            variant="outline"
            :to="`/admin/transcripts/${progress.transcript_id}`"
          >
            View Transcript
          </UButton>

          <UButton
            variant="ghost"
            @click="resetForm"
          >
            Start New
          </UButton>
        </div>
      </div>

      <div v-if="isFailed" class="space-y-4">
        <UButton
          variant="outline"
          @click="resetForm"
        >
          Try Again
        </UButton>
      </div>

      <div v-if="isCancelled" class="space-y-4">
        <UAlert color="warning" title="Job was cancelled" />
        <UButton
          variant="outline"
          @click="resetForm"
        >
          Start New
        </UButton>
      </div>
    </div>

    <!-- Playlist mode: two-column layout -->
    <div v-else class="flex gap-6 items-start">
      <!-- Left column: playlist video list -->
      <div class="flex-1 min-w-0">
        <PlaylistSelector
          :playlist="playlistInfo"
          :loading="playlistLoading"
          :error="playlistError"
          v-model:selected="selectedVideos"
          @back="clearInput"
        />
      </div>

      <!-- Right column: transcript options -->
      <div class="w-80 flex-shrink-0 space-y-5">
        <FolderPicker v-model="selectedFolderId" :disabled="isProcessing" />

        <UFormField
          label="Speaker context (optional)"
          description="Help Gemini identify speakers"
        >
          <UTextarea
            v-model="speakerHint"
            placeholder="e.g. This is PMQ; speakers include the PM and opposition leader"
            :rows="2"
            class="w-full"
            :disabled="isProcessing"
          />
        </UFormField>

        <div class="flex gap-3">
          <UButton
            v-if="!isProcessing && !isCompleted && !isCancelled"
            @click="startJob"
            :loading="isStarting"
            :disabled="!canTranscribe || isStarting"
            size="lg"
          >
            {{ transcribeButtonLabel }}
          </UButton>

          <UButton
            v-if="isProcessing && !isStarting"
            @click="cancelJob"
            :loading="isCancelling"
            :disabled="isCancelling"
            color="error"
            variant="outline"
            size="lg"
          >
            Cancel
          </UButton>
        </div>

        <JobProgress
          v-if="progress"
          :progress="progress"
          :status-label="statusLabel"
          :chunk-info="chunkInfo"
          :substep-label="substepLabel"
          :substep-detail="substepDetail"
        />

        <UAlert
          v-if="error"
          color="error"
          :title="error"
        />

        <div v-if="isCompleted && progress?.transcript_id" class="space-y-4">
          <UAlert color="success" title="Transcript saved successfully!" />

          <div class="flex gap-3">
            <UButton
              variant="outline"
              :to="`/admin/transcripts/${progress.transcript_id}`"
            >
              View Transcript
            </UButton>

            <UButton
              variant="ghost"
              @click="resetForm"
            >
              Start New
            </UButton>
          </div>
        </div>

        <div v-if="isFailed" class="space-y-4">
          <UButton
            variant="outline"
            @click="resetForm"
          >
            Try Again
          </UButton>
        </div>

        <div v-if="isCancelled" class="space-y-4">
          <UAlert color="warning" title="Job was cancelled" />
          <UButton
            variant="outline"
            @click="resetForm"
          >
            Start New
          </UButton>
        </div>
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

interface PlaylistInfo {
  id: string
  title: string
  channel: string
  videoCount: number
  videos: VideoInfo[]
}

type InputMode = 'detecting' | 'single' | 'playlist' | 'batch'

const route = useRoute()
const router = useRouter()
const { authFetch } = useAuthFetch()

const youtubeUrl = ref('')
const selectedFolderId = ref<string | null>(null)
const speakerHint = ref('')
const isStarting = ref(false)
const currentJobId = ref<string | null>(route.query.jobId as string || null)

// Video preview state
const videoInfo = ref<VideoInfo | null>(null)
const videoLoading = ref(false)
const videoError = ref<string | null>(null)

// Playlist state
const playlistInfo = ref<PlaylistInfo | null>(null)
const playlistLoading = ref(false)
const playlistError = ref<string | null>(null)

// Batch/selection state
const parsedUrls = ref<VideoInfo[]>([])
const selectedVideos = ref<VideoInfo[]>([])

const inputMode = ref<InputMode>('detecting')

const { progress, error, statusLabel, chunkInfo, substepLabel, substepDetail, isActive } = useJobProgress(currentJobId)

const isCancelling = ref(false)
const isProcessing = computed(() => isActive.value || isStarting.value)
const isCompleted = computed(() => progress.value?.status === 'completed')
const isFailed = computed(() => progress.value?.status === 'failed')
const isCancelled = computed(() => progress.value?.status === 'cancelled')

const canTranscribe = computed(() => {
  if (inputMode.value === 'single') {
    return !!videoInfo.value && !videoLoading.value
  }
  if (inputMode.value === 'playlist' || inputMode.value === 'batch') {
    return selectedVideos.value.length > 0
  }
  return false
})

const transcribeButtonLabel = computed(() => {
  if (inputMode.value === 'playlist' || inputMode.value === 'batch') {
    const count = selectedVideos.value.length
    return count > 1 ? `Transcribe ${count} Videos` : 'Transcribe'
  }
  return 'Transcribe'
})

// URL type detection helpers
function isPlaylistUrl(url: string): boolean {
  return url.includes('list=') && (url.includes('youtube.com') || url.includes('youtu.be'))
}

function isSingleVideoUrl(url: string): boolean {
  const regex = /^(https?:\/\/)?(www\.)?(youtube\.com\/watch\?v=|youtu\.be\/)[a-zA-Z0-9_-]+/
  return regex.test(url.trim())
}

function parseMultipleUrls(input: string): string[] {
  const lines = input.split(/[\n,]/).map(l => l.trim()).filter(Boolean)
  return lines.filter(line => isSingleVideoUrl(line) || isPlaylistUrl(line))
}

// Debounced URL watcher
let debounceTimer: ReturnType<typeof setTimeout> | null = null

watch(youtubeUrl, (newUrl) => {
  // Clear previous state
  videoInfo.value = null
  videoError.value = null
  playlistInfo.value = null
  playlistError.value = null
  parsedUrls.value = []
  selectedVideos.value = []

  if (!newUrl.trim()) {
    inputMode.value = 'detecting'
    return
  }

  // Debounce the detection
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => detectAndFetch(newUrl), 500)
})

async function detectAndFetch(input: string) {
  const urls = parseMultipleUrls(input)

  if (urls.length === 0) {
    inputMode.value = 'detecting'
    return
  }

  // Check for multiple URLs (batch mode)
  if (urls.length > 1) {
    inputMode.value = 'batch'
    await fetchBatchVideoInfo(urls)
    return
  }

  const url = urls[0]!

  // Check for playlist
  if (isPlaylistUrl(url)) {
    inputMode.value = 'playlist'
    await fetchPlaylistInfo(url)
    return
  }

  // Single video
  if (isSingleVideoUrl(url)) {
    inputMode.value = 'single'
    await fetchVideoInfo(url)
    return
  }

  inputMode.value = 'detecting'
}

async function fetchVideoInfo(url: string) {
  videoLoading.value = true
  videoError.value = null

  try {
    const info = await authFetch<VideoInfo>('/api/video/info', {
      method: 'POST',
      body: { url }
    })
    videoInfo.value = { ...info, url }
  } catch (err: any) {
    videoError.value = err.data?.message || 'Failed to fetch video info'
  } finally {
    videoLoading.value = false
  }
}

async function fetchPlaylistInfo(url: string) {
  playlistLoading.value = true
  playlistError.value = null

  try {
    const info = await authFetch<PlaylistInfo>('/api/playlist/info', {
      method: 'POST',
      body: { url }
    })
    playlistInfo.value = info
    // Select all videos by default
    selectedVideos.value = [...info.videos]
  } catch (err: any) {
    playlistError.value = err.data?.message || 'Failed to fetch playlist info'
  } finally {
    playlistLoading.value = false
  }
}

async function fetchBatchVideoInfo(urls: string[]) {
  const results: VideoInfo[] = []

  for (const url of urls) {
    try {
      const info = await authFetch<VideoInfo>('/api/video/info', {
        method: 'POST',
        body: { url }
      })
      results.push({ ...info, url })
    } catch (err) {
      // Skip failed URLs
      console.error(`Failed to fetch info for ${url}:`, err)
    }
  }

  parsedUrls.value = results
  selectedVideos.value = [...results]
}

function clearInput() {
  youtubeUrl.value = ''
  inputMode.value = 'detecting'
}

async function startJob() {
  isStarting.value = true

  try {
    // Single video mode
    if (inputMode.value === 'single' && videoInfo.value) {
      const response = await authFetch<{ jobId: string }>('/api/jobs', {
        method: 'POST',
        body: {
          url: videoInfo.value.url || youtubeUrl.value.trim(),
          folderId: selectedFolderId.value,
          videoTitle: videoInfo.value.title,
          speakerHint: speakerHint.value?.trim() || undefined
        }
      })

      currentJobId.value = response.jobId
      router.replace({ query: { jobId: response.jobId } })
      return
    }

    // Batch mode (playlist or multiple URLs)
    if ((inputMode.value === 'playlist' || inputMode.value === 'batch') && selectedVideos.value.length > 0) {
      const response = await authFetch<{ jobIds: string[] }>('/api/jobs/batch', {
        method: 'POST',
        body: {
          videos: selectedVideos.value.map(v => ({
            url: v.url,
            title: v.title
          })),
          folderId: selectedFolderId.value,
          playlistId: playlistInfo.value?.id,
          playlistName: playlistInfo.value?.title,
          speakerHint: speakerHint.value?.trim() || undefined
        }
      })

      // Navigate to first job
      if (response.jobIds.length > 0) {
        currentJobId.value = response.jobIds[0]!
        router.replace({ query: { jobId: response.jobIds[0] } })
      }
      return
    }
  } catch (err: any) {
    console.error('Failed to start job:', err)
  } finally {
    isStarting.value = false
  }
}

function resetForm() {
  youtubeUrl.value = ''
  selectedFolderId.value = null
  speakerHint.value = ''
  currentJobId.value = null
  isCancelling.value = false
  videoInfo.value = null
  videoError.value = null
  playlistInfo.value = null
  playlistError.value = null
  parsedUrls.value = []
  selectedVideos.value = []
  inputMode.value = 'detecting'
  router.replace({ query: {} })
}

async function cancelJob() {
  if (!currentJobId.value) return

  isCancelling.value = true

  try {
    await authFetch(`/api/jobs/${currentJobId.value}/cancel`, {
      method: 'POST'
    })
  } catch (err: any) {
    console.error('Failed to cancel job:', err)
  } finally {
    isCancelling.value = false
  }
}

// Watch for route query changes
watch(() => route.query.jobId, (newJobId) => {
  const id = newJobId as string || null
  if (id !== currentJobId.value) {
    currentJobId.value = id
    if (!id) {
      resetForm()
    }
  }
})

// Restore YouTube URL from job if returning to an active job
watch(progress, (newProgress) => {
  if (newProgress && !youtubeUrl.value) {
    youtubeUrl.value = newProgress.youtube_url
  }
}, { immediate: true })
</script>
