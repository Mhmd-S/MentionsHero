<script lang="ts">
definePageMeta({ layout: 'admin', ssr: false })
</script>

<script setup lang="ts">
import { usePolymarket, type PolyEventDetail, type PolyPersonaMarket, type PolyMarket } from '~/composables/usePolymarket'
import { usePersonas } from '~/composables/usePersonas'
import type { TermResult } from '~/components/TermSection.vue'

const route = useRoute()
const eventId = route.params.id as string

const { getEventDetail, refreshEvent, reanalyzeEvent, toggleEventPublic } = usePolymarket()
const { personas, fetchPersonas } = usePersonas()

const detail = ref<PolyEventDetail | null>(null)
const loading = ref(true)
const refreshing = ref(false)

// Persona selection
const selectedPersonaId = ref<string | undefined>(undefined)

const personaOptions = computed(() =>
  personas.value.map(p => ({ label: p.name, value: p.id }))
)

// Normalize markets to always use PolyPersonaMarket shape
const normalizedMarkets = computed<PolyPersonaMarket[]>(() => {
  if (!detail.value?.markets?.length) return []
  return detail.value.markets.map(m => {
    if ('market' in m) return m as PolyPersonaMarket
    return { market: m as PolyMarket, search_config: null, term_results: [] }
  })
})

// Search & filter state
const searchQuery = ref('')
const sortBy = ref<'mentions' | 'mentions_asc' | 'percentage' | 'alpha' | 'price'>('mentions')
const filterHasMentions = ref(false)

const filterTrend = ref<'all' | 'increasing' | 'decreasing' | 'stable'>('all')

const sortOptions = [
  { label: 'Mentions (most)', value: 'mentions' },
  { label: 'Mentions (least)', value: 'mentions_asc' },
  { label: 'Percentage', value: 'percentage' },
  { label: 'Alphabetical', value: 'alpha' },
  { label: 'Price', value: 'price' },
]
const trendOptions = [
  { label: 'All trends', value: 'all' },
  { label: 'Increasing', value: 'increasing' },
  { label: 'Decreasing', value: 'decreasing' },
  { label: 'Stable', value: 'stable' },
]

interface TermSectionItem {
  market: PolyMarket
  searchTerm: string
  termResult: TermResult | null
  lastPrice: number | null
  result: string | null
  closeTime: string | null
}

const allTermSections = computed<TermSectionItem[]>(() => {
  if (!selectedPersonaId.value) return []
  const items: TermSectionItem[] = []
  for (const m of normalizedMarkets.value) {
    const terms = m.search_config?.search_terms?.length
      ? m.search_config.search_terms
      : ['']
    for (const term of terms) {
      const tr = m.term_results?.find(r => r.search_term === term) || null
      items.push({
        market: m.market,
        searchTerm: term,
        termResult: tr,
        lastPrice: m.market.last_trade_price != null ? m.market.last_trade_price * 100 : null,
        result: m.market.result ?? null,
        closeTime: m.market.closed_time ?? null,
      })
    }
  }
  return items
})

const filteredAndSortedSections = computed(() => {
  let items = [...allTermSections.value]

  if (searchQuery.value.trim()) {
    const q = searchQuery.value.trim().toLowerCase()
    items = items.filter(i =>
      i.market.question?.toLowerCase().includes(q) ||
      i.searchTerm?.toLowerCase().includes(q)
    )
  }

  if (filterHasMentions.value) {
    items = items.filter(i => (i.termResult?.total_mentions ?? 0) > 0)
  }

  if (filterTrend.value !== 'all') {
    items = items.filter(i => (i.termResult?.trend ?? 'stable') === filterTrend.value)
  }

  items.sort((a, b) => {
    switch (sortBy.value) {
      case 'mentions':
        return (b.termResult?.total_mentions ?? 0) - (a.termResult?.total_mentions ?? 0)
      case 'mentions_asc':
        return (a.termResult?.total_mentions ?? 0) - (b.termResult?.total_mentions ?? 0)
      case 'percentage':
        return (b.termResult?.percentage ?? 0) - (a.termResult?.percentage ?? 0)
      case 'alpha':
        return a.searchTerm.localeCompare(b.searchTerm)
      case 'price':
        return (b.lastPrice ?? 0) - (a.lastPrice ?? 0)
      default:
        return 0
    }
  })

  return items
})

const filteredMarkets = computed(() => {
  const q = searchQuery.value.trim().toLowerCase()
  if (!q) return normalizedMarkets.value
  return normalizedMarkets.value.filter(m =>
    m.market.question?.toLowerCase().includes(q)
  )
})

async function loadDetail() {
  loading.value = true
  try {
    detail.value = await getEventDetail(eventId, selectedPersonaId.value || undefined)
  } finally {
    loading.value = false
  }
}

async function handleRefresh() {
  refreshing.value = true
  try {
    await refreshEvent(eventId)
    if (selectedPersonaId.value) {
      await reanalyzeEvent(eventId, selectedPersonaId.value)
    }
    detail.value = await getEventDetail(eventId, selectedPersonaId.value || undefined)
  } finally {
    refreshing.value = false
  }
}

const showPublic = computed(() => detail.value?.event?.show_public ?? false)

async function handleTogglePublic() {
  if (!eventId) return
  const newVal = !showPublic.value
  const ok = await toggleEventPublic(eventId, newVal)
  if (ok && detail.value?.event) {
    detail.value.event.show_public = newVal
  }
}

