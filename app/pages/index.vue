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

      <UButton
        v-if="!isProcessing && !isCompleted"
        @click="startJob"
        :loading="isStarting"
        :disabled="!youtubeUrl || isStarting"
        size="lg"
      >
        Transcribe
      </UButton>

      <JobProgress
        v-if="progress"
        :progress="progress"
        :status-label="statusLabel"
        :chunk-info="chunkInfo"
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
    </div>
  </div>
</template>

<script setup lang="ts">
const route = useRoute()
const router = useRouter()

const youtubeUrl = ref('')
const isStarting = ref(false)
const currentJobId = ref<string | null>(route.query.jobId as string || null)

const { progress, error, statusLabel, chunkInfo, isActive } = useJobProgress(currentJobId)

const isProcessing = computed(() => isActive.value || isStarting.value)
const isCompleted = computed(() => progress.value?.status === 'completed')
const isFailed = computed(() => progress.value?.status === 'failed')

async function startJob() {
  if (!youtubeUrl.value) return

  isStarting.value = true

  try {
    const response = await $fetch<{ jobId: string }>('/api/jobs', {
      method: 'POST',
      body: { url: youtubeUrl.value }
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
  currentJobId.value = null
  router.replace({ query: {} })
}

// Restore YouTube URL from job if returning to an active job
watch(progress, (newProgress) => {
  if (newProgress && !youtubeUrl.value) {
    youtubeUrl.value = newProgress.youtube_url
  }
}, { immediate: true })
</script>
