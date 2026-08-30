<script setup lang="ts">
const route = useRoute()
const slug = route.params.slug as string
const { publicFetch } = usePublicApi()
const { fetchSubscription } = useSubscription()
const { session } = useAuth()

interface MarketEntry {
  market_id: string
  question: string | null
  search_term: string
  price: number
  result: string | null
  status: string
  total_mentions?: number
  briefings_with_term?: number
  total_briefings?: number
  percentage?: number
  trend?: string
}

interface MarketEvent {
  source: 'kalshi' | 'polymarket'
  event_id: string
  event_ticker: string | null
  title: string
  strike_date: string | null
  end_date: string | null
  status: string
  image: string | null
  markets: MarketEntry[]
}

interface PersonaMarketsDetail {
  persona: {
    id: string
    name: string
    slug: string | null
    image_url: string | null
    description: string | null
  }
  events: MarketEvent[]
  is_limited: boolean
}

// SSR-compatible fetch for persona data (SEO)
const { data: persona, status: personaStatus, error: personaError } = await useFetch<{ name: string; slug: string | null; image_url: string | null; description: string | null }>(
  `/api/public/personas/${slug}`,
)

// The persona fetch has its own failure mode: without this the page would spin
// forever whenever the persona 404s while the markets call succeeds.
const personaLoading = computed(() => personaStatus.value === 'pending')
const personaMissing = computed(() => !personaLoading.value && (!!personaError.value || !persona.value))

const marketsData = ref<PersonaMarketsDetail | null>(null)
// Starts true: the markets fetch is client-only, so the server-rendered HTML must
// show the skeleton, not a false "no markets" empty state.
const loading = ref(true)
const error = ref('')

const sourceFilter = ref('all')
const statusFilter = ref('all')
const search = ref('')

/**
 * Event cards on /markets link here as #event-{event_id}. The markets load on the
 * client, after the browser has already tried to resolve the hash, so bring the
 * event into view once its markup exists.
 */
