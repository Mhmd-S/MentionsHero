<template>
  <div>
    <div class="mb-8">
      <UButton
        to="/transcripts"
        variant="ghost"
        icon="i-heroicons-arrow-left"
        size="sm"
        class="mb-4"
      >
        Back to all transcripts
      </UButton>
      <h1 class="text-2xl font-bold">Transcript</h1>
    </div>

    <div v-if="pending" class="flex justify-center py-8">
      <UIcon name="i-heroicons-arrow-path" class="size-6 animate-spin" />
    </div>

    <div v-else-if="error" class="py-8">
      <UAlert color="error" title="Transcript not found" />
    </div>

    <div v-else-if="transcript" class="space-y-6">
      <div class="flex items-center justify-between">
        <div class="text-sm text-gray-500">
          <a
            :href="transcript.youtube_url"
            target="_blank"
            class="hover:underline flex items-center gap-1"
          >
            {{ transcript.youtube_url }}
            <UIcon name="i-heroicons-arrow-top-right-on-square" class="size-3" />
          </a>
        </div>
        <div class="text-xs text-gray-400">
          {{ formatDate(transcript.created_at) }}
        </div>
      </div>

      <div class="flex gap-2">
        <UButton
          variant="outline"
          icon="i-heroicons-clipboard-document"
          size="sm"
          @click="copyTranscript"
        >
          {{ copied ? 'Copied!' : 'Copy' }}
        </UButton>
        <UButton
          variant="outline"
          color="error"
          icon="i-heroicons-trash"
          size="sm"
          @click="deleteTranscript"
          :loading="deleting"
        >
          Delete
        </UButton>
      </div>

      <UCard>
        <div class="whitespace-pre-wrap text-sm leading-relaxed">
          {{ transcript.transcript }}
        </div>
      </UCard>
    </div>
  </div>
</template>

<script setup lang="ts">
interface Transcript {
  id: string
  youtube_url: string
  transcript: string
  created_at: string
}

const route = useRoute()
const router = useRouter()
const copied = ref(false)
const deleting = ref(false)

const { data: transcript, pending, error } = await useFetch<Transcript>(`/api/transcripts/${route.params.id}`)

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  })
}

async function copyTranscript() {
  if (!transcript.value) return
  await navigator.clipboard.writeText(transcript.value.transcript)
  copied.value = true
  setTimeout(() => {
    copied.value = false
  }, 2000)
}

async function deleteTranscript() {
  if (!confirm('Are you sure you want to delete this transcript?')) return

  deleting.value = true
  try {
    await $fetch(`/api/transcripts/${route.params.id}`, {
      method: 'DELETE'
    })
    router.push('/transcripts')
  } catch (err) {
    console.error('Failed to delete transcript')
  } finally {
    deleting.value = false
  }
}
</script>
