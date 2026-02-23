<script setup lang="ts">
definePageMeta({ layout: 'public' })

interface Segment {
  speaker: string
  speaker_raw: string
  resolved: boolean
  content: string
}

interface PublicTranscript {
  id: string
  name: string | null
  youtube_url: string | null
  upload_date: string | null
  created_at: string
  segments: Segment[]
  speaker_map: Record<string, string>
  speakers: string[]
  segment_counts: Record<string, number>
}

const route = useRoute()
const { session } = useAuth()
const { checkAndRecordRead, FREE_TIER_LIMIT } = useReads()

const { data: transcript, pending, error } = await useFetch<PublicTranscript>(
  `/api/public/transcripts/${route.params.id}`
)

// Read metering
const readStatus = ref<{ allowed: boolean; reads_this_month: number; limit: number } | null>(null)
const checkingGate = ref(true)

onMounted(async () => {
  readStatus.value = await checkAndRecordRead(route.params.id as string)
  checkingGate.value = false
})

const canRead = computed(() => readStatus.value?.allowed === true)
const showPaywall = computed(() => !checkingGate.value && readStatus.value !== null && !canRead.value)

// Speaker color palette
const SPEAKER_COLORS = [
  { bg: 'bg-indigo-100', text: 'text-indigo-800', dot: 'bg-indigo-500' },
  { bg: 'bg-emerald-100', text: 'text-emerald-800', dot: 'bg-emerald-500' },
  { bg: 'bg-amber-100', text: 'text-amber-800', dot: 'bg-amber-500' },
  { bg: 'bg-rose-100', text: 'text-rose-800', dot: 'bg-rose-500' },
  { bg: 'bg-violet-100', text: 'text-violet-800', dot: 'bg-violet-500' },
  { bg: 'bg-cyan-100', text: 'text-cyan-800', dot: 'bg-cyan-500' },
  { bg: 'bg-orange-100', text: 'text-orange-800', dot: 'bg-orange-500' },
  { bg: 'bg-teal-100', text: 'text-teal-800', dot: 'bg-teal-500' },
  { bg: 'bg-fuchsia-100', text: 'text-fuchsia-800', dot: 'bg-fuchsia-500' },
  { bg: 'bg-sky-100', text: 'text-sky-800', dot: 'bg-sky-500' },
]
const NEUTRAL_COLOR = { bg: 'bg-gray-100', text: 'text-gray-600', dot: 'bg-gray-400' }

const speakerColorMap = computed(() => {
  const map: Record<string, typeof SPEAKER_COLORS[0]> = {}
  transcript.value?.speakers.forEach((name, idx) => {
    map[name] = SPEAKER_COLORS[idx % SPEAKER_COLORS.length]
  })
  return map
})

function colorFor(segment: Segment) {
  if (!segment.resolved) return NEUTRAL_COLOR
  return speakerColorMap.value[segment.speaker] ?? NEUTRAL_COLOR
}

// Search
const searchQuery = ref('')
const debouncedSearch = ref('')
let debounceTimer: ReturnType<typeof setTimeout> | null = null
watch(searchQuery, (val) => {
  if (debounceTimer) clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    debouncedSearch.value = val
  }, 300)
})

const displaySegments = computed(() => {
  const segments = transcript.value?.segments ?? []
  const query = debouncedSearch.value.trim()
  if (!query) return segments
  const pattern = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i')
  return segments.filter(seg => pattern.test(seg.content) || pattern.test(seg.speaker))
})

const matchCount = computed(() => {
  const query = debouncedSearch.value.trim()
  if (!query) return null
  return displaySegments.value.length
})

function highlightContent(text: string): string {
  const query = debouncedSearch.value.trim()
  if (!query) return text
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  return text.replace(
    new RegExp(`(${escaped})`, 'gi'),
    '<mark class="bg-yellow-200 px-0.5 rounded">$1</mark>'
  )
}

// Speaker filter
const selectedSpeaker = ref<string | null>(null)

