<script setup lang="ts">
const route = useRoute()
const slug = route.params.slug as string
const { publicFetch } = usePublicApi()
const { isSubscribed, fetchSubscription } = useSubscription()
const { session } = useAuth()

interface Persona {
  id: string
  name: string
  description: string | null
  meta_title: string | null
  meta_description: string | null
  slug: string | null
  image_url: string | null
  aliases: string[]
}

interface TranscriptSummary {
  id: string
  name: string | null
  created_at: string
  upload_date: string | null
  is_premium: boolean
  folder_id: string | null
  folder_name: string | null
  preview: string
}

interface PaginatedTranscripts {
  items: TranscriptSummary[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

const PAGE_SIZE = 20

// SSR-compatible fetch for persona data (critical for SEO meta tags)
const { data: persona, status: personaStatus } = await useFetch<Persona>(
  `/api/public/personas/${slug}`,
)
const loadingPersona = computed(() => personaStatus.value === 'pending')

const transcripts = ref<TranscriptSummary[]>([])
const loadingTranscripts = ref(false)
const transcriptsError = ref('')
const transcriptsLoaded = ref(false)
const search = ref('')
const sortBy = ref<'date' | 'name'>('date')
const sortOrder = ref<'desc' | 'asc'>('desc')
const page = ref(1)
const totalPages = ref(1)
const total = ref(0)

let searchTimer: ReturnType<typeof setTimeout> | null = null
const debouncedSearch = ref('')

watch(search, (val) => {
  if (searchTimer) clearTimeout(searchTimer)
  searchTimer = setTimeout(() => {
    debouncedSearch.value = val
    page.value = 1
  }, 400)
})

async function loadTranscripts() {
  if (!persona.value) return
  loadingTranscripts.value = true
  transcriptsError.value = ''
  try {
    const params = new URLSearchParams({
      sort_by: sortBy.value,
      sort_order: sortOrder.value,
      page: String(page.value),
      page_size: String(PAGE_SIZE),
    })
    if (debouncedSearch.value.trim()) {
      params.set('search', debouncedSearch.value.trim())
    }
    const result = await publicFetch<PaginatedTranscripts>(
      `/api/public/personas/${slug}/transcripts?${params}`
    )
    transcripts.value = result.items
    totalPages.value = result.total_pages
    total.value = result.total
    transcriptsLoaded.value = true
  } catch (err) {
    // A failed fetch used to fall through to the empty state, so a broken
    // request read as "this speaker has no transcripts". Say what happened.
    console.error('Failed to load transcripts:', err)
    transcripts.value = []
    totalPages.value = 1
    total.value = 0
    transcriptsError.value =
      err?.data?.detail || 'The transcript list did not load.'
  } finally {
    loadingTranscripts.value = false
  }
}

watch([debouncedSearch, sortBy, sortOrder, page], () => loadTranscripts())

function toggleSort(field: 'date' | 'name') {
  if (sortBy.value === field) {
    sortOrder.value = sortOrder.value === 'desc' ? 'asc' : 'desc'
  } else {
    sortBy.value = field
    sortOrder.value = field === 'date' ? 'desc' : 'asc'
  }
}

function clearTranscriptSearch() {
  search.value = ''
  debouncedSearch.value = ''
  page.value = 1
}

const filterEmptyHint = computed(() =>
  isSubscribed.value
    ? 'This filter matches the words inside a transcript, not just its title. Try a different word, or clear it.'
    : 'This filter matches the words inside a transcript. Premium transcripts are not searched on a free account.'
)

function sortLabel(field: 'date' | 'name') {
  const name = field === 'date' ? 'date' : 'name'
  if (sortBy.value !== field) return `Sort by ${name}`
  return sortOrder.value === 'desc'
    ? `Sorted by ${name}, newest first. Reverse the order.`
    : `Sorted by ${name}, oldest first. Reverse the order.`
}

const rangeStart = computed(() => (total.value === 0 ? 0 : (page.value - 1) * PAGE_SIZE + 1))
const rangeEnd = computed(() => Math.min(page.value * PAGE_SIZE, total.value))

function formatStamp(d: Date) {
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatDate(dateString: string | null, fallback?: string) {
  const str = dateString || fallback
  if (!str) return ''
  // YYYYMMDD (yt-dlp upload_date) and YYYY-MM-DD (keyword-search dates) are
  // calendar dates, not instants — build them locally so they never shift a day.
  if (/^\d{8}$/.test(str)) {
    return formatStamp(new Date(+str.slice(0, 4), +str.slice(4, 6) - 1, +str.slice(6)))
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(str)) {
    const [y, m, d] = str.split('-').map(Number)
    return formatStamp(new Date(y!, m! - 1, d!))
  }
  const parsed = new Date(str)
  return Number.isNaN(parsed.getTime()) ? '' : formatStamp(parsed)
}

// --- Keyword Search ---
interface KeywordMatch {
  transcript_id: string
  transcript_name: string
  date: string | null
  context: string
  position: number
  mention_count?: number
}

interface KeywordSearchResult {
  query: string
  total_matches: number
  transcripts_with_matches: number
  matches: KeywordMatch[]
  is_limited: boolean
}

const keywordQuery = ref('')
const keywordResults = ref<KeywordSearchResult | null>(null)
const keywordLoading = ref(false)
const keywordError = ref('')

let keywordTimer: ReturnType<typeof setTimeout> | null = null

async function searchKeywords() {
  const q = keywordQuery.value.trim()
  if (!q || q.length < 2) {
    keywordResults.value = null
    keywordError.value = ''
    return
  }
  keywordLoading.value = true
  keywordError.value = ''
  showAllGroups.value = false
  try {
    keywordResults.value = await publicFetch<KeywordSearchResult>(
      `/api/public/personas/${slug}/keyword-search?q=${encodeURIComponent(q)}`
    )
  } catch (err) {
    keywordError.value = (err as { data?: { detail?: string } })?.data?.detail || 'The search request did not complete.'
    keywordResults.value = null
  } finally {
    keywordLoading.value = false
  }
}

watch(keywordQuery, () => {
  if (keywordTimer) clearTimeout(keywordTimer)
  keywordTimer = setTimeout(() => searchKeywords(), 500)
})

// One card per transcript instead of one card per context window: the same
// matches, grouped, so a briefing's mentions read as one thing.
interface MatchGroup {
  transcriptId: string
  name: string
  date: string | null
  mentions: number
  snippets: string[]
}

const matchGroups = computed<MatchGroup[]>(() => {
  const res = keywordResults.value
  if (!res) return []
  const byTranscript = new Map<string, MatchGroup>()
  for (const m of res.matches) {
    let group = byTranscript.get(m.transcript_id)
    if (!group) {
      group = {
        transcriptId: m.transcript_id,
        name: m.transcript_name,
        date: m.date,
        mentions: 0,
        snippets: [],
      }
      byTranscript.set(m.transcript_id, group)
    }
    group.mentions += typeof m.mention_count === 'number' && m.mention_count > 0 ? m.mention_count : 1
    group.snippets.push(m.context)
  }
  return [...byTranscript.values()].sort((a, b) => (b.date || '').localeCompare(a.date || ''))
})

// The API caps matches at 100. When that cap bites, the per-transcript counts
// are a floor rather than a total, so no tally is drawn — a rail that under-counts
// is worse than no rail.
const countedMentions = computed(() => matchGroups.value.reduce((sum, g) => sum + g.mentions, 0))
const matchesComplete = computed(() => {
  const res = keywordResults.value
  if (!res) return false
  return !res.is_limited && countedMentions.value === res.total_matches
})

// Series mode: one tick per briefing that mentioned the term, oldest first.
const keywordSeries = computed<number[] | null>(() => {
  if (!matchesComplete.value) return null
  const groups = matchGroups.value
  if (groups.length < 2 || groups.some(g => !g.date)) return null
  return [...groups]
    .sort((a, b) => (a.date || '').localeCompare(b.date || ''))
    .map(g => g.mentions)
})

const SNIPPETS_PER_GROUP = 3
const GROUP_PREVIEW = 5
const showAllGroups = ref(false)
const visibleGroups = computed(() =>
  showAllGroups.value ? matchGroups.value : matchGroups.value.slice(0, GROUP_PREVIEW)
)

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

// The API returns raw transcript text, so escape here and emit a bare <mark>
// (styled globally in main.css). v-html is used for this field and no other.
function highlightContext(context: string, query: string): string {
  const safe = escapeHtml(context)
  if (!query) return safe
  const escaped = escapeHtml(query).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(`(${escaped})`, 'gi')
  return safe.replace(regex, '<mark>$1</mark>')
}

const breadcrumbItems = computed(() => [
  { label: 'Transcripts', to: '/' },
  { label: persona.value?.name || 'Speaker' },
])

// SEO meta tags (rendered during SSR thanks to useFetch above)
useSeoMeta({
  title: () => persona.value?.meta_title || persona.value?.name || 'Transcripts',
  description: () => persona.value?.meta_description || persona.value?.description || '',
  ogTitle: () => persona.value?.meta_title || persona.value?.name || 'Transcripts',
  ogDescription: () => persona.value?.meta_description || persona.value?.description || '',
  twitterCard: 'summary_large_image',
  twitterTitle: () => persona.value?.meta_title || persona.value?.name || 'Transcripts',
  twitterDescription: () => persona.value?.meta_description || persona.value?.description || '',
  robots: 'index, follow',
})

// /personas/{id} also resolves (backend falls back to id lookup), so point the
// canonical at the slug URL instead of letting the auto-canonical self-reference the id.
useHead({
  link: [
    {
      rel: 'canonical',
      href: () => `https://mentionshero.com/personas/${persona.value?.slug || slug}`,
    },
  ],
})

defineOgImage({
  component: 'OgImagePersona',
  alt: () => persona.value?.name || 'Transcripts',
  props: {
    name: () => persona.value?.name || '',
    description: () => persona.value?.description || '',
    imageUrl: () => persona.value?.image_url || '',
  },
})

// Structured data
useSchemaOrg([
  // Give the persona a page-scoped @id. definePerson defaults to the site
  // identity slot (#identity), which would make the persona the site's identity
  // and evict the MentionsHero Organization defined in the default layout.
  definePerson({
    '@id': () => `https://mentionshero.com/personas/${persona.value?.slug || slug}#person`,
    name: () => persona.value?.name || '',
    description: () => persona.value?.description || '',
    image: () => persona.value?.image_url || '',
  }),
  defineBreadcrumb({
    itemListElement: [
      { name: 'Transcripts', item: '/' },
      { name: () => persona.value?.name || '' },
    ],
  }),
])

onMounted(async () => {
  if (session.value) await fetchSubscription()
  loadTranscripts()
})
</script>

<template>
  <div class="py-6">
    <!-- Loading the speaker itself -->
    <UiLoadingBlock v-if="loadingPersona" variant="text" :count="4" label="Loading speaker" />

    <!-- Not found -->
    <UiNotFoundState
      v-else-if="!persona"
      title="That speaker is not on MentionsHero"
      description="The address may be wrong, or the speaker may have been removed. Every speaker we transcribe is listed on the transcripts page."
      back-label="Back to transcripts"
      back-to="/"
    />

    <template v-else>
      <UBreadcrumb :items="breadcrumbItems" class="mb-5" />

      <!-- Speaker header. The title slot holds the name and nothing else: it
           renders inside the <h1> and anything more corrupts the heading text. -->
      <UPageHeader
        :title="persona.name"
        :description="persona.description || undefined"
        :ui="{
          root: 'relative border-b border-default pb-8',
          wrapper: 'flex flex-row items-center justify-between gap-5',
          headline: 'mb-3 type-label text-xs font-medium text-dimmed flex items-center gap-2',
          title: 'text-2xl sm:text-2xl text-highlighted',
          description: 'mt-4 measure text-base text-muted',
        }"
      >
        <template #headline>
          <UIcon name="i-lucide-mic" class="size-3.5" aria-hidden="true" />
          Speaker
        </template>
        <template #links>
          <UiPersonaAvatar :name="persona.name" :src="persona.image_url" size="lg" decorative />
        </template>
      </UPageHeader>

      <div class="mt-8 grid items-start gap-10 lg:grid-cols-[minmax(0,1fr)_15rem] lg:gap-12">
        <div class="min-w-0 space-y-12">
          <!-- Keyword search -->
          <section aria-labelledby="keyword-heading" class="rounded-sm border border-default bg-elevated/40 p-5 sm:p-6">
            <div class="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 id="keyword-heading" class="type-subhead text-highlighted">
                  Search what {{ persona.name }} said
                </h2>
                <p class="mt-1 text-sm text-muted">
                  Every mention across the transcripts below, quoted in context.
                </p>
              </div>
              <UBadge
                v-if="!isSubscribed"
                color="primary"
                variant="subtle"
                size="sm"
                icon="i-lucide-lock"
                label="Subscribers"
              />
            </div>

            <!-- Gated: the panel stands in for the search itself -->
            <UiUpsellBanner
              v-if="!isSubscribed"
              class="mt-5"
              variant="panel"
              icon="i-lucide-text-search"
              :title="`Keyword search across ${persona.name}'s transcripts is part of the subscription`"
              description="Type any word and see every time it was said, which briefing it came from, and the sentence around it."
              cta-label="See pricing"
              cta-to="/pricing"
              :secondary-label="session ? null : 'Sign in'"
              :secondary-to="session ? null : '/login'"
            />

            <!-- Unlocked -->
            <template v-else>
              <div class="mt-5">
                <UFormField
                  label="Keyword"
                  :ui="{ label: 'type-label text-dimmed' }"
                >
                  <UInput
                    v-model="keywordQuery"
                    icon="i-lucide-search"
                    placeholder="tariffs, shutdown, inflation…"
                    size="lg"
                    class="w-full"
                  />
                </UFormField>
                <p class="mt-2 type-caption text-dimmed">
                  Two characters or more. Results update as you type.
                </p>
              </div>

              <!-- Searching -->
              <UiLoadingBlock
                v-if="keywordLoading"
                class="mt-5"
                variant="rows"
                :count="3"
                label="Searching transcripts"
              />

              <!-- Error -->
              <UAlert
                v-else-if="keywordError"
                class="mt-5"
                color="error"
                variant="subtle"
                icon="i-lucide-circle-alert"
                title="The search did not run"
                :description="`${keywordError} Try the same term again, or shorten it.`"
              >
                <template #actions>
                  <UButton
                    color="neutral"
                    variant="outline"
                    size="xs"
                    icon="i-lucide-rotate-cw"
                    label="Try again"
                    @click="searchKeywords()"
                  />
                </template>
              </UAlert>

              <!-- Results -->
              <div v-else-if="keywordResults" class="mt-6 space-y-5">
                <div class="flex flex-wrap items-end gap-x-10 gap-y-4">
                  <UiStatRow
                    layout="stack"
                    size="lg"
                    label="Mentions"
                    :value="keywordResults.total_matches"
                    tone="mark"
                  />
                  <UiStatRow
                    layout="stack"
                    size="lg"
                    label="Transcripts"
                    :value="keywordResults.transcripts_with_matches"
                  />
                  <div v-if="keywordSeries" class="min-w-0">
                    <p class="type-label text-dimmed">Per briefing</p>
                    <UiTallyRail
                      class="mt-2"
                      :values="keywordSeries"
                      :slots="30"
                      :label="`Mentions of ${keywordResults.query} per briefing, oldest first`"
                    />
                    <p class="mt-1.5 type-caption text-dimmed">One tick per briefing, oldest first.</p>
                  </div>
                </div>

                <p v-if="keywordResults.total_matches > 0 && !matchesComplete" class="type-caption text-dimmed">
                  Showing the first
                  <span class="type-figure text-muted">{{ countedMentions }}</span>
                  of
                  <span class="type-figure text-muted">{{ keywordResults.total_matches }}</span>
                  mentions. Narrow the term to see them all.
                </p>

                <!-- No matches -->
                <UiEmptyState
                  v-if="matchGroups.length === 0"
                  variant="plain"
                  size="sm"
                  icon="i-lucide-search-x"
                  :title="`No mentions of “${keywordResults.query}”`"
                  description="Try a shorter word, a different spelling, or drop the plural."
                />

                <!-- Grouped matches: one card per transcript -->
                <template v-else>
                  <ul class="space-y-3">
                    <li
                      v-for="group in visibleGroups"
                      :key="group.transcriptId"
                      class="rounded-sm border border-default bg-default p-4"
                    >
                      <div class="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
                        <div class="flex min-w-0 items-baseline gap-3">
                          <NuxtLink
                            :to="`/transcripts/${group.transcriptId}?search=${encodeURIComponent(keywordResults.query)}`"
                            class="truncate font-medium text-highlighted underline-offset-4 hover:underline hover:decoration-2 hover:decoration-mark-500"
                          >
                            {{ group.name }}
                          </NuxtLink>
                          <span v-if="group.date" class="type-figure shrink-0 text-sm text-muted">
                            {{ formatDate(group.date) }}
                          </span>
                        </div>
                        <div v-if="matchesComplete" class="flex items-center gap-2">
                          <UiTallyRail
                            :count="group.mentions"
                            :height="12"
                            :label="`${group.mentions} mentions in ${group.name}`"
                          />
                          <span class="type-figure text-sm text-highlighted">{{ group.mentions }}</span>
                          <span class="type-caption text-dimmed">
                            mention{{ group.mentions === 1 ? '' : 's' }}
                          </span>
                        </div>
                      </div>

                      <ul class="mt-3 space-y-2.5">
                        <li
                          v-for="(snippet, i) in group.snippets.slice(0, SNIPPETS_PER_GROUP)"
                          :key="i"
                          class="border-l-2 border-mark-500/50 pl-3 text-sm leading-relaxed text-muted"
                          v-html="highlightContext(snippet, keywordResults.query)"
                        />
                      </ul>
                      <p
                        v-if="group.snippets.length > SNIPPETS_PER_GROUP"
                        class="mt-2.5 pl-3 type-caption text-dimmed"
                      >
                        <span class="type-figure">+{{ group.snippets.length - SNIPPETS_PER_GROUP }}</span>
                        more passage{{ group.snippets.length - SNIPPETS_PER_GROUP === 1 ? '' : 's' }}
                        in this transcript.
                      </p>
                    </li>
                  </ul>

                  <UButton
                    v-if="matchGroups.length > GROUP_PREVIEW"
                    color="neutral"
                    variant="outline"
                    size="sm"
                    block
                    :icon="showAllGroups ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
                    :aria-expanded="showAllGroups"
                    :label="showAllGroups
                      ? 'Show fewer transcripts'
                      : `Show all ${matchGroups.length} transcripts`"
                    @click="showAllGroups = !showAllGroups"
                  />
                </template>
              </div>

              <!-- Nothing typed yet -->
              <p v-else-if="!keywordQuery.trim()" class="mt-4 type-caption text-dimmed">
                Type a word to count it across every briefing on this page.
              </p>
            </template>
          </section>

          <!-- Transcripts -->
          <section aria-labelledby="transcripts-heading" class="space-y-5">
            <div class="flex flex-wrap items-end justify-between gap-4">
              <h2 id="transcripts-heading" class="type-heading text-highlighted">
                Transcripts
                <span v-if="transcriptsLoaded && total > 0" class="type-figure text-lg text-dimmed">
                  {{ total }}
                </span>
              </h2>

              <div class="flex w-full flex-wrap items-center gap-3 sm:w-auto">
                <UInput
                  v-model="search"
                  icon="i-lucide-search"
                  placeholder="Filter by a word said…"
                  aria-label="Filter transcripts by a word said in them"
                  size="sm"
                  class="w-full sm:w-56"
                />

                <div class="flex items-center gap-2" role="group" aria-label="Sort transcripts">
                  <span class="type-label text-dimmed">Sort</span>
                  <UButton
                    size="xs"
                    color="neutral"
                    :variant="sortBy === 'date' ? 'subtle' : 'ghost'"
                    :aria-pressed="sortBy === 'date'"
                    :aria-label="sortLabel('date')"
                    :trailing-icon="sortBy === 'date'
                      ? (sortOrder === 'desc' ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up')
                      : undefined"
                    label="Date"
                    @click="toggleSort('date')"
                  />
                  <UButton
                    size="xs"
                    color="neutral"
                    :variant="sortBy === 'name' ? 'subtle' : 'ghost'"
                    :aria-pressed="sortBy === 'name'"
                    :aria-label="sortLabel('name')"
                    :trailing-icon="sortBy === 'name'
                      ? (sortOrder === 'desc' ? 'i-lucide-chevron-down' : 'i-lucide-chevron-up')
                      : undefined"
                    label="Name"
                    @click="toggleSort('name')"
                  />
                </div>
              </div>
            </div>

            <!-- Error: a failed request is not an empty result -->
            <UAlert
              v-if="transcriptsError"
              color="error"
              variant="subtle"
              icon="i-lucide-circle-alert"
              title="The transcript list did not load"
              :description="`${transcriptsError} Check your connection, then load it again.`"
            >
              <template #actions>
                <UButton
                  color="neutral"
                  variant="outline"
                  size="xs"
                  icon="i-lucide-rotate-cw"
                  label="Load again"
                  @click="loadTranscripts()"
                />
              </template>
            </UAlert>

            <UiLoadingBlock
              v-else-if="loadingTranscripts"
              variant="rows"
              :count="6"
              label="Loading transcripts"
            />

            <!-- Empty -->
            <UiEmptyState
              v-else-if="transcripts.length === 0 && debouncedSearch"
              icon="i-lucide-search-x"
              :title="`No transcript contains “${debouncedSearch}”`"
              :description="filterEmptyHint"
            >
              <UButton
                color="neutral"
                variant="outline"
                icon="i-lucide-x"
                label="Clear the filter"
                @click="clearTranscriptSearch()"
              />
            </UiEmptyState>

            <UiEmptyState
              v-else-if="transcripts.length === 0"
              icon="i-lucide-file-text"
              :title="`No transcripts of ${persona.name} are public yet`"
              description="We publish each briefing once it is transcribed. Browse the speakers we already cover in the meantime."
              action-label="Browse speakers"
              action-to="/"
              action-icon="i-lucide-arrow-left"
            />

            <!-- List -->
            <ul v-else class="border-t border-default">
              <li v-for="t in transcripts" :key="t.id" class="rule-dotted">
                <NuxtLink
                  :to="`/transcripts/${t.id}`"
                  class="group flex items-start gap-3 px-2 py-4 transition-colors hover:bg-elevated/60"
                >
                  <UIcon name="i-lucide-file-text" class="mt-0.5 size-4 shrink-0 text-dimmed" aria-hidden="true" />
                  <div class="min-w-0 flex-1">
                    <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
                      <span
                        class="font-medium text-highlighted underline-offset-4 group-hover:underline group-hover:decoration-2 group-hover:decoration-mark-500"
                      >
                        {{ t.name || 'Untitled' }}
                      </span>
                      <UBadge
                        v-if="t.is_premium"
                        color="primary"
                        variant="subtle"
                        size="xs"
                        icon="i-lucide-lock"
                        label="Premium"
                      />
                    </div>
                    <p v-if="t.preview" class="mt-1 line-clamp-2 text-sm text-muted">
                      {{ t.preview }}
                    </p>
                    <div class="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 type-caption text-dimmed">
                      <span class="type-figure">{{ formatDate(t.upload_date, t.created_at) }}</span>
                      <span v-if="t.folder_name" class="inline-flex items-center gap-1">
                        <UIcon name="i-lucide-folder" class="size-3" aria-hidden="true" />
                        {{ t.folder_name }}
                      </span>
                    </div>
                  </div>
                </NuxtLink>
              </li>
            </ul>

            <!-- Pagination -->
            <div
              v-if="!transcriptsError && !loadingTranscripts && totalPages > 1"
              class="flex flex-wrap items-center justify-between gap-4 pt-2"
            >
              <p class="type-caption text-dimmed">
                Showing
                <span class="type-figure text-muted">{{ rangeStart }}–{{ rangeEnd }}</span>
                of
                <span class="type-figure text-muted">{{ total }}</span>
              </p>
              <UPagination
                v-model:page="page"
                :total="total"
                :items-per-page="PAGE_SIZE"
                :sibling-count="1"
                size="sm"
              />
            </div>
          </section>
        </div>

        <!-- Margin metadata -->
        <aside class="lg:sticky lg:top-24">
          <h2 class="sr-only">About {{ persona.name }}</h2>
          <dl class="space-y-3">
            <UiStatRow
              semantic
              divided
              size="sm"
              label="Transcripts"
              :value="transcriptsLoaded ? total : null"
            />
          </dl>

          <div v-if="persona.aliases?.length" class="mt-6">
            <p class="type-label text-dimmed">Also known as</p>
            <ul class="mt-2.5 flex flex-wrap gap-1.5">
              <li v-for="alias in persona.aliases" :key="alias">
                <UBadge color="neutral" variant="subtle" size="sm" class="font-mono" :label="alias" />
              </li>
            </ul>
            <p class="mt-2.5 type-caption text-dimmed">
              We attribute a line to {{ persona.name }} when the transcript labels the speaker
              with one of these names.
            </p>
          </div>
        </aside>
      </div>
    </template>
  </div>
</template>
