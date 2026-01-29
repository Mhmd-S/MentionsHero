<template>
  <div>
    <div class="mb-8">
      <h1 class="text-2xl font-bold">New Transcript</h1>
      <p class="text-gray-500 mt-1">Enter a YouTube URL to generate a transcript</p>
    </div>

    <div class="max-w-xl space-y-6">
      <UFormField label="YouTube URL">
        <UInput
          v-model="youtubeUrl"
          placeholder="https://www.youtube.com/watch?v=..."
          size="lg"
          class="w-full"
          :disabled="isProcessing"
        />
      </UFormField>

      <UFormField>
        <UCheckbox
          v-model="skipCleanup"
          label="Skip punctuation cleanup (faster, but less polished)"
          :disabled="isProcessing"
        />
      </UFormField>

      <div class="flex gap-3">
        <UButton
          v-if="!isProcessing && !isCompleted && !isCancelled"
          @click="startJob"
          :loading="isStarting"
          :disabled="!youtubeUrl || isStarting"
          size="lg"
        >
          Transcribe
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
            :to="`/transcripts/${progress.transcript_id}`"
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
</template>

<script setup lang="ts">
const route = useRoute()
const router = useRouter()

const youtubeUrl = ref('')
const skipCleanup = ref(false)
const isStarting = ref(false)
const currentJobId = ref<string | null>(route.query.jobId as string || null)

const { progress, error, statusLabel, chunkInfo, substepLabel, substepDetail, isActive } = useJobProgress(currentJobId)

const isCancelling = ref(false)
const isProcessing = computed(() => isActive.value || isStarting.value)
const isCompleted = computed(() => progress.value?.status === 'completed')
const isFailed = computed(() => progress.value?.status === 'failed')
const isCancelled = computed(() => progress.value?.status === 'cancelled')

async function startJob() {
  if (!youtubeUrl.value) return

  isStarting.value = true

  try {
    const response = await $fetch<{ jobId: string }>('/api/jobs', {
      method: 'POST',
      body: { url: youtubeUrl.value, skipCleanup: skipCleanup.value }
    })

    currentJobId.value = response.jobId

    // Update URL with jobId for refresh recovery
    router.replace({ query: { jobId: response.jobId } })
  } catch (err: any) {
    // Error will be shown through the progress composable or caught here
    console.error('Failed to start job:', err)
  } finally {
    isStarting.value = false
  }
}

function resetForm() {
  youtubeUrl.value = ''
  skipCleanup.value = false
  currentJobId.value = null
  isCancelling.value = false
  router.replace({ query: {} })
}

async function cancelJob() {
  if (!currentJobId.value) return

  isCancelling.value = true

  try {
    await $fetch(`/api/jobs/${currentJobId.value}/cancel`, {
      method: 'POST'
    })
  } catch (err: any) {
    console.error('Failed to cancel job:', err)
  } finally {
    isCancelling.value = false
  }
}

// Watch for route query changes (e.g., clicking "New Transcript" while viewing a job)
watch(() => route.query.jobId, (newJobId) => {
  const id = newJobId as string || null
  if (id !== currentJobId.value) {
    currentJobId.value = id
    // Clear form when navigating away from a job
    if (!id) {
      youtubeUrl.value = ''
      skipCleanup.value = false
      isCancelling.value = false
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
