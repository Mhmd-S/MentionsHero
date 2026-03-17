<script setup lang="ts">
interface TopTerm {
  term: string
  mentions: number
  price: number
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
  market_count: number
  top_terms: TopTerm[]
}

interface PersonaWithEvents {
  persona: {
    id: string
    name: string
    slug: string | null
    image_url: string | null
  }
  events: MarketEvent[]
}

const { data: personaMarkets, status } = await useFetch<PersonaWithEvents[]>('/api/public/markets')
const loading = computed(() => status.value === 'pending')

const search = ref('')
const sourceFilter = ref<'all' | 'kalshi' | 'polymarket'>('all')

const filtered = computed(() => {
  const q = search.value.toLowerCase().trim()
  return (personaMarkets.value || [])
    .map((pm) => {
      let events = pm.events
      if (sourceFilter.value !== 'all') {
        events = events.filter((e) => e.source === sourceFilter.value)
      }
      if (q) {
        events = events.filter(
          (e) =>
            e.title.toLowerCase().includes(q) ||
            e.top_terms.some((t) => t.term.toLowerCase().includes(q))
        )
      }
      return { ...pm, events }
    })
    .filter((pm) => pm.events.length > 0)
})

const filteredKalshiByPersona = computed(() =>
  filtered.value
    .map((pm) => ({ ...pm, events: pm.events.filter((e) => e.source === 'kalshi') }))
    .filter((pm) => pm.events.length > 0)
)

const filteredPolyByPersona = computed(() =>
  filtered.value
    .map((pm) => ({ ...pm, events: pm.events.filter((e) => e.source === 'polymarket') }))
    .filter((pm) => pm.events.length > 0)
)

const totalEvents = computed(() =>
  (personaMarkets.value || []).reduce((sum, pm) => sum + pm.events.length, 0)
)

