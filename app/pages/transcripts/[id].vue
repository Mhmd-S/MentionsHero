<script setup lang="ts">
const route = useRoute()
const transcriptId = route.params.id as string
const { publicFetch } = usePublicApi()
const { isSubscribed } = useSubscription()

interface SpeakerFrequency {
  speaker: string
  count: number
}

interface TranscriptDetail {
  id: string
  youtube_url: string | null
  transcript: string
  name: string | null
  created_at: string
  is_premium: boolean
  is_locked: boolean
  hasHighlights?: boolean
  matchCount?: number
  speakerFrequencies?: SpeakerFrequency[]
}

const transcript = ref<TranscriptDetail | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
const searchInput = ref('')
const debouncedSearch = ref('')

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
  return query
})

async function refresh() {
  loading.value = true
  error.value = null
  try {
    const params = new URLSearchParams(searchQuery.value).toString()
    const url = `/api/public/transcripts/${transcriptId}` + (params ? `?${params}` : '')
    transcript.value = await publicFetch<TranscriptDetail>(url)
  } catch (e: any) {
    error.value = e.data?.detail || 'Transcript not found'
  } finally {
    loading.value = false
  }
}

watch(searchQuery, () => refresh())
onMounted(() => refresh())

const hasHighlights = computed(() => transcript.value?.hasHighlights || false)
const matchCount = computed(() => transcript.value?.matchCount ?? null)
const speakerFrequencies = computed(() => transcript.value?.speakerFrequencies || [])
const hasSearch = computed(() => searchInput.value.trim().length > 0)

function clearSearch() {
  searchInput.value = ''
  debouncedSearch.value = ''
}

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <div>
    <!-- Back -->
    <UButton
      variant="ghost"
      icon="i-heroicons-arrow-left"
      size="sm"
      class="mb-4"
      @click="$router.back()"
    >
      Back
    </UButton>

    <!-- Loading -->
    <div v-if="loading && !transcript" class="flex justify-center py-8">
      <UIcon name="i-heroicons-arrow-path" class="size-6 animate-spin" />
    </div>

    <!-- Error -->
    <div v-else-if="error && !transcript" class="py-8">
      <UAlert color="error" :title="error" />
    </div>

    <div v-if="transcript" class="space-y-6">
      <!-- Header -->
      <div>
        <div class="flex items-center gap-3 mb-2">
          <h1 class="text-2xl font-bold">{{ transcript.name || 'Transcript' }}</h1>
          <UBadge v-if="transcript.is_premium" color="warning" variant="subtle">Premium</UBadge>
        </div>
        <div class="text-xs text-gray-400">{{ formatDate(transcript.created_at) }}</div>
      </div>

      <!-- Locked / Paywall -->
      <UAlert
        v-if="transcript.is_locked"
        color="warning"
        icon="i-heroicons-lock-closed"
        title="Premium Content"
        description="Subscribe to read the full transcript. Preview shown below."
      >
        <template #actions>
          <NuxtLink to="/pricing">
            <UButton size="sm" color="warning">Subscribe</UButton>
          </NuxtLink>
        </template>
      </UAlert>

      <!-- Search & Content -->
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
                    v-if="hasSearch"
                    variant="ghost"
                    size="sm"
                    @click="clearSearch"
                  >
                    Clear
                  </UButton>
                </div>
              </div>
              <UInput
                v-model="searchInput"
                placeholder="Search in transcript..."
                icon="i-heroicons-magnifying-glass"
              />
            </div>
          </template>
          <div class="whitespace-pre-wrap text-sm leading-relaxed">
            <div
              v-if="hasHighlights"
              v-html="transcript.transcript"
            />
            <div v-else>{{ transcript.transcript }}</div>
          </div>

          <!-- Truncation notice for locked transcripts -->
          <div v-if="transcript.is_locked" class="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700 text-center">
            <p class="text-gray-500 mb-3">Subscribe to view the full transcript</p>
            <NuxtLink to="/pricing">
              <UButton color="primary">View Plans</UButton>
            </NuxtLink>
          </div>
        </UCard>

        <!-- Speaker Frequency Sidebar -->
        <UCard v-if="speakerFrequencies.length > 0" class="h-fit lg:sticky lg:top-20">
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