const filteredSegments = computed(() => {
  let segments = displaySegments.value
  if (selectedSpeaker.value) {
    segments = segments.filter(seg => seg.speaker === selectedSpeaker.value)
  }
  return segments
})

function toggleSpeaker(speaker: string) {
  selectedSpeaker.value = selectedSpeaker.value === speaker ? null : speaker
}

// Formatting
function formatUploadDate(dateStr: string) {
  const year = dateStr.slice(0, 4)
  const month = dateStr.slice(4, 6)
  const day = dateStr.slice(6, 8)
  return new Date(`${year}-${month}-${day}`).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric'
  })
}

function formatDate(dateString: string) {
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    year: 'numeric'
  })
}

// Copy
const copied = ref(false)
async function copyTranscript() {
  if (!transcript.value) return
  const text = transcript.value.segments
    .map(s => `${s.speaker}:\n${s.content}`)
    .join('\n\n')
  await navigator.clipboard.writeText(text)
  copied.value = true
  setTimeout(() => { copied.value = false }, 2000)
}

// Page title
useHead({
  title: computed(() => transcript.value?.name || 'Transcript')
})

useServerSeoMeta({
  robots: 'noindex, nofollow',
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Loading -->
    <div v-if="pending && !transcript" class="flex justify-center py-20">
      <UIcon name="i-heroicons-arrow-path" class="size-8 animate-spin text-gray-400" />
    </div>

    <!-- Error -->
    <div v-else-if="error || !transcript" class="flex flex-col items-center py-20 text-center">
      <UIcon name="i-heroicons-document-magnifying-glass" class="size-12 text-gray-300 mb-4" />
      <h1 class="text-xl font-semibold text-gray-700 mb-2">Transcript not found</h1>
      <p class="text-sm text-gray-500">This transcript may have been removed or the link is invalid.</p>
    </div>

    <!-- Paywall -->
    <div v-else-if="showPaywall" class="flex flex-col items-center py-20 text-center max-w-md mx-auto">
      <UIcon name="i-heroicons-lock-closed" class="size-12 text-gray-300 mb-4" />

      <template v-if="!session">
        <h2 class="text-xl font-semibold text-gray-700 mb-2">Sign in to read</h2>
        <p class="text-sm text-gray-500 mb-6">
          Create a free account to read up to {{ FREE_TIER_LIMIT }} transcripts per month.
        </p>
        <div class="flex gap-3">
          <NuxtLink to="/signup">
            <UButton>Sign up free</UButton>
          </NuxtLink>
          <NuxtLink to="/login">
            <UButton variant="outline">Sign in</UButton>
          </NuxtLink>
        </div>
      </template>

      <template v-else>
        <h2 class="text-xl font-semibold text-gray-700 mb-2">Monthly limit reached</h2>
        <p class="text-sm text-gray-500 mb-2">
          You've read {{ readStatus?.reads_this_month }} of {{ readStatus?.limit }} free transcripts this month.
        </p>
        <p class="text-sm text-gray-400">
          Upgrade your plan to continue reading.
        </p>
      </template>
    </div>

    <!-- Checking gate -->
    <div v-else-if="checkingGate" class="flex justify-center py-20">
      <UIcon name="i-heroicons-arrow-path" class="size-8 animate-spin text-gray-400" />
    </div>

    <!-- Content (allowed) -->
    <template v-else-if="canRead">
      <!-- Header -->
      <div class="mb-8">
        <h1 class="text-2xl font-bold text-gray-900 mb-2">
          {{ transcript.name || 'Untitled Transcript' }}
        </h1>
        <div class="flex flex-wrap items-center gap-3 text-sm text-gray-500">
          <span v-if="transcript.upload_date">
            {{ formatUploadDate(transcript.upload_date) }}
          </span>
          <span v-else>
            {{ formatDate(transcript.created_at) }}
          </span>
          <a
            v-if="transcript.youtube_url"
            :href="transcript.youtube_url"
            target="_blank"
            rel="noopener"
            class="inline-flex items-center gap-1 text-primary hover:underline"
          >
            <UIcon name="i-heroicons-play-circle" class="size-4" />
            Watch on YouTube
          </a>
          <UButton
            variant="ghost"
            size="xs"
            :icon="copied ? 'i-heroicons-check' : 'i-heroicons-clipboard-document'"
            @click="copyTranscript"
          >
            {{ copied ? 'Copied' : 'Copy' }}
          </UButton>
          <span v-if="readStatus" class="text-xs text-gray-400">
            {{ readStatus.reads_this_month }}/{{ readStatus.limit }} reads this month
          </span>
        </div>
      </div>

      <!-- Two-column layout -->
      <div class="flex flex-col lg:flex-row gap-6">
        <!-- Main transcript -->
        <div class="flex-1 min-w-0">
          <UCard>
            <div v-if="filteredSegments.length === 0" class="text-center py-8 text-gray-400">
              <template v-if="debouncedSearch.trim()">
                No segments match "{{ debouncedSearch }}"
              </template>
              <template v-else>
                No transcript content available.
              </template>
            </div>

            <div v-else class="space-y-1">
              <template v-for="(seg, idx) in filteredSegments" :key="idx">
                <!-- Speaker label: show when speaker changes -->
                <div
                  v-if="idx === 0 || seg.speaker !== filteredSegments[idx - 1]!.speaker"
                  class="flex items-center gap-2 pt-5 first:pt-0 pb-1"
                >
                  <span
                    :class="[colorFor(seg).bg, colorFor(seg).text, 'px-2 py-0.5 text-xs font-semibold rounded']"
                  >
                    {{ seg.speaker }}
                  </span>
                </div>

                <!-- Content -->
                <p
                  class="text-sm leading-relaxed text-gray-800 pl-2"
                  v-html="highlightContent(seg.content)"
                />
              </template>
            </div>
          </UCard>
        </div>

        <!-- Sidebar -->
        <div class="w-full lg:w-64 shrink-0">
          <div class="lg:sticky lg:top-4 space-y-4">
            <!-- Search -->
            <UCard>
              <div class="space-y-3">
                <UInput
                  v-model="searchQuery"
                  placeholder="Search transcript..."
                  icon="i-heroicons-magnifying-glass"
                  size="sm"
                />
                <div v-if="matchCount !== null" class="text-xs text-gray-500">
                  {{ matchCount }} segment{{ matchCount !== 1 ? 's' : '' }} found
                </div>
              </div>
            </UCard>

            <!-- Speaker legend -->
            <UCard>
              <template #header>
                <div class="flex items-center justify-between">
                  <h3 class="text-sm font-semibold text-gray-700">Speakers</h3>
                  <UButton
                    v-if="selectedSpeaker"
                    variant="ghost"
                    size="xs"
                    @click="selectedSpeaker = null"
                  >
                    Clear
                  </UButton>
                </div>
              </template>
              <div class="space-y-1">
                <button
                  v-for="speaker in transcript.speakers"
                  :key="speaker"
                  class="flex items-center gap-2 w-full py-1.5 px-1 rounded text-left transition-colors"
                  :class="[
                    selectedSpeaker === speaker
                      ? 'bg-gray-100'
                      : 'hover:bg-gray-50',
                    selectedSpeaker && selectedSpeaker !== speaker ? 'opacity-40' : ''
                  ]"
                  @click="toggleSpeaker(speaker)"
                >
                  <span
                    :class="[speakerColorMap[speaker]?.dot ?? NEUTRAL_COLOR.dot, 'size-2 rounded-full shrink-0']"
                  />
                  <span class="text-sm truncate flex-1 text-gray-700">{{ speaker }}</span>
                  <span class="text-xs text-gray-400 font-mono shrink-0">
                    {{ transcript.segment_counts[speaker] }}
                  </span>
                </button>
              </div>
            </UCard>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
