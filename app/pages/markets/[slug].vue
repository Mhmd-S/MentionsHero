<script setup lang="ts">
const route = useRoute()
const slug = route.params.slug as string
const { publicFetch } = usePublicApi()
const { isSubscribed, fetchSubscription } = useSubscription()
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
const { data: persona } = await useFetch<{ name: string; slug: string | null; image_url: string | null; description: string | null }>(
  `/api/public/personas/${slug}`,
)

const marketsData = ref<PersonaMarketsDetail | null>(null)
const loading = ref(false)
const error = ref('')

const sourceFilter = ref<'all' | 'kalshi' | 'polymarket'>('all')
const statusFilter = ref<'all' | 'active' | 'closed'>('all')
const search = ref('')

async function loadMarkets() {
  loading.value = true
  error.value = ''
  try {
    marketsData.value = await publicFetch<PersonaMarketsDetail>(`/api/public/markets/${slug}`)
  } catch (err: any) {
    error.value = err?.data?.detail || 'Failed to load markets'
  } finally {
    loading.value = false
  }
}

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

const kalshiEvents = computed(() => filteredEvents.value.filter((e) => e.source === 'kalshi'))
const polymarketEvents = computed(() => filteredEvents.value.filter((e) => e.source === 'polymarket'))

const totalMarkets = computed(() =>
  (marketsData.value?.events || []).reduce((sum, e) => sum + e.markets.length, 0)
)

