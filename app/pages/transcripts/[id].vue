<script setup lang="ts">
const route = useRoute()
const transcriptId = route.params.id as string
const { publicFetch } = usePublicApi()

interface SpeakerFrequency {
  speaker: string
  count: number
}

interface PersonaInfo {
  name: string
  slug: string
  image_url: string | null
}

interface TranscriptNeighbor {
  id: string
  name: string | null
}

interface TranscriptDetail {
  id: string
  youtube_url: string | null
  upload_date: string | null
  transcript: string
  name: string | null
  created_at: string
  hasHighlights?: boolean
  matchCount?: number
  speakerFrequencies?: SpeakerFrequency[]
  persona?: PersonaInfo
}

interface Segment {
  speaker: string
  content: string
  timestamp?: string
}

useSeoMeta({
  title: () => transcript.value?.name || 'Transcript',
  description: () => {
    const date = transcript.value?.upload_date
    return date ? `Press briefing transcript from ${formatUploadDate(date)}` : 'Press briefing transcript'
  },
  ogTitle: () => transcript.value?.name || 'Transcript',
  ogDescription: () => 'Press briefing transcript on MentionsHero',
  robots: 'noindex, nofollow',
})

defineOgImage({ component: 'OgImageDefault', alt: () => transcript.value?.name || 'Transcript' })

// Structured data (page stays noindex - added for consistency)
useSchemaOrg([
  defineWebPage({
    name: () => transcript.value?.name || 'Transcript',
  }),
  defineBreadcrumb({
    itemListElement: [
      { name: 'Transcripts', item: '/' },
      {
        name: () => transcript.value?.persona?.name || 'Transcripts',
        item: () => transcript.value?.persona?.slug
          ? `/personas/${transcript.value.persona.slug}`
          : '/',
      },
      { name: () => transcript.value?.name || 'Transcript' },
    ],
  }),
])

const transcript = ref<TranscriptDetail | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)

// Pre-fill search from URL query param (e.g. from keyword search links)
const initialSearch = (route.query.search as string) || ''
const searchInput = ref(initialSearch)
const debouncedSearch = ref(initialSearch)

// Next/prev navigation
const prevTranscript = ref<TranscriptNeighbor | null>(null)
const nextTranscript = ref<TranscriptNeighbor | null>(null)

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

    // Fetch next/prev neighbors if persona is known
    if (transcript.value?.persona?.slug) {
      loadNeighbors(transcript.value.persona.slug)
    }
  } catch (e: unknown) {
    const detail = (e as { data?: { detail?: string } })?.data?.detail
    error.value = detail || 'We could not load that transcript'
  } finally {
    loading.value = false
  }
}

async function loadNeighbors(personaSlug: string) {
  try {
    const result = await publicFetch<{ prev: TranscriptNeighbor | null; next: TranscriptNeighbor | null }>(
      `/api/public/transcripts/${transcriptId}/neighbors?persona=${encodeURIComponent(personaSlug)}`
    )
    prevTranscript.value = result.prev
    nextTranscript.value = result.next
  } catch {
    // Non-critical, ignore
  }
}

watch(searchQuery, () => refresh())
onMounted(() => refresh())

/** First load: nothing on screen yet. Re-fetch: the transcript is still there. */
const initialLoading = computed(() => loading.value && !transcript.value)
/** A search round-trip while the previous result is still rendered. */
const refreshing = computed(() => loading.value && !!transcript.value)

const showTimestamps = ref(true)
const inlineTimestampPattern = /\[\d{1,3}:\d{2}\]\s*/g
function stripInlineTimestamps(text: string): string {
  return text.replace(inlineTimestampPattern, '')
}
const hasHighlights = computed(() => transcript.value?.hasHighlights || false)
const matchCount = computed(() => transcript.value?.matchCount ?? null)
const speakerFrequencies = computed(() => transcript.value?.speakerFrequencies || [])
const hasSearch = computed(() => searchInput.value.trim().length > 0)
const noMatches = computed(() =>
  !loading.value && debouncedSearch.value.trim().length > 0 && matchCount.value === 0
)

const totalSearchMatches = computed(() => {
  return speakerFrequencies.value.reduce((sum, f) => sum + f.count, 0)
})

/**
 * One parser, two dialects.
 *
 * Plain text arrives when no search is active. When the API highlights a term
 * it returns HTML instead, and the speaker name comes back HTML-escaped — so
 * the speaker class has to allow `&#;` and the name can run longer. Everything
 * else about the two passes was identical, so only the pattern differs.
 */
