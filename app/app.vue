<template>
  <UApp>
    <UContainer class="py-10">
      <div class="max-w-2xl mx-auto space-y-6">
        <h1 class="text-2xl font-bold">YouTube Transcriber</h1>

        <UFormField label="YouTube URL">
          <UInput
            v-model="youtubeUrl"
            placeholder="https://www.youtube.com/watch?v=..."
            size="lg"
            class="w-full"
          />
        </UFormField>

        <UButton
          @click="transcribe"
          :loading="isLoading"
          :disabled="!youtubeUrl || isLoading"
          size="lg"
        >
          {{ isLoading ? 'Transcribing...' : 'Transcribe' }}
        </UButton>

        <UAlert
          v-if="error"
          color="error"
          :title="error"
        />

        <div v-if="transcript" class="space-y-2">
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-semibold">Transcript</h2>
            <UButton
              variant="ghost"
              size="sm"
              @click="copyTranscript"
            >
              {{ copied ? 'Copied!' : 'Copy' }}
            </UButton>
          </div>
          <div class="p-4 bg-gray-50 dark:bg-gray-900 rounded-lg whitespace-pre-wrap text-sm">
            {{ transcript }}
          </div>
        </div>
      </div>
    </UContainer>
  </UApp>
</template>

<script setup lang="ts">
const youtubeUrl = ref('')
const isLoading = ref(false)
const error = ref('')
const transcript = ref('')
const copied = ref(false)

async function transcribe() {
  if (!youtubeUrl.value) return

  isLoading.value = true
  error.value = ''
  transcript.value = ''

  try {
    const response = await $fetch<{ success: boolean; transcript: string }>('/api/download', {
      method: 'POST',
      body: { url: youtubeUrl.value }
    })

    transcript.value = response.transcript
  } catch (err: any) {
    error.value = err.data?.message || 'Transcription failed'
  } finally {
    isLoading.value = false
  }
}

async function copyTranscript() {
  await navigator.clipboard.writeText(transcript.value)
  copied.value = true
  setTimeout(() => {
    copied.value = false
  }, 2000)
}
</script>
