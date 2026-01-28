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
        <template #header>
          <div class="space-y-4">
            <div class="flex items-center justify-between">
              <h2 class="text-lg font-semibold">Search & Highlight</h2>
              <div class="flex items-center gap-3">
                <div v-if="matchCount !== null && matchCount > 0" class="text-sm text-gray-600 dark:text-gray-400">
                  <span class="font-semibold">{{ matchCount }}</span> match{{ matchCount !== 1 ? 'es' : '' }} found
                </div>
                <UButton
                  v-if="hasFilters"
                  variant="ghost"
                  size="sm"
                  @click="clearFilters"
                >
                  Clear
                </UButton>
              </div>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
              <UFormField label="Search text">
                <UInput
                  v-model="searchString"
                  placeholder="Search in transcript..."
                  icon="i-heroicons-magnifying-glass"
                  @input="applyFilters"
                />
              </UFormField>
              <UFormField label="Highlight speakers">
                <USelectMenu
                  v-model="selectedSpeakers"
                  :options="availableSpeakers"
                  :placeholder="selectedSpeakers.length === 0 ? 'Select speakers to highlight...' : `${selectedSpeakers.length} selected`"
                  multiple
                  @update:model-value="applyFilters"
                />
              </UFormField>
            </div>
          </div>
        </template>
        <div class="whitespace-pre-wrap text-sm leading-relaxed">
          <div
            v-if="hasHighlights"
            v-html="transcript.transcript"
          />
          <div v-else>{{ transcript.transcript }}</div>
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
  availableSpeakers?: string[]
  hasHighlights?: boolean
  matchCount?: number
}

const route = useRoute()
const router = useRouter()
const copied = ref(false)
const deleting = ref(false)
const searchString = ref('')
const selectedSpeakers = ref<string[]>([])

const searchQuery = computed(() => {
  const query: Record<string, string> = {}
  if (searchString.value.trim()) {
    query.search = searchString.value.trim()
  }
  if (selectedSpeakers.value.length > 0) {
    query.speakers = selectedSpeakers.value.join(',')
  }
  return query
})

const { data: transcript, pending, error, refresh } = await useFetch<Transcript>(
  `/api/transcripts/${route.params.id}`,
  {
    query: searchQuery,
    watch: [searchQuery]
  }
)

const availableSpeakers = computed(() => transcript.value?.availableSpeakers || [])
const hasHighlights = computed(() => transcript.value?.hasHighlights || false)
const matchCount = computed(() => transcript.value?.matchCount ?? null)
const hasFilters = computed(() => searchString.value.trim().length > 0 || selectedSpeakers.value.length > 0)

// Initialize available speakers when transcript loads
watch(transcript, (newTranscript) => {
  if (newTranscript && !newTranscript.availableSpeakers && newTranscript.transcript) {
    // Extract speakers from transcript if not provided
    const speakerPattern = /^([A-Z_0-9]+|Character\d+):/gm
    const speakers = new Set<string>()
    const matches = newTranscript.transcript.matchAll(speakerPattern)
    for (const match of matches) {
      speakers.add(match[1]!)
    }
    if (newTranscript) {
      newTranscript.availableSpeakers = Array.from(speakers).sort()
    }
  }
}, { immediate: true })

function applyFilters() {
  // Filters are applied automatically via reactive query params
  // No need to manually refresh as watch handles it
}

function clearFilters() {
  searchString.value = ''
  selectedSpeakers.value = []
  applyFilters()
}

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
  // Strip HTML tags when copying
  const textToCopy = hasHighlights.value
    ? transcript.value.transcript.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, ' ')
    : transcript.value.transcript
  await navigator.clipboard.writeText(textToCopy)
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