const PLAIN_SPEAKER_PATTERN = /^(?:\[(\d{1,3}:\d{2})\]\s+)?([A-Z0-9][\w\s\-'._()]{1,60}?):\s*(.*)$/
const HTML_SPEAKER_PATTERN = /^(?:\[(\d{1,3}:\d{2})\]\s+)?([A-Z0-9][\w\s\-&#;'._()]{1,80}?):\s*(.*)$/

function parseSegments(text: string, pattern: RegExp): Segment[] {
  const lines = text.split('\n')
  const result: Segment[] = []
  let currentSpeaker: string | null = null
  let currentTimestamp: string | undefined = undefined
  let currentContent: string[] = []

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    const match = trimmed.match(pattern)
    if (match) {
      if (currentSpeaker && currentContent.length) {
        result.push({ speaker: currentSpeaker, content: currentContent.join(' '), timestamp: currentTimestamp })
      }
      currentTimestamp = match[1] || undefined
      currentSpeaker = match[2] ?? null
      currentContent = match[3] ? [match[3]] : []
    } else if (currentSpeaker) {
      currentContent.push(trimmed)
    }
  }
  if (currentSpeaker && currentContent.length) {
    result.push({ speaker: currentSpeaker, content: currentContent.join(' '), timestamp: currentTimestamp })
  }
  return result
}

const displaySegments = computed<Segment[]>(() => {
  if (!transcript.value) return []
  return parseSegments(
    transcript.value.transcript,
    hasHighlights.value ? HTML_SPEAKER_PATTERN : PLAIN_SPEAKER_PATTERN
  )
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

// A shorter result set must never strand the reader on a page that no longer exists.
watch(totalPages, (pages) => {
  if (currentPage.value > pages) currentPage.value = Math.max(1, pages)
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

const breadcrumbItems = computed(() => {
  const items: Array<{ label: string, to?: string }> = [{ label: 'Transcripts', to: '/' }]
  const persona = transcript.value?.persona
  if (persona) {
    items.push(persona.slug
      ? { label: persona.name, to: `/personas/${persona.slug}` }
      : { label: persona.name })
  }
  items.push({ label: transcript.value?.name || 'Transcript' })
  return items
})
</script>

<template>
  <div class="pb-16">
    <!-- Loading: this is a reading surface, so the skeleton is prose lines. -->
    <UiLoadingBlock v-if="initialLoading" variant="text" :count="8" label="Loading transcript" class="pt-10" />

    <!-- Error -->
    <UiNotFoundState
      v-else-if="error && !transcript"
      :title="error"
      description="The transcript may have been removed, or the address may be wrong. Every published briefing is listed on the transcripts page."
      back-label="Back to transcripts"
      back-to="/"
    />

    <template v-if="transcript">
      <!-- ── Header ─────────────────────────────────────────────────────── -->
      <header class="pt-6 pb-8">
        <UBreadcrumb
          :items="breadcrumbItems"
          class="mb-4"
          :ui="{
            list: 'flex-wrap gap-y-1',
            link: 'min-w-0 text-sm',
            linkLabel: 'truncate max-w-[14rem] sm:max-w-xs'
          }"
        />

        <h1 class="type-title measure-wide text-highlighted">{{ transcript.name || 'Transcript' }}</h1>

        <div class="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2">
          <span class="inline-flex items-center gap-2 text-dimmed">
            <UIcon name="i-lucide-calendar" class="size-4 shrink-0" aria-hidden="true" />
            <span class="type-figure text-sm text-toned">
              {{ formatUploadDate(transcript.upload_date) || formatDate(transcript.created_at) }}
            </span>
          </span>

          <ULink
            v-if="transcript.persona?.slug"
            :to="`/personas/${transcript.persona.slug}`"
            class="inline-flex items-center gap-2 text-sm text-toned transition-colors hover:text-highlighted"
          >
            <UiPersonaAvatar
              :name="transcript.persona.name"
              :src="transcript.persona.image_url"
              size="xs"
              decorative
            />
            <span>{{ transcript.persona.name }}</span>
          </ULink>

          <ULink
            v-if="transcript.youtube_url"
            :to="transcript.youtube_url"
            target="_blank"
            rel="noopener noreferrer"
            class="inline-flex items-center gap-1.5 text-sm text-toned transition-colors hover:text-highlighted"
          >
            <UIcon name="i-lucide-circle-play" class="size-4 shrink-0" aria-hidden="true" />
            <span>Watch on YouTube</span>
            <UIcon name="i-lucide-external-link" class="size-3 shrink-0" aria-hidden="true" />
          </ULink>
        </div>
      </header>

      <!-- ── Sticky search bar ──────────────────────────────────────────── -->
      <div
        class="sticky top-(--ui-header-height) z-10 border-b border-default bg-default/95 py-3 backdrop-blur-sm"
      >
        <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-4">
          <UInput
            v-model="searchInput"
            aria-label="Search this transcript"
            placeholder="Search this transcript…"
            icon="i-lucide-search"
            size="md"
            :loading="refreshing"
            class="w-full sm:flex-1"
            :ui="{ base: 'font-mono' }"
          />

          <div class="flex items-center justify-between gap-3 sm:justify-start">
            <div class="flex min-w-0 items-center gap-2">
              <UiLoadingBlock v-if="refreshing" variant="inline" label="Searching transcript" />
              <UBadge
                v-else-if="matchCount !== null && matchCount > 0"
                color="secondary"
                variant="subtle"
                size="sm"
                class="shrink-0 whitespace-nowrap"
              >
                <span class="type-figure">{{ matchCount }}</span>
                <span class="ml-1">match{{ matchCount !== 1 ? 'es' : '' }}</span>
              </UBadge>
              <UButton
                v-if="hasSearch"
                variant="ghost"
                color="neutral"
                size="xs"
                icon="i-lucide-x"
                aria-label="Clear the search"
                @click="clearSearch"
              />
            </div>

            <USwitch v-model="showTimestamps" label="Timestamps" class="shrink-0" />
          </div>
        </div>
      </div>

      <p v-if="noMatches" class="pt-3 text-sm text-muted">
        Nothing in this briefing matches
        <span class="type-figure text-toned">&ldquo;{{ debouncedSearch.trim() }}&rdquo;</span>.
        Try a shorter word, or drop the plural.
      </p>

      <!-- ── Body + speaker rail ────────────────────────────────────────── -->
      <div
        :class="speakerFrequencies.length > 0
          ? 'mt-8 grid grid-cols-1 gap-10 lg:grid-cols-[minmax(0,1fr)_16rem]'
          : 'mt-8'"
      >
        <!-- Transcript -->
        <div class="relative min-w-0" :aria-busy="refreshing">
          <div
            class="transcript-body transition-opacity duration-200"
            :class="refreshing ? 'opacity-50' : 'opacity-100'"
          >
            <!-- Segments. Speaker and timestamp hang in the margin at sm+. -->
            <div v-if="displaySegments.length > 0" class="divide-y divide-dotted divide-default">
              <article
                v-for="(seg, idx) in paginatedSegments"
                :key="(currentPage - 1) * pageSize + idx"
                class="grid gap-x-6 gap-y-1.5 py-5 first:pt-0 sm:grid-cols-[8.5rem_minmax(0,1fr)]"
              >
                <div
                  class="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 sm:flex-col sm:items-end sm:text-right"
                >
                  <span
                    v-if="showTimestamps && seg.timestamp"
                    class="type-figure text-xs text-dimmed"
                  >{{ seg.timestamp }}</span>
                  <span class="type-label wrap-break-word text-toned">
                    <span v-if="hasHighlights" v-html="seg.speaker" />
                    <template v-else>{{ seg.speaker }}</template>
                  </span>
                </div>

                <p
                  v-if="hasHighlights"
                  class="measure text-base leading-[1.75] text-default"
                  v-html="showTimestamps ? seg.content : stripInlineTimestamps(seg.content)"
                />
                <p
                  v-else
                  class="measure text-base leading-[1.75] text-default"
                >{{ showTimestamps ? seg.content : stripInlineTimestamps(seg.content) }}</p>
              </article>
            </div>

            <!-- Fallback: raw text when the speaker pattern matched nothing. -->
            <div
              v-else
              class="measure-wide wrap-break-word text-base leading-[1.75] whitespace-pre-wrap text-default"
            >
              <div v-if="hasHighlights" v-html="transcript.transcript" />
              <div v-else>{{ transcript.transcript }}</div>
            </div>
          </div>

          <!-- Pagination -->
          <nav
            v-if="displaySegments.length > 0 && totalPages > 1"
            class="mt-8 flex flex-col gap-3 border-t border-default pt-6 sm:flex-row sm:items-center sm:justify-between"
            aria-label="Transcript pages"
          >
            <span class="type-label text-dimmed">
              Page {{ currentPage }} of {{ totalPages }}
            </span>
            <div class="flex flex-wrap items-center justify-start gap-1 sm:justify-end">
              <UButton
                variant="outline"
                color="neutral"
                size="sm"
                icon="i-lucide-chevron-left"
                aria-label="Previous page"
                :disabled="currentPage === 1"
                @click="goToPage(currentPage - 1)"
              />
              <template v-for="p in totalPages" :key="p">
                <UButton
                  v-if="p === 1 || p === totalPages || (p >= currentPage - 1 && p <= currentPage + 1)"
                  :variant="p === currentPage ? 'solid' : 'outline'"
                  :color="p === currentPage ? 'primary' : 'neutral'"
                  size="sm"
                  :aria-label="`Page ${p}`"
                  :aria-current="p === currentPage ? 'page' : undefined"
                  class="type-figure"
                  @click="goToPage(p)"
                >
                  {{ p }}
                </UButton>
                <span
                  v-else-if="p === currentPage - 2 || p === currentPage + 2"
                  class="px-1 text-dimmed"
                  aria-hidden="true"
                >…</span>
              </template>
              <UButton
                variant="outline"
                color="neutral"
                size="sm"
                icon="i-lucide-chevron-right"
                aria-label="Next page"
                :disabled="currentPage === totalPages"
                @click="goToPage(currentPage + 1)"
              />
            </div>
          </nav>

          <!-- Prev / next briefing -->
          <nav
            v-if="prevTranscript || nextTranscript"
            class="mt-10 grid gap-3 border-t border-default pt-6 sm:grid-cols-2"
            aria-label="Nearby briefings"
          >
            <ULink
              v-if="prevTranscript"
              :to="`/transcripts/${prevTranscript.id}`"
              class="flex min-w-0 items-center gap-2 text-toned transition-colors hover:text-highlighted"
            >
              <UIcon name="i-lucide-arrow-left" class="size-4 shrink-0" aria-hidden="true" />
              <span class="min-w-0">
                <span class="type-label block text-dimmed">Earlier</span>
                <span class="block truncate text-sm">{{ prevTranscript.name || 'Previous briefing' }}</span>
              </span>
            </ULink>
            <div v-else class="hidden sm:block" />
            <ULink
              v-if="nextTranscript"
              :to="`/transcripts/${nextTranscript.id}`"
              class="flex min-w-0 items-center justify-start gap-2 text-toned transition-colors hover:text-highlighted sm:justify-end sm:text-right"
            >
              <span class="min-w-0">
                <span class="type-label block text-dimmed">Later</span>
                <span class="block truncate text-sm">{{ nextTranscript.name || 'Next briefing' }}</span>
              </span>
              <UIcon name="i-lucide-arrow-right" class="size-4 shrink-0" aria-hidden="true" />
            </ULink>
          </nav>
        </div>

        <!-- Speaker frequency: one tally rail per speaker. -->
        <aside
          v-if="speakerFrequencies.length > 0"
          class="h-fit lg:sticky lg:top-[calc(var(--ui-header-height)+4.5rem)]"
          aria-label="Mentions by speaker"
        >
          <UCard :ui="{ body: 'p-4 sm:p-4' }">
            <div class="flex items-center gap-2">
              <UIcon name="i-lucide-tally-5" class="size-4 shrink-0 text-mark-600 dark:text-mark-400" aria-hidden="true" />
              <h2 class="type-label text-dimmed">Who said it</h2>
            </div>

            <UiStatRow
              label="Total"
              :value="totalSearchMatches"
              tone="mark"
              size="sm"
              divided
              class="mt-3"
            />

            <ul class="mt-4 space-y-3.5">
              <li v-for="freq in speakerFrequencies" :key="freq.speaker" class="space-y-1.5">
                <div class="flex items-baseline justify-between gap-2">
                  <span class="type-label min-w-0 truncate text-toned">{{ freq.speaker }}</span>
                  <span class="type-figure shrink-0 text-sm text-mark-600 dark:text-mark-400">{{ freq.count }}</span>
                </div>
              </li>
            </ul>
          </UCard>
        </aside>
      </div>
    </template>
  </div>
</template>

<style scoped>
/*
 * The API hands back highlight markup carrying a legacy yellow utility class on
 * every <mark>. Tailwind does not emit that utility for this build (the class
 * string lives only in the Python source it is generated from), so the global
 * `mark` rule already paints the amber wash. But the moment any source file in
 * this repo makes Tailwind emit that legacy utility, it would outrank the base
 * layer and every search hit here would turn lemon. This unlayered rule pins the
 * mark to the brand amber whatever else ends up in the stylesheet.
 * (The class names are deliberately not written out here: Tailwind scans this
 * file, and naming them would generate the very utility we are guarding against.)
 */
.transcript-body :deep(mark) {
  background-color: color-mix(in oklab, var(--color-mark-500) 32%, transparent);
  color: inherit;
  border-radius: 0.125rem;
  padding-inline: 0.15em;
  box-decoration-break: clone;
  -webkit-box-decoration-break: clone;
}
</style>