async function scrollToHash() {
  if (!import.meta.client) return
  const hash = route.hash
  if (!hash) return
  await nextTick()
  document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function loadMarkets() {
  loading.value = true
  error.value = ''
  try {
    marketsData.value = await publicFetch<PersonaMarketsDetail>(`/api/public/markets/${slug}`)
    scrollToHash()
  } catch (err) {
    error.value = (err as { data?: { detail?: string } })?.data?.detail || 'The markets service did not respond.'
  } finally {
    loading.value = false
  }
}

/** Both venues, one loop. */
const SOURCES = [
  { key: 'kalshi', label: 'Kalshi' },
  { key: 'polymarket', label: 'Polymarket' },
] as const

const filteredEvents = computed(() => {
  if (!marketsData.value) return []
  const q = search.value.toLowerCase().trim()

  return marketsData.value.events
    .filter((e) => {
      if (sourceFilter.value !== 'all' && e.source !== sourceFilter.value) return false
      if (statusFilter.value !== 'all' && e.status !== statusFilter.value) return false
      if (q) {
        const matchesTitle = e.title.toLowerCase().includes(q)
        const matchesMarket = e.markets.some(
          (m) => (m.question || '').toLowerCase().includes(q) || m.search_term.toLowerCase().includes(q)
        )
        if (!matchesTitle && !matchesMarket) return false
      }
      return true
    })
})

const sections = computed(() =>
  SOURCES.map((source) => ({
    ...source,
    events: filteredEvents.value.filter((e) => e.source === source.key),
  })).filter((section) => section.events.length > 0)
)

const allEvents = computed(() => marketsData.value?.events || [])

const totalMarkets = computed(() =>
  allEvents.value.reduce((sum, e) => sum + e.markets.length, 0)
)

const sourceItems = computed(() => {
  const count = (key: string) => allEvents.value.filter((e) => e.source === key).length
  return [
    { label: 'All', value: 'all', count: allEvents.value.length },
    { label: 'Kalshi', value: 'kalshi', count: count('kalshi') },
    { label: 'Polymarket', value: 'polymarket', count: count('polymarket') },
  ]
})

const statusItems = computed(() => {
  const count = (key: string) => allEvents.value.filter((e) => e.status === key).length
  return [
    { label: 'All', value: 'all', count: allEvents.value.length },
    { label: 'Active', value: 'active', count: count('active') },
    { label: 'Resolved', value: 'closed', count: count('closed') },
  ]
})

const filtersApplied = computed(
  () => !!search.value || sourceFilter.value !== 'all' || statusFilter.value !== 'all'
)

function clearFilters() {
  search.value = ''
  sourceFilter.value = 'all'
  statusFilter.value = 'all'
}

function formatDate(dateString: string | null) {
  if (!dateString) return ''
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

/** Unlocked payload is signalled by field-absence: the API omits it for free users. */
function isUnlocked(market: MarketEntry) {
  return market.total_mentions !== undefined
}

function trendLabel(trend?: string) {
  if (trend === 'increasing') return 'Rising'
  if (trend === 'decreasing') return 'Falling'
  return 'Stable'
}

function trendIcon(trend?: string) {
  if (trend === 'increasing') return 'i-lucide-trending-up'
  if (trend === 'decreasing') return 'i-lucide-trending-down'
  return 'i-lucide-minus'
}

function trendTone(trend?: string): 'yes' | 'no' | 'muted' {
  if (trend === 'increasing') return 'yes'
  if (trend === 'decreasing') return 'no'
  return 'muted'
}

onMounted(async () => {
  if (session.value) await fetchSubscription()
  loadMarkets()
})

// SEO
useSeoMeta({
  title: () => persona.value ? `${persona.value.name} — Markets` : 'Markets',
  description: () => persona.value ? `Prediction markets and transcript mentions analysis for ${persona.value.name}.` : '',
  ogTitle: () => persona.value ? `${persona.value.name} — Markets | MentionsHero` : 'Markets',
  ogDescription: () => persona.value ? `Track prediction markets linked to ${persona.value.name}'s transcript mentions.` : '',
  twitterCard: 'summary_large_image',
  twitterTitle: () => persona.value ? `${persona.value.name} — Markets | MentionsHero` : 'Markets',
  twitterDescription: () => persona.value ? `Track prediction markets linked to ${persona.value.name}'s transcript mentions.` : '',
  robots: 'index, follow',
})

// /markets/{id} also resolves (the backend falls back to id lookup), so point the
// canonical at the slug URL instead of letting the auto-canonical self-reference the id.
useHead({
  link: [
    {
      rel: 'canonical',
      href: () => `https://mentionshero.com/markets/${persona.value?.slug || slug}`,
    },
  ],
})

defineOgImage({
  component: persona.value?.image_url ? 'OgImagePersona' : 'OgImageDefault',
  alt: () => persona.value?.name || 'Markets',
  props: persona.value?.image_url
    ? {
        name: persona.value.name,
        description: 'Prediction markets analysis',
        imageUrl: persona.value.image_url,
      }
    : undefined,
})

useSchemaOrg([
  defineWebPage({
    name: () => persona.value ? `${persona.value.name} — Markets` : 'Markets',
  }),
  defineBreadcrumb({
    itemListElement: [
      { name: 'Transcripts', item: '/' },
      { name: 'Markets', item: '/markets' },
      { name: () => persona.value?.name || '' },
    ],
  }),
])
</script>

<template>
  <div>
    <!-- Loading the persona shell -->
    <UiLoadingBlock v-if="personaLoading" variant="spinner" label="Loading persona" />

    <!-- Persona does not resolve -->
    <UiNotFoundState
      v-else-if="personaMissing"
      title="That persona is not on MentionsHero"
      description="The name in the address does not match a tracked persona. It may have been renamed or removed."
      back-label="Back to markets"
      back-to="/markets"
      icon="i-lucide-search-x"
    />

    <template v-else-if="persona">
      <UBreadcrumb
        class="mb-4"
        :items="[
          { label: 'Transcripts', to: '/' },
          { label: 'Markets', to: '/markets' },
          { label: persona.name },
        ]"
      />

      <UPageHeader
        :title="persona.name"
        :ui="{
          title: 'text-2xl sm:text-2xl text-highlighted',
          description: 'mt-4 measure text-base text-muted',
          headline: 'mb-3 type-label text-xs font-medium text-dimmed flex items-center gap-2',
        }"
      >
        <template #headline>
          <div class="flex items-center gap-3">
            <UiPersonaAvatar :name="persona.name" :src="persona.image_url" size="md" decorative />
            <span class="type-label text-dimmed">Prediction markets</span>
          </div>
        </template>
        <template #description>
          <span class="text-base text-muted">
            What the markets price against what
            {{ persona.name }} actually said.
            <template v-if="totalMarkets > 0">
              <span class="type-figure text-default">{{ totalMarkets }}</span>
              {{ totalMarkets === 1 ? 'market' : 'markets' }} tracked.
            </template>
          </span>
        </template>
        <template #links>
          <UButton
            :to="`/personas/${persona.slug || slug}`"
            color="neutral"
            variant="outline"
            trailing-icon="i-lucide-arrow-right"
          >
            Transcripts
          </UButton>
        </template>
      </UPageHeader>

      <!-- Filters -->
      <div class="my-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <UInput
          v-model="search"
          type="search"
          icon="i-lucide-search"
          aria-label="Search this persona's markets by question or tracked term"
          placeholder="Search questions or terms"
          class="w-full lg:w-80"
          size="md"
          variant="outline"
        />
        <div class="flex flex-wrap items-center gap-x-6 gap-y-3">
          <UiFilterToggle v-model="sourceFilter" label="Venue" :items="sourceItems" />
          <UiFilterToggle v-model="statusFilter" label="Status" :items="statusItems" />
        </div>
      </div>

      <!-- Loading markets -->
      <UiLoadingBlock v-if="loading" variant="cards" :count="6" :columns="3" label="Loading markets" />

      <!-- Error -->
      <UAlert
        v-else-if="error"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        title="The markets did not load"
        :description="error"
        :actions="[{ label: 'Try again', color: 'neutral', variant: 'outline', onClick: () => loadMarkets() }]"
      />

      <!-- Nothing to show -->
      <UiEmptyState
        v-else-if="sections.length === 0"
        icon="i-lucide-chart-bar"
        :title="filtersApplied ? 'No markets match those filters' : `No markets are tracked for ${persona.name} yet`"
        :description="filtersApplied
          ? 'Try a shorter word, or set the venue and status filters back to All.'
          : 'When a Kalshi or Polymarket mentions event is linked to this persona, its terms and counts appear here.'"
      >
        <UButton
          v-if="filtersApplied"
          color="primary"
          variant="solid"
          icon="i-lucide-rotate-cw"
          @click="clearFilters()"
        >
          Clear the filters
        </UButton>
        <UButton v-else to="/markets" color="primary" variant="solid" trailing-icon="i-lucide-arrow-right">
          Browse every market
        </UButton>
      </UiEmptyState>

      <!-- Venue sections: one loop, both venues, equal treatment -->
      <div v-else class="space-y-12">
        <section v-for="section in sections" :key="section.key">
          <div class="rule-dotted mb-5 flex items-baseline gap-3 pb-2">
            <h2 class="type-heading text-highlighted">{{ section.label }}</h2>
            <UBadge color="neutral" variant="subtle" size="sm" class="type-figure">
              {{ section.events.length }}
            </UBadge>
            <span class="type-caption text-dimmed">{{ section.events.length === 1 ? 'event' : 'events' }}</span>
          </div>

          <div class="space-y-8">
            <!-- Each event is addressable: /markets/{slug}#event-{event_id} -->
            <div
              v-for="event in section.events"
              :id="`event-${event.event_id}`"
              :key="event.event_id"
              class="scroll-mt-24 rounded-sm target:ring-1 target:ring-default"
            >
              <div class="mb-3 flex items-start gap-3">
                <img
                  v-if="event.image"
                  :src="event.image"
                  alt=""
                  class="size-8 shrink-0 rounded-sm object-cover"
                >
                <div class="min-w-0 flex-1">
                  <div class="flex flex-wrap items-start gap-x-2 gap-y-1">
                    <h3 class="text-base font-semibold leading-snug text-highlighted">{{ event.title }}</h3>
                    <UBadge
                      v-if="event.status !== 'active'"
                      color="neutral"
                      variant="subtle"
                      size="xs"
                      class="mt-0.5 shrink-0 capitalize"
                    >
                      {{ event.status }}
                    </UBadge>
                  </div>
                  <p class="type-caption mt-1 flex flex-wrap items-center gap-x-2 text-dimmed">
                    <span v-if="event.event_ticker" class="type-figure break-all uppercase">{{ event.event_ticker }}</span>
                    <span v-if="event.event_ticker && (event.strike_date || event.end_date)" aria-hidden="true">&middot;</span>
                    <span v-if="event.strike_date || event.end_date" class="type-figure">
                      {{ formatDate(event.strike_date || event.end_date) }}
                    </span>
                  </p>
                </div>
              </div>

              <div class="grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-3">
                <UCard
                  v-for="market in event.markets"
                  :key="`${market.market_id}-${market.search_term}`"
                  class="h-full"
                  :ui="{ body: 'sm:p-4' }"
                >
                  <div class="flex h-full flex-col gap-3">
                    <div class="flex flex-wrap items-center gap-2">
                      <UiTermChip
                        :term="market.search_term"
                        :price="market.price"
                        :result="market.result"
                      />
                      <UBadge v-if="market.result === 'yes'" color="success" variant="subtle" size="xs">
                        Resolved YES
                      </UBadge>
                      <UBadge v-else-if="market.result === 'no'" color="error" variant="subtle" size="xs">
                        Resolved NO
                      </UBadge>
                    </div>

                    <p v-if="market.question" class="text-sm leading-snug text-muted">
                      {{ market.question }}
                    </p>

                    <!-- Paywalled payload: the gate is field-absence -->
                    <dl v-if="isUnlocked(market)" class="mt-auto space-y-2 pt-1">
                      <UiStatRow semantic label="Mentions" tone="mark" size="sm" divided>
                        <span class="inline-flex items-center gap-2">
                          {{ market.total_mentions }}
                          <UiTallyRail :count="market.total_mentions" :max="12" :height="10" />
                        </span>
                      </UiStatRow>
                      <UiStatRow
                        semantic
                        label="Briefings"
                        size="sm"
                        divided
                        :value="`${market.briefings_with_term ?? 0}/${market.total_briefings ?? 0}${market.percentage !== undefined ? ` · ${Math.round(market.percentage)}%` : ''}`"
                      />
                      <UiStatRow
                        semantic
                        label="Trend"
                        size="sm"
                        :tone="trendTone(market.trend)"
                        :icon="trendIcon(market.trend)"
                        :value="trendLabel(market.trend)"
                      />
                    </dl>

                    <div v-else class="mt-auto flex items-center gap-2 pt-2">
                      <UIcon name="i-lucide-lock" class="size-3.5 shrink-0 text-dimmed" aria-hidden="true" />
                      <span class="type-caption text-dimmed">Mention count is part of the subscription</span>
                    </div>
                  </div>
                </UCard>
              </div>
            </div>
          </div>
        </section>
      </div>

      <!-- Paywall prompt for free users -->
      <UiUpsellBanner
        v-if="marketsData?.is_limited"
        class="mt-10"
        :title="`Mention counts for ${persona.name} are part of the subscription`"
        description="Subscribe to see how often each term was said, how many briefings it appeared in, and which way the count is moving."
      />
    </template>
  </div>
</template>
