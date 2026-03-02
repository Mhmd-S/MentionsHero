<script setup lang="ts">
const route = useRoute()
const transcriptId = route.params.id as string
const { publicFetch } = usePublicApi()

interface SpeakerFrequency {
  speaker: string
  count: number
}

interface TranscriptDetail {
  id: string
  youtube_url: string | null
  upload_date: string | null
  transcript: string
  name: string | null
  created_at: string
  is_premium: boolean
  is_locked: boolean
  hasHighlights?: boolean
  matchCount?: number
  speakerFrequencies?: SpeakerFrequency[]
}

interface Segment {
  speaker: string
  content: string
}

useSeoMeta({
  title: () => transcript.value?.name || 'Transcript',
  description: () => {
    const date = transcript.value?.upload_date
    return date ? `Press briefing transcript from ${formatUploadDate(date)}` : 'Press briefing transcript'
  },
  ogTitle: () => transcript.value?.name || 'Transcript',
  ogDescription: () => 'Press briefing transcript on MentionsHero',
  twitterCard: 'summary',
  robots: 'noindex, nofollow',
})

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

const maxFrequency = computed(() => {
  if (speakerFrequencies.value.length === 0) return 0
  return Math.max(...speakerFrequencies.value.map(f => f.count))
})

const totalSearchMatches = computed(() => {
  return speakerFrequencies.value.reduce((sum, f) => sum + f.count, 0)
})