function formatDate(dateString: string | null) {
  if (!dateString) return ''
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

function trendIcon(trend?: string) {
  if (trend === 'increasing') return 'i-lucide-trending-up'
  if (trend === 'decreasing') return 'i-lucide-trending-down'
  return 'i-lucide-minus'
}

function trendColor(trend?: string) {
  if (trend === 'increasing') return 'text-green-500'
  if (trend === 'decreasing') return 'text-red-500'
  return 'text-muted'
}

onMounted(() => {
  if (session.value) fetchSubscription()
  loadMarkets()
})

// SEO
useSeoMeta({
  title: () => persona.value ? `${persona.value.name} — Markets` : 'Markets',
  description: () => persona.value ? `Prediction markets and transcript mentions analysis for ${persona.value.name}.` : '',
  ogTitle: () => persona.value ? `${persona.value.name} — Markets | MentionsHero` : 'Markets',
  ogDescription: () => persona.value ? `Track prediction markets linked to ${persona.value.name}'s transcript mentions.` : '',
  robots: 'index, follow',
})

if (persona.value?.image_url) {
  defineOgImage({
    component: 'OgImagePersona',
    props: {
      name: () => persona.value?.name || '',
      description: () => `Prediction markets analysis`,
      imageUrl: () => persona.value?.image_url || '',
    },
  })
}

useSchemaOrg([
  defineWebPage({
    name: () => persona.value ? `${persona.value.name} — Markets` : 'Markets',
  }),
  defineBreadcrumb({
    itemListElement: [
      { name: 'Home', item: '/' },
      { name: 'Markets', item: '/markets' },
      { name: () => persona.value?.name || '' },
    ],
  }),
])
</script>

<template>
  <div>
    <!-- Loading persona -->
    <div v-if="!persona && !error" class="flex justify-center py-16">
      <UIcon name="i-lucide-loader" class="size-6 animate-spin text-muted" />
    </div>

    <!-- Persona not found -->
    <div v-else-if="!persona" class="py-16 text-center text-muted">
      <UIcon name="i-lucide-alert-triangle" class="size-10 mx-auto mb-3 opacity-40" />
      <p class="font-medium">Not found.</p>
      <NuxtLink to="/markets">
        <UButton variant="outline" size="sm" class="mt-4">Back to Markets</UButton>
      </NuxtLink>
    </div>

    <template v-else>
      <!-- Header -->
      <UPageHeader :title="persona.name">
        <template #title>
          <NuxtLink to="/markets" class="flex items-center gap-1 mb-3 text-sm text-muted hover:text-default transition-colors">
            <UIcon name="i-lucide-arrow-left" class="size-4" />
            All Markets
          </NuxtLink>
          <div class="flex items-center gap-4">
            <UAvatar v-if="persona.image_url" :src="persona.image_url" :alt="persona.name" size="xl" />
            <UAvatar v-else :text="persona.name[0]" size="xl" />
            <div>
              <span class="text-2xl font-bold">{{ persona.name }}</span>
              <p v-if="totalMarkets > 0" class="text-sm text-muted mt-1">
                {{ totalMarkets }} market{{ totalMarkets !== 1 ? 's' : '' }} tracked
              </p>
            </div>
          </div>
        </template>
      </UPageHeader>

      <!-- Filters -->
      <div class="flex items-center gap-3 flex-wrap my-4">
        <UInput v-model="search" icon="i-lucide-search" placeholder="Search markets..." class="w-full sm:w-80" size="md" variant="outline" />
        <div class="flex items-center gap-1">
          <UButton size="xs" :variant="sourceFilter === 'all' ? 'solid' : 'ghost'" @click="sourceFilter = 'all'">All</UButton>
          <UButton size="xs" :variant="sourceFilter === 'kalshi' ? 'solid' : 'ghost'" @click="sourceFilter = 'kalshi'">Kalshi</UButton>
          <UButton size="xs" :variant="sourceFilter === 'polymarket' ? 'solid' : 'ghost'" @click="sourceFilter = 'polymarket'">Polymarket</UButton>
        </div>
        <div class="flex items-center gap-1">
          <UButton size="xs" :variant="statusFilter === 'all' ? 'solid' : 'ghost'" @click="statusFilter = 'all'">All</UButton>
          <UButton size="xs" :variant="statusFilter === 'active' ? 'solid' : 'ghost'" @click="statusFilter = 'active'">Active</UButton>
          <UButton size="xs" :variant="statusFilter === 'closed' ? 'solid' : 'ghost'" @click="statusFilter = 'closed'">Resolved</UButton>
        </div>
      </div>

      <!-- Loading markets -->
      <div v-if="loading" class="flex justify-center py-12">
        <UIcon name="i-lucide-loader" class="size-5 animate-spin text-muted" />
      </div>

      <!-- Error -->
      <div v-else-if="error" class="py-12 text-center text-red-500">
        <UIcon name="i-lucide-alert-circle" class="size-8 mx-auto mb-2 opacity-60" />
        <p class="text-sm">{{ error }}</p>
      </div>

      <!-- No events -->
      <div v-else-if="filteredEvents.length === 0" class="py-12 text-center text-muted">
        <UIcon name="i-lucide-bar-chart-3" class="size-10 mx-auto mb-3 opacity-40" />
        <p class="text-sm">{{ search ? `No markets matching "${search}"` : 'No analyzed markets yet' }}</p>
      </div>

      <!-- Events -->
      <div v-else class="space-y-8">
        <!-- Kalshi section -->
        <div v-if="kalshiEvents.length > 0">
          <div class="flex items-center gap-2 mb-4">
            <h2 class="text-lg font-semibold">Kalshi</h2>
            <UBadge color="info" variant="subtle" size="xs">{{ kalshiEvents.length }}</UBadge>
          </div>
          <div class="space-y-6">
            <div v-for="event in kalshiEvents" :key="event.event_id">
              <div class="flex items-center gap-2 mb-3">
                <img v-if="event.image" :src="event.image" :alt="event.title" class="size-8 rounded-md object-cover shrink-0" />
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <p class="font-semibold text-sm truncate">{{ event.title }}</p>
                    <UBadge v-if="event.status !== 'active'" color="neutral" variant="subtle" size="xs">{{ event.status }}</UBadge>
                  </div>
                  <p v-if="event.strike_date || event.end_date" class="text-xs text-muted">{{ formatDate(event.strike_date || event.end_date) }}</p>
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                <UCard v-for="market in event.markets" :key="`${market.market_id}-${market.search_term}`" :ui="{ body: 'sm:p-4' }">
                  <p class="text-sm font-medium leading-snug mb-2">{{ market.question }}</p>
                  <div class="flex items-center flex-wrap gap-1.5 mb-3">
                    <UBadge variant="subtle" color="neutral" size="xs">{{ market.search_term }}</UBadge>
                    <UBadge variant="outline" color="neutral" size="xs">{{ market.price }}&cent;</UBadge>
                    <UBadge v-if="market.result === 'yes'" color="success" variant="subtle" size="xs">YES</UBadge>
                    <UBadge v-else-if="market.result === 'no'" color="error" variant="subtle" size="xs">NO</UBadge>
                  </div>
                  <div v-if="market.total_mentions !== undefined" class="space-y-1">
                    <div class="flex items-center gap-2 text-xs">
                      <span class="text-muted"><span class="font-medium text-default">{{ market.total_mentions }}</span> mention{{ market.total_mentions !== 1 ? 's' : '' }}</span>
                      <span class="text-muted">&middot;</span>
                      <span class="text-muted">{{ market.briefings_with_term }}/{{ market.total_briefings }} briefings</span>
                    </div>
                    <div class="flex items-center gap-1.5 text-xs">
                      <UIcon :name="trendIcon(market.trend)" :class="['size-3.5', trendColor(market.trend)]" />
                      <span :class="trendColor(market.trend)" class="capitalize">{{ market.trend || 'stable' }}</span>
                      <span v-if="market.percentage !== undefined" class="text-muted">&middot; {{ Math.round(market.percentage) }}% of briefings</span>
                    </div>
                  </div>
                  <div v-else class="flex items-center gap-2 text-xs text-muted py-1">
                    <UIcon name="i-lucide-lock" class="size-3.5" />
                    <span>Subscribe to see analysis</span>
                  </div>
                </UCard>
              </div>
            </div>
          </div>
        </div>

        <!-- Polymarket section -->
        <div v-if="polymarketEvents.length > 0">
          <div class="flex items-center gap-2 mb-4">
            <h2 class="text-lg font-semibold">Polymarket</h2>
            <UBadge color="primary" variant="subtle" size="xs">{{ polymarketEvents.length }}</UBadge>
          </div>
          <div class="space-y-6">
            <div v-for="event in polymarketEvents" :key="event.event_id">
              <div class="flex items-center gap-2 mb-3">
                <img v-if="event.image" :src="event.image" :alt="event.title" class="size-8 rounded-md object-cover shrink-0" />
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2">
                    <p class="font-semibold text-sm truncate">{{ event.title }}</p>
                    <UBadge v-if="event.status !== 'active'" color="neutral" variant="subtle" size="xs">{{ event.status }}</UBadge>
                  </div>
                  <p v-if="event.strike_date || event.end_date" class="text-xs text-muted">{{ formatDate(event.strike_date || event.end_date) }}</p>
                </div>
              </div>
              <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                <UCard v-for="market in event.markets" :key="`${market.market_id}-${market.search_term}`" :ui="{ body: 'sm:p-4' }">
                  <p class="text-sm font-medium leading-snug mb-2">{{ market.question }}</p>
                  <div class="flex items-center flex-wrap gap-1.5 mb-3">
                    <UBadge variant="subtle" color="neutral" size="xs">{{ market.search_term }}</UBadge>
                    <UBadge variant="outline" color="neutral" size="xs">{{ market.price }}&cent;</UBadge>
                    <UBadge v-if="market.result === 'yes'" color="success" variant="subtle" size="xs">YES</UBadge>
                    <UBadge v-else-if="market.result === 'no'" color="error" variant="subtle" size="xs">NO</UBadge>
                  </div>
                  <div v-if="market.total_mentions !== undefined" class="space-y-1">
                    <div class="flex items-center gap-2 text-xs">
                      <span class="text-muted"><span class="font-medium text-default">{{ market.total_mentions }}</span> mention{{ market.total_mentions !== 1 ? 's' : '' }}</span>
                      <span class="text-muted">&middot;</span>
                      <span class="text-muted">{{ market.briefings_with_term }}/{{ market.total_briefings }} briefings</span>
                    </div>
                    <div class="flex items-center gap-1.5 text-xs">
                      <UIcon :name="trendIcon(market.trend)" :class="['size-3.5', trendColor(market.trend)]" />
                      <span :class="trendColor(market.trend)" class="capitalize">{{ market.trend || 'stable' }}</span>
                      <span v-if="market.percentage !== undefined" class="text-muted">&middot; {{ Math.round(market.percentage) }}% of briefings</span>
                    </div>
                  </div>
                  <div v-else class="flex items-center gap-2 text-xs text-muted py-1">
                    <UIcon name="i-lucide-lock" class="size-3.5" />
                    <span>Subscribe to see analysis</span>
                  </div>
                </UCard>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Paywall CTA for free users -->
      <div
        v-if="marketsData?.is_limited"
        class="mt-6 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-3"
      >
        <div class="flex-1">
          <p class="text-sm font-medium">Unlock full market analysis</p>
          <p class="text-sm text-muted mt-0.5">
            Subscribe to see mention counts, trends, and detailed analysis for {{ persona.name }}'s prediction markets.
          </p>
        </div>
        <UButton to="/pricing" icon="i-lucide-crown" variant="soft" color="warning" size="sm">
          View Pricing
        </UButton>
      </div>
    </template>
  </div>
</template>