watch(selectedPersonaId, () => {
  if (detail.value) loadDetail()
})

onMounted(async () => {
  await fetchPersonas()
  await loadDetail()
})
</script>

<template>
  <div class="max-w-7xl">
    <!-- Back button -->
    <NuxtLink to="/admin/markets?tab=polymarket"
      class="inline-flex items-center gap-1 text-gray-500 hover:text-gray-900 dark:hover:text-gray-100 transition-colors mb-4">
      <UIcon name="i-lucide-chevron-left" class="w-5 h-5" />
      <span class="text-base">Markets</span>
    </NuxtLink>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center p-8">
      <UIcon name="i-lucide-loader" class="w-6 h-6 animate-spin" />
    </div>

    <div v-else-if="!detail" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
      Event not found.
    </div>

    <template v-else>
      <!-- Event header -->
      <div class="flex items-start gap-4 mb-6">
        <img v-if="detail.event.image" :src="detail.event.image" class="w-12 h-12 rounded object-cover shrink-0"
          alt="" />
        <div class="flex-1 min-w-0">
          <h1 class="text-2xl sm:text-3xl font-bold truncate mb-1">{{ detail.event.title || detail.event.slug }}</h1>
          <div class="flex items-center gap-3 text-sm text-gray-500">
            <UBadge color="info" variant="soft" size="xs">Polymarket</UBadge>
            <span v-if="detail.event.end_date">Ends {{ new Date(detail.event.end_date).toLocaleDateString() }}</span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <UButton
            size="xs"
            :variant="showPublic ? 'solid' : 'outline'"
            :icon="showPublic ? 'i-lucide-eye' : 'i-lucide-eye-off'"
            :color="showPublic ? 'primary' : 'neutral'"
            @click="handleTogglePublic"
          >
            {{ showPublic ? 'Public' : 'Hidden' }}
          </UButton>
          <UButton size="xs" variant="ghost" icon="i-lucide-refresh-cw" :loading="refreshing" @click="handleRefresh" />
        </div>
      </div>

      <!-- Persona selector -->
      <div class="flex flex-wrap items-center gap-3 mb-4">
        <span class="text-sm font-medium text-gray-600 dark:text-gray-400">Persona:</span>
        <USelectMenu v-model="selectedPersonaId" :items="personaOptions" value-key="value"
          placeholder="Select persona for analysis" class="w-64" />
        <UButton v-if="selectedPersonaId" size="xs" variant="ghost" icon="i-lucide-x"
          @click="selectedPersonaId = undefined" />
      </div>

      <!-- Markets -->
      <div v-if="!normalizedMarkets.length" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        No markets for this event.
      </div>

      <template v-else>
        <!-- Search input (always visible) -->
        <div class="mb-3">
          <UInput v-model="searchQuery" placeholder="Search markets…" icon="i-lucide-search" size="xs"
            class="w-64">
            <template v-if="searchQuery" #trailing>
              <UButton size="xs" variant="ghost" icon="i-lucide-x" @click="searchQuery = ''" />
            </template>
          </UInput>
        </div>

        <!-- Sort & Filter toolbar (only when persona selected) -->
        <div v-if="selectedPersonaId" class="flex flex-wrap items-center gap-2 mb-3">
          <USelectMenu v-model="sortBy" :items="sortOptions" value-key="value" class="w-44" size="xs" />

          <USelectMenu v-model="filterTrend" :items="trendOptions" value-key="value" class="w-36" size="xs" />

          <UButton size="xs" :variant="filterHasMentions ? 'solid' : 'outline'"
            @click="filterHasMentions = !filterHasMentions">
            Has mentions
          </UButton>
          <span class="text-xs text-gray-400 ml-auto">
            {{ filteredAndSortedSections.length }} of {{ allTermSections.length }} terms
          </span>
        </div>

        <div class="gap-5 grid grid-cols-2">
          <!-- With persona analysis: sorted/filtered list -->
          <template v-if="selectedPersonaId">
            <TermSection v-for="item in filteredAndSortedSections" :key="`${item.market.id}-${item.searchTerm}`"
              :market-id="item.market.id" :question="item.market.question" :search-term="item.searchTerm"
              :term-result="item.termResult" :last-price="item.lastPrice" :persona-id="selectedPersonaId"
              :result="item.result" :close-time="item.closeTime" />
            <div v-if="!filteredAndSortedSections.length"
              class="text-gray-500 text-sm p-4 border border-dashed rounded-lg">
              No terms match the current filters.
            </div>
          </template>
          <!-- Without persona: show markets in original order -->
          <template v-else>
            <div v-for="m in filteredMarkets" :key="m.market.id"
              class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
              <div class="flex items-center justify-between gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-800/50">
                <span class="text-sm font-medium truncate flex-1">{{ m.market.question || '—' }}</span>
                <div class="flex items-center gap-2 shrink-0">
                  <UBadge v-if="m.market.result" :color="m.market.result === 'yes' ? 'success' : 'error'"
                    variant="subtle" size="xs">
                    {{ m.market.result.toUpperCase() }}
                  </UBadge>
                  <span v-if="m.market.last_trade_price != null && !m.market.result"
                    class="text-sm font-semibold text-primary">
                    {{ (m.market.last_trade_price * 100).toFixed(0) }}%
                  </span>
                </div>
              </div>
              <div class="px-3 py-2 text-xs text-gray-500">
                Select a persona to see analysis.
              </div>
            </div>
          </template>
        </div>
      </template>
    </template>
  </div>
</template>