// Parse transcript text into speaker segments
const speakerPattern = /^([A-Z0-9][\w\s\-'._()]{1,60}?):\s*(.*)$/

function parseSegments(text: string): Segment[] {
  const lines = text.split('\n')
  const result: Segment[] = []
  let currentSpeaker: string | null = null
  let currentContent: string[] = []

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const match = trimmed.match(speakerPattern)
    if (match) {
      if (currentSpeaker && currentContent.length) {
        result.push({ speaker: currentSpeaker, content: currentContent.join(' ') })
      }
      currentSpeaker = match[1] ?? null
      currentContent = match[2] ? [match[2]] : []
    } else if (currentSpeaker) {
      currentContent.push(trimmed)
    }
  }
  if (currentSpeaker && currentContent.length) {
    result.push({ speaker: currentSpeaker, content: currentContent.join(' ') })
  }
  return result
}

const segments = computed(() => {
  if (!transcript.value) return []
  return parseSegments(transcript.value.transcript)
})

// For highlighted mode, parse into segments preserving HTML
const highlightedSegments = computed(() => {
  if (!transcript.value || !hasHighlights.value) return []
  const text = transcript.value.transcript
  const lines = text.split('\n')
  const result: Segment[] = []
  let currentSpeaker: string | null = null
  let currentContent: string[] = []

  // In highlighted mode, speaker names are HTML-escaped but follow the same pattern
  const htmlSpeakerPattern = /^([A-Z0-9][\w\s\-&#;'._()]{1,80}?):\s*(.*)$/

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const match = trimmed.match(htmlSpeakerPattern)
    if (match) {
      if (currentSpeaker && currentContent.length) {
        result.push({ speaker: currentSpeaker, content: currentContent.join(' ') })
      }
      currentSpeaker = match[1] ?? null
      currentContent = match[2] ? [match[2]] : []
    } else if (currentSpeaker) {
      currentContent.push(trimmed)
    }
  }
  if (currentSpeaker && currentContent.length) {
    result.push({ speaker: currentSpeaker, content: currentContent.join(' ') })
  }
  return result
})

const displaySegments = computed(() => {
  return hasHighlights.value ? highlightedSegments.value : segments.value
})

// Pagination
const pageSize = 50
const currentPage = ref(1)

const totalPages = computed(() => Math.ceil(displaySegments.value.length / pageSize))

const paginatedSegments = computed(() => {
  const start = (currentPage.value - 1) * pageSize
  return displaySegments.value.slice(start, start + pageSize)
})

// Reset to page 1 when search changes
watch(debouncedSearch, () => {
  currentPage.value = 1
})

function goToPage(p: number) {
  currentPage.value = p
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

function clearSearch() {
  searchInput.value = ''
  debouncedSearch.value = ''
}

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function formatUploadDate(yyyymmdd: string | null | undefined): string | null {
  if (!yyyymmdd || yyyymmdd.length !== 8) return null
  const year = yyyymmdd.slice(0, 4)
  const month = yyyymmdd.slice(4, 6)
  const day = yyyymmdd.slice(6, 8)
  return new Date(`${year}-${month}-${day}`).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric',
  })
}
</script>

<template>
  <div class="max-w-5xl mx-auto">
    <!-- Loading -->
    <div v-if="loading && !transcript" class="flex justify-center py-20">
      <UIcon name="i-lucide-loader" class="size-6 animate-spin text-muted" />
    </div>

    <!-- Error -->
    <div v-else-if="error && !transcript" class="py-16 text-center">
      <UIcon name="i-lucide-alert-triangle" class="size-10 mx-auto mb-4 opacity-40 text-muted" />
      <p class="text-muted font-medium">{{ error }}</p>
      <NuxtLink to="/">
        <UButton variant="outline" size="sm" class="mt-4">Back to Browse</UButton>
      </NuxtLink>
    </div>

    <template v-if="transcript">
      <!-- Header -->
      <div class="py-6">
        <NuxtLink to="/" class="inline-flex items-center gap-1.5 text-sm text-muted hover:text-primary transition-colors mb-3">
          <UIcon name="i-lucide-arrow-left" class="size-4" />
          All Personas
        </NuxtLink>
        <h1 class="text-xl font-semibold">{{ transcript.name || 'Transcript' }}</h1>
        <div class="flex flex-wrap items-center gap-3 mt-2">
          <span class="inline-flex items-center gap-1.5 text-sm text-muted">
            <UIcon name="i-lucide-calendar" class="size-4" />
            {{ formatUploadDate(transcript.upload_date) || formatDate(transcript.created_at) }}
          </span>
          <a
            v-if="transcript.youtube_url"
            :href="transcript.youtube_url"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1.5 text-sm text-muted hover:text-primary transition-colors"
          >
            <UIcon name="i-lucide-play-circle" class="size-4" />
            <span>YouTube</span>
            <UIcon name="i-lucide-external-link" class="size-3" />
          </a>
          <UBadge v-if="transcript.is_premium" color="warning" variant="subtle" size="sm">Premium</UBadge>
        </div>
      </div>

      <!-- Sticky Search Bar (hidden for locked transcripts) -->
      <div v-if="!transcript.is_locked" class="sticky top-(--ui-header-height) z-10 bg-background/95 backdrop-blur-sm py-3">
        <div class="flex items-center gap-3">
          <UInput
            v-model="searchInput"
            placeholder="Search transcript..."
            icon="i-lucide-search"
            size="md"
            class="flex-1"
          />
          <UBadge
            v-if="matchCount !== null && matchCount > 0"
            color="primary"
            variant="subtle"
            class="whitespace-nowrap"
          >
            {{ matchCount }} match{{ matchCount !== 1 ? 'es' : '' }}
          </UBadge>
          <UButton
            v-if="hasSearch"
            variant="ghost"
            color="neutral"
            size="xs"
            icon="i-lucide-x"
            @click="clearSearch"
          />
        </div>
      </div>

      <!-- Content & Speaker Frequency -->
      <div :class="speakerFrequencies.length > 0 ? 'grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-8 mt-6' : 'mt-6'">
        <!-- Transcript Body -->
        <div class="relative">
          <!-- Segmented display -->
          <div v-if="displaySegments.length > 0" class="space-y-5">
            <div
              v-for="(seg, idx) in paginatedSegments"
              :key="(currentPage - 1) * pageSize + idx"
              class="border-l-2 border-primary/30 pl-4"
            >
              <div class="text-md underline font-semibold tracking-wide uppercase text-primary mb-1">
                {{ hasHighlights ? '' : seg.speaker }}
                <span v-if="hasHighlights" v-html="seg.speaker" />
              </div>
              <p
                v-if="hasHighlights"
                class="text-[0.9375rem] leading-7 text-dimmed"
                v-html="seg.content"
              />
              <p
                v-else
                class="text-[0.9375rem] leading-7"
              >{{ seg.content }}</p>
            </div>

            <!-- Pagination controls (hidden for locked transcripts) -->
            <div v-if="totalPages > 1 && !transcript.is_locked" class="flex items-center justify-between pt-6 border-t border-muted">
              <span class="text-sm text-muted">
                Page {{ currentPage }} of {{ totalPages }}
              </span>
              <div class="flex items-center gap-1">
                <UButton
                  variant="outline"
                  size="sm"
                  icon="i-lucide-chevron-left"
                  :disabled="currentPage === 1"
                  @click="goToPage(currentPage - 1)"
                />
                <template v-for="p in totalPages" :key="p">
                  <UButton
                    v-if="p === 1 || p === totalPages || (p >= currentPage - 1 && p <= currentPage + 1)"
                    :variant="p === currentPage ? 'solid' : 'outline'"
                    size="sm"
                    @click="goToPage(p)"
                  >
                    {{ p }}
                  </UButton>
                  <span
                    v-else-if="p === currentPage - 2 || p === currentPage + 2"
                    class="text-muted px-1"
                  >...</span>
                </template>
                <UButton
                  variant="outline"
                  size="sm"
                  icon="i-lucide-chevron-right"
                  :disabled="currentPage === totalPages"
                  @click="goToPage(currentPage + 1)"
                />
              </div>
            </div>
          </div>

          <!-- Fallback: raw text if parsing yielded no segments -->
          <div v-else class="whitespace-pre-wrap wrap-break-word text-[0.9375rem] leading-7 text-dimmed">
            <div v-if="hasHighlights" v-html="transcript.transcript" />
            <div v-else>{{ transcript.transcript }}</div>
          </div>

          <!-- Locked transcript fade-out and CTA -->
          <div v-if="transcript.is_locked" class="relative mt-0">
            <div class="absolute -top-32 left-0 right-0 h-32 bg-linear-to-t from-background to-transparent pointer-events-none" />
            <div class="pt-10 pb-6 text-center">
              <div class="inline-flex items-center justify-center size-14 rounded-full bg-elevated mb-4">
                <UIcon name="i-lucide-lock" class="size-7 text-muted" />
              </div>
              <p class="font-semibold text-lg mb-1">Full transcript requires a subscription</p>
              <p class="text-sm text-muted mb-5">Get unlimited access to all premium transcripts</p>
              <NuxtLink to="/pricing">
                <UButton color="primary" size="lg">Subscribe to Read</UButton>
              </NuxtLink>
            </div>
          </div>
        </div>

        <!-- Speaker Frequency Sidebar -->
        <div v-if="speakerFrequencies.length > 0" class="h-fit lg:sticky lg:top-30">
          <UCard :ui="{ body: 'p-4 sm:p-4' }">
            <div class="flex items-center justify-between mb-4">
              <div class="flex items-center gap-2">
                <UIcon name="i-lucide-bar-chart-2" class="size-4 text-primary" />
                <h3 class="font-semibold text-sm">Frequency by Speaker</h3>
              </div>
              <span class="text-xs text-muted tabular-nums">{{ totalSearchMatches }} total</span>
            </div>
            <div class="space-y-3">
              <div
                v-for="freq in speakerFrequencies"
                :key="freq.speaker"
              >
                <div class="flex items-center justify-between mb-1.5">
                  <span class="text-sm font-medium truncate mr-2">{{ freq.speaker }}</span>
                  <span class="text-xs tabular-nums font-medium text-muted">{{ freq.count }}</span>
                </div>
                <div class="h-1.5 bg-elevated rounded-full overflow-hidden">
                  <div
                    class="h-full bg-primary rounded-full transition-all duration-300"
                    :style="{ width: `${maxFrequency > 0 ? (freq.count / maxFrequency) * 100 : 0}%` }"
                  />
                </div>
              </div>
            </div>
          </UCard>
        </div>
      </div>
    </template>
  </div>
</template>