function formatDate(dateString: string | null) {
  if (!dateString) return ''
  return new Date(dateString).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

useSeoMeta({
  title: 'Prediction Markets & Transcript Analysis',
  description: 'Track prediction markets linked to transcript mentions. See how often public figures mention key terms and how it relates to Kalshi & Polymarket prices.',
  ogTitle: 'MentionsHero — Prediction Markets Analysis',
  ogDescription: 'Track prediction markets linked to transcript mentions. See mention frequency, trends, and market prices.',
  robots: 'index, follow',
})

defineOgImage({ component: 'OgImageDefault' })

useSchemaOrg([
  defineWebPage({
    name: 'Prediction Markets & Transcript Analysis',
    description: 'Track prediction markets linked to transcript mentions across Kalshi and Polymarket.',
  }),
  defineBreadcrumb({
    itemListElement: [
      { name: 'Home', item: '/' },
      { name: 'Markets' },
    ],
  }),
])
</script>

<template>
  <div>
    <UPageHeader title="Markets">
      <template #description>
        <span class="text-sm text-muted">
          Prediction markets linked to transcript mentions
          <span v-if="totalEvents > 0" class="text-default">&middot; {{ totalEvents }} events tracked</span>
        </span>
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
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex justify-center py-16">
      <UIcon name="i-lucide-loader" class="size-6 animate-spin text-muted" />
    </div>

    <!-- Empty -->
    <div v-else-if="filtered.length === 0" class="py-16 text-center text-muted">
      <UIcon name="i-lucide-bar-chart-3" class="size-12 mx-auto mb-4 opacity-40" />
      <p class="text-sm">{{ search ? `No markets matching "${search}"` : 'No markets available yet' }}</p>
    </div>

    <!-- Separated source sections -->
    <div v-else class="space-y-10">
      <!-- Kalshi section -->
      <div v-if="filteredKalshiByPersona.length > 0">
        <div class="flex items-center gap-2 mb-5">
          <h2 class="text-lg font-semibold">Kalshi</h2>
          <UBadge color="info" variant="subtle" size="xs">{{ filteredKalshiByPersona.reduce((s, pm) => s + pm.events.length, 0) }}</UBadge>
        </div>
        <div class="space-y-8">
          <div v-for="pm in filteredKalshiByPersona" :key="pm.persona.id">
            <div class="flex items-center gap-3 mb-3">
              <NuxtLink :to="`/personas/${pm.persona.slug || pm.persona.id}`">
                <UAvatar v-if="pm.persona.image_url" :src="pm.persona.image_url" :alt="pm.persona.name" size="md" />
                <UAvatar v-else :text="pm.persona.name[0]" size="md" />
              </NuxtLink>
              <div>
                <NuxtLink :to="`/personas/${pm.persona.slug || pm.persona.id}`" class="font-semibold hover:text-primary transition-colors">{{ pm.persona.name }}</NuxtLink>
                <p class="text-xs text-muted">{{ pm.events.length }} event{{ pm.events.length !== 1 ? 's' : '' }}</p>
              </div>
              <NuxtLink :to="`/markets/${pm.persona.slug || pm.persona.id}`" class="ml-auto">
                <UButton variant="outline" size="xs" trailing-icon="i-lucide-arrow-right">View All</UButton>
              </NuxtLink>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <NuxtLink v-for="event in pm.events" :key="event.event_id" :to="`/markets/${pm.persona.slug || pm.persona.id}`">
                <UCard class="h-full hover:ring-primary/50 hover:ring-1 transition-all" :ui="{ body: 'sm:p-4' }">
                  <div class="flex items-start gap-3">
                    <img v-if="event.image" :src="event.image" :alt="event.title" class="size-10 rounded-md object-cover shrink-0" />
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 mb-1">
                        <UBadge v-if="event.status !== 'active'" color="neutral" variant="subtle" size="xs">{{ event.status }}</UBadge>
                      </div>
                      <p class="text-sm font-medium truncate">{{ event.title }}</p>
                      <p v-if="event.strike_date || event.end_date" class="text-xs text-muted mt-0.5">{{ formatDate(event.strike_date || event.end_date) }}</p>
                      <div v-if="event.top_terms.length > 0" class="flex flex-wrap gap-1.5 mt-2">
                        <UBadge v-for="term in event.top_terms" :key="term.term" variant="subtle" color="neutral" size="xs">{{ term.term }} &middot; {{ term.price }}&cent;</UBadge>
                        <UBadge v-if="event.market_count > event.top_terms.length" variant="outline" color="neutral" size="xs">+{{ event.market_count - event.top_terms.length }} more</UBadge>
                      </div>
                    </div>
                  </div>
                </UCard>
              </NuxtLink>
            </div>
          </div>
        </div>
      </div>

      <!-- Polymarket section -->
      <div v-if="filteredPolyByPersona.length > 0">
        <div class="flex items-center gap-2 mb-5">
          <h2 class="text-lg font-semibold">Polymarket</h2>
          <UBadge color="primary" variant="subtle" size="xs">{{ filteredPolyByPersona.reduce((s, pm) => s + pm.events.length, 0) }}</UBadge>
        </div>
        <div class="space-y-8">
          <div v-for="pm in filteredPolyByPersona" :key="pm.persona.id">
            <div class="flex items-center gap-3 mb-3">
              <NuxtLink :to="`/personas/${pm.persona.slug || pm.persona.id}`">
                <UAvatar v-if="pm.persona.image_url" :src="pm.persona.image_url" :alt="pm.persona.name" size="md" />
                <UAvatar v-else :text="pm.persona.name[0]" size="md" />
              </NuxtLink>
              <div>
                <NuxtLink :to="`/personas/${pm.persona.slug || pm.persona.id}`" class="font-semibold hover:text-primary transition-colors">{{ pm.persona.name }}</NuxtLink>
                <p class="text-xs text-muted">{{ pm.events.length }} event{{ pm.events.length !== 1 ? 's' : '' }}</p>
              </div>
              <NuxtLink :to="`/markets/${pm.persona.slug || pm.persona.id}`" class="ml-auto">
                <UButton variant="outline" size="xs" trailing-icon="i-lucide-arrow-right">View All</UButton>
              </NuxtLink>
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
              <NuxtLink v-for="event in pm.events" :key="event.event_id" :to="`/markets/${pm.persona.slug || pm.persona.id}`">
                <UCard class="h-full hover:ring-primary/50 hover:ring-1 transition-all" :ui="{ body: 'sm:p-4' }">
                  <div class="flex items-start gap-3">
                    <img v-if="event.image" :src="event.image" :alt="event.title" class="size-10 rounded-md object-cover shrink-0" />
                    <div class="flex-1 min-w-0">
                      <div class="flex items-center gap-2 mb-1">
                        <UBadge v-if="event.status !== 'active'" color="neutral" variant="subtle" size="xs">{{ event.status }}</UBadge>
                      </div>
                      <p class="text-sm font-medium truncate">{{ event.title }}</p>
                      <p v-if="event.strike_date || event.end_date" class="text-xs text-muted mt-0.5">{{ formatDate(event.strike_date || event.end_date) }}</p>
                      <div v-if="event.top_terms.length > 0" class="flex flex-wrap gap-1.5 mt-2">
                        <UBadge v-for="term in event.top_terms" :key="term.term" variant="subtle" color="neutral" size="xs">{{ term.term }} &middot; {{ term.price }}&cent;</UBadge>
                        <UBadge v-if="event.market_count > event.top_terms.length" variant="outline" color="neutral" size="xs">+{{ event.market_count - event.top_terms.length }} more</UBadge>
                      </div>
                    </div>
                  </div>
                </UCard>
              </NuxtLink>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Premium upsell -->
    <div class="mt-8 rounded-lg border border-yellow-500/20 bg-yellow-500/5 px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-3">
      <div class="flex-1">
        <p class="text-sm font-medium">Unlock full market analysis</p>
        <p class="text-sm text-muted mt-0.5">
          Subscribe to see mention counts, trends, and detailed analysis for every prediction market.
        </p>
      </div>
      <UButton to="/pricing" icon="i-lucide-crown" variant="soft" color="warning" size="sm">
        View Pricing
      </UButton>
    </div>
  </div>
</template>
