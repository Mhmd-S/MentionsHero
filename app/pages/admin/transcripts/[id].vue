<template>
  <div>
    <div class="mb-8">
      <UButton
        to="/admin/transcripts"
        variant="ghost"
        icon="i-heroicons-arrow-left"
        size="sm"
        class="mb-4"
      >
        Back to all transcripts
      </UButton>
      <h1 class="text-2xl font-bold">{{ transcript?.name || 'Transcript' }}</h1>
    </div>

    <div v-if="pending && !transcript" class="flex justify-center py-8">
      <UIcon name="i-heroicons-arrow-path" class="size-6 animate-spin" />
    </div>

    <div v-else-if="error && !transcript" class="py-8">
      <UAlert color="error" title="Transcript not found" />
    </div>

    <div v-if="transcript" class="space-y-6">
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
        <div class="text-xs text-gray-400 text-right space-y-0.5">
          <div v-if="transcript.upload_date">
            Uploaded {{ formatUploadDate(transcript.upload_date) }}
          </div>
          <div>Added {{ formatDate(transcript.created_at) }}</div>
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

      <div :class="speakerFrequencies.length > 0 ? 'grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-6' : ''">
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
                    v-model="searchInput"
                    placeholder="Search in transcript..."
                    icon="i-heroicons-magnifying-glass"
                  />
                </UFormField>
                <UFormField label="Highlight speakers">
                  <USelectMenu
                    v-model="selectedSpeakers"
                    :items="availableSpeakers"
                    :placeholder="selectedSpeakers.length === 0 ? 'Select speakers to highlight...' : `${selectedSpeakers.length} selected`"
                    multiple
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

        <UCard v-if="speakerFrequencies.length > 0" class="h-fit lg:sticky lg:top-4">
          <template #header>
            <div class="flex items-center gap-2">
              <UIcon name="i-heroicons-chart-bar" class="size-5" />
              <h3 class="font-semibold">Frequency by Speaker</h3>
            </div>
          </template>
          <div class="space-y-3">
            <div
              v-for="freq in speakerFrequencies"
              :key="freq.speaker"
              class="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-800 last:border-0"
            >
              <span class="text-sm font-medium truncate mr-2">{{ freq.speaker }}</span>
              <span class="text-sm font-semibold text-primary bg-primary/10 px-2 py-0.5 rounded">
                {{ freq.count }}
              </span>
            </div>
          </div>
        </UCard>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
interface SpeakerFrequency {
  speaker: string
  count: number
}

interface Transcript {
  id: string
  name: string | null
  youtube_url: string
  transcript: string
  created_at: string
  upload_date: string | null
  availableSpeakers?: string[]
  hasHighlights?: boolean
  matchCount?: number
  speakerFrequencies?: SpeakerFrequency[]
}

const route = useRoute()
const router = useRouter()
const { authFetch } = useAuthFetch()
const copied = ref(false)
const deleting = ref(false)
const searchInput = ref('')
const debouncedSearch = ref('')
const selectedSpeakers = ref<string[]>([])

// Debounce search input
let debounceTimer: ReturnType<typeof setTimeout> | null = null
watch(searchInput, (val) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    debouncedSearch.value = val
  }, 400)
})

const searchQuery = computed(() => {
  const query: Record<string, string> = {}
  if (debouncedSearch.value.trim()) {
    query.search = debouncedSearch.value.trim()
  }
  if (selectedSpeakers.value.length > 0) {
    query.speakers = selectedSpeakers.value.join(',')
  }
  return query
})

const transcript = ref<Transcript | null>(null)
const pending = ref(true)
const error = ref<any>(null)

async function refresh() {
  pending.value = true
  error.value = null
  try {
    const query: Record<string, string> = {}
    if (debouncedSearch.value.trim()) query.search = debouncedSearch.value.trim()
    if (selectedSpeakers.value.length > 0) query.speakers = selectedSpeakers.value.join(',')
    const params = new URLSearchParams(query).toString()
    const url = `/api/transcripts/${route.params.id}` + (params ? `?${params}` : '')
    transcript.value = await authFetch<Transcript>(url)
  } catch (e: any) {
    error.value = e
  } finally {
    pending.value = false
  }
}

watch(searchQuery, () => refresh())
onMounted(() => refresh())

const availableSpeakers = computed(() => transcript.value?.availableSpeakers || [])
const hasHighlights = computed(() => transcript.value?.hasHighlights || false)
const matchCount = computed(() => transcript.value?.matchCount ?? null)
const speakerFrequencies = computed(() => transcript.value?.speakerFrequencies || [])
const hasFilters = computed(() => searchInput.value.trim().length > 0 || selectedSpeakers.value.length > 0)

// Initialize available speakers when transcript loads
watch(transcript, (newTranscript) => {
  if (newTranscript && !newTranscript.availableSpeakers && newTranscript.transcript) {
    // Extract speakers from transcript if not provided
    const speakerPattern = /^([A-Z][a-zA-Z'-]*(?:\s+[A-Z][a-zA-Z'-]*)?|[A-Z_0-9]+|Character\d+):/gm
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

function clearFilters() {
  searchInput.value = ''
  debouncedSearch.value = ''
  selectedSpeakers.value = []
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

function formatUploadDate(dateStr: string) {
  const year = dateStr.slice(0, 4)
  const month = dateStr.slice(4, 6)
  const day = dateStr.slice(6, 8)
  return new Date(`${year}-${month}-${day}`).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
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
    await authFetch(`/api/transcripts/${route.params.id}`, {
      method: 'DELETE'
    })
    router.push('/admin/transcripts')
  } catch (err) {
    console.error('Failed to delete transcript')
  } finally {
    deleting.value = false
  }
}
</script>
