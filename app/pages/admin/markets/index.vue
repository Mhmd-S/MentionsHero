<script lang="ts">
definePageMeta({ layout: 'admin' })
</script>

<script setup lang="ts">
import { useKalshi, type BrowsedEvent } from '~/composables/useKalshi'
import { usePolymarket, type PolyEvent, type PolySearchResult } from '~/composables/usePolymarket'

const route = useRoute()
const router = useRouter()

// ----- Tab state -----
const activeTab = ref((route.query.tab as string) === 'polymarket' ? 'polymarket' : 'kalshi')

watch(activeTab, (val) => {
  router.replace({ query: { ...route.query, tab: val === 'kalshi' ? undefined : val } })
})

// ----- Kalshi state -----
const { browseEvents } = useKalshi()
const kalshiGrouped = ref<Record<string, BrowsedEvent[]>>({})
const kalshiLoading = ref(false)
const kalshiSearch = ref('')
const categories = ['Politicians', 'Earnings', 'Sports'] as const

function matchesSearch(ev: BrowsedEvent, q: string): boolean {
  if (!q) return true
  const lower = q.toLowerCase()
  return (
    (ev.event_title || '').toLowerCase().includes(lower) ||
    (ev.series_title || '').toLowerCase().includes(lower) ||
    (ev.event_subtitle || '').toLowerCase().includes(lower) ||
    ev.markets.some(m => m.word.toLowerCase().includes(lower))
  )
}

function sortByStrikeDate(events: BrowsedEvent[]): BrowsedEvent[] {
  return [...events].sort((a, b) => {
    const da = a.strike_date ? new Date(a.strike_date).getTime() : 0
    const db = b.strike_date ? new Date(b.strike_date).getTime() : 0
    return db - da
  })
}

const kalshiFiltered = computed(() => {
  const q = kalshiSearch.value.trim()
  const result: Record<string, BrowsedEvent[]> = {}
  for (const cat of categories) {
    const events = kalshiGrouped.value[cat] ?? []
    const matched = sortByStrikeDate(events.filter(ev => matchesSearch(ev, q)))
    if (matched.length) result[cat] = matched
  }
  return result
})

const activeCategories = computed(() =>
  categories.filter(cat => (kalshiFiltered.value[cat]?.length ?? 0) > 0)
)

const kalshiTotalEvents = computed(() =>
  Object.values(kalshiGrouped.value).reduce((sum, arr) => sum + arr.length, 0)
)

const kalshiFilteredCount = computed(() =>
  Object.values(kalshiFiltered.value).reduce((sum, arr) => sum + arr.length, 0)
)

async function loadKalshi() {
  kalshiLoading.value = true
  try {
    kalshiGrouped.value = await browseEvents()
  } finally {
    kalshiLoading.value = false
  }
}

// ----- Polymarket state -----
const { searchEvents, listStoredEvents, addEvent } = usePolymarket()
const polySearch = ref('')
const polySearchResults = ref<PolySearchResult[]>([])
const polySearching = ref(false)
const polyStoredEvents = ref<PolyEvent[]>([])
const polyLoading = ref(false)
const polyAdding = ref<string | null>(null)
const polyMentionsOnly = ref(true)

async function handlePolySearch() {
  const q = polySearch.value.trim()
  if (!q) return
  polySearching.value = true
  try {
    polySearchResults.value = await searchEvents(q, 20, polyMentionsOnly.value)
  } finally {
    polySearching.value = false
  }
}

async function handlePolyAdd(result: PolySearchResult) {
  polyAdding.value = result.slug
  try {
    const detail = await addEvent(result.slug)
    if (detail) {
      // Refresh stored events list
      polyStoredEvents.value = await listStoredEvents()
      // Remove from search results since it's now stored
      polySearchResults.value = polySearchResults.value.filter(r => r.slug !== result.slug)
    }
  } finally {
    polyAdding.value = null
  }
}

async function loadPolymarket() {
  polyLoading.value = true
  try {
    polyStoredEvents.value = await listStoredEvents()
  } finally {
    polyLoading.value = false
  }
}

// Check if a search result is already stored
function isAlreadyStored(slug: string): boolean {
  return polyStoredEvents.value.some(ev => ev.slug === slug)
}

// Split stored events into active vs expired
function isExpired(ev: PolyEvent): boolean {
  if (ev.closed) return true
  if (ev.end_date) {
    const end = new Date(ev.end_date)
    const today = new Date()
    // Only expired if end_date is strictly before today (not same day)
    end.setHours(0, 0, 0, 0)
    today.setHours(0, 0, 0, 0)
    if (end < today) return true
  }
  return false
}

const polyActiveEvents = computed(() => polyStoredEvents.value.filter(ev => !isExpired(ev)))
const polyExpiredEvents = computed(() => polyStoredEvents.value.filter(ev => isExpired(ev)))
const showExpired = ref(false)

// ----- Load on mount -----
onMounted(() => {
  loadKalshi()
  loadPolymarket()
})
</script>

<template>
  <div class="max-w-7xl ">
    <!-- Header -->
    <div class="mb-6 flex flex-col sm:flex-row items-start sm:items-end justify-between gap-4">
      <div>
        <h1 class="text-2xl sm:text-3xl font-bold mb-1">Markets</h1>
        <p class="text-gray-500 text-base">Prediction market events</p>
      </div>
    </div>

    <!-- Tabs -->
    <div class="flex items-center gap-1 mb-6 border-b border-gray-200 dark:border-gray-700">
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors"
        :class="activeTab === 'kalshi'
          ? 'border-primary-500 text-primary-600 dark:text-primary-400'
          : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
        @click="activeTab = 'kalshi'"
      >
        Kalshi
      </button>
      <button
        class="px-4 py-2 text-sm font-medium border-b-2 transition-colors"
        :class="activeTab === 'polymarket'
          ? 'border-primary-500 text-primary-600 dark:text-primary-400'
          : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'"
        @click="activeTab = 'polymarket'"
      >
        Polymarket
      </button>
    </div>

    <!-- ==================== KALSHI TAB ==================== -->
    <div v-if="activeTab === 'kalshi'">
      <div class="mb-4">
        <UInput
          v-model="kalshiSearch"
          icon="i-lucide-search"
          placeholder="Search events & markets..."
          class="w-full sm:w-72"
          :disabled="kalshiLoading"
        />
      </div>

      <div v-if="kalshiLoading" class="flex items-center justify-center p-8">
        <UIcon name="i-lucide-loader" class="w-6 h-6 animate-spin" />
      </div>

      <div v-else-if="kalshiTotalEvents === 0" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        No open mentions events available.
      </div>

      <div v-else-if="kalshiFilteredCount === 0" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        No events matching "{{ kalshiSearch.trim() }}".
      </div>

      <div v-else class="space-y-8">
        <div v-for="cat in activeCategories" :key="cat">
          <h2 class="text-lg font-semibold mb-3">{{ cat }}</h2>
          <div class="space-y-3">
            <NuxtLink
              v-for="ev in kalshiFiltered[cat]"
              :key="ev.event_ticker"
              :to="`/admin/markets/${ev.event_ticker}`"
              class="block p-4 border rounded-lg hover:border-primary-500 transition-colors cursor-pointer"
            >
              <div class="flex items-start gap-3">
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 mb-1">
                    <span class="font-semibold truncate">{{ ev.event_title || ev.series_title }}</span>
                  </div>
                  <div class="flex items-center gap-3 text-xs text-gray-500">
                    <span v-if="ev.strike_date">{{ new Date(ev.strike_date).toLocaleDateString() }}</span>
                    <span v-if="ev.event_subtitle">{{ ev.event_subtitle }}</span>
                    <span>{{ ev.active_market_count }} market{{ ev.active_market_count !== 1 ? 's' : '' }}</span>
                  </div>
                  <div v-if="ev.markets.length" class="flex flex-wrap gap-1.5 mt-2">
                    <UBadge
                      v-for="m in ev.markets.slice(0, 5)"
                      :key="m.ticker"
                      color="neutral"
                      variant="soft"
                      size="xs"
                    >
                      {{ m.word }} <span class="ml-1 opacity-60">{{ m.last_price != null ? m.last_price + '¢' : '' }}</span>
                    </UBadge>
                    <UBadge
                      v-if="ev.markets.length > 5"
                      color="neutral"
                      variant="outline"
                      size="xs"
                    >+{{ ev.markets.length - 5 }} more</UBadge>
                  </div>
                </div>
              </div>
            </NuxtLink>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== POLYMARKET TAB ==================== -->
    <div v-if="activeTab === 'polymarket'">
      <!-- Search Polymarket -->
      <div class="flex items-center gap-2 mb-2">
        <UInput
          v-model="polySearch"
          icon="i-lucide-search"
          placeholder="Search Polymarket events..."
          class="flex-1 sm:max-w-md"
          @keydown.enter="handlePolySearch"
        />
        <UButton :loading="polySearching" @click="handlePolySearch">
          Search
        </UButton>
      </div>
      <label class="flex items-center gap-2 text-sm text-gray-500 mb-6 cursor-pointer">
        <input v-model="polyMentionsOnly" type="checkbox" class="rounded" />
        Mentions markets only
      </label>

      <!-- Search results -->
      <div v-if="polySearchResults.length" class="mb-8">
        <h2 class="text-sm font-medium text-gray-500 mb-3">Search Results</h2>
        <div class="space-y-3">
          <div
            v-for="result in polySearchResults"
            :key="result.slug"
            class="flex items-center gap-3 p-4 border rounded-lg"
          >
            <img
              v-if="result.image"
              :src="result.image"
              class="w-10 h-10 rounded object-cover shrink-0"
              alt=""
            />
            <div class="flex-1 min-w-0">
              <span class="font-semibold text-sm truncate block">{{ result.title || result.slug }}</span>
              <div class="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
                <span>{{ result.market_count }} market{{ result.market_count !== 1 ? 's' : '' }}</span>
                <span v-if="result.end_date">Ends {{ new Date(result.end_date).toLocaleDateString() }}</span>
              </div>
            </div>
            <UButton
              v-if="!isAlreadyStored(result.slug)"
              size="xs"
              icon="i-lucide-plus"
              :loading="polyAdding === result.slug"
              @click="handlePolyAdd(result)"
            >
              Add
            </UButton>
            <UBadge v-else color="success" variant="soft" size="xs">Added</UBadge>
          </div>
        </div>
      </div>

      <!-- No search results message -->
      <div v-if="polySearchResults.length === 0 && polySearching === false && polySearch.trim()" class="mb-6 text-gray-500 text-sm">
        No results found. Try a different search term.
      </div>

      <!-- Stored events -->
      <div>
        <h2 class="text-sm font-medium text-gray-500 mb-3">Stored Events</h2>

        <div v-if="polyLoading" class="flex items-center justify-center p-8">
          <UIcon name="i-lucide-loader" class="w-6 h-6 animate-spin" />
        </div>

        <div v-else-if="polyStoredEvents.length === 0" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
          No Polymarket events added yet. Search above to find and add events.
        </div>

        <template v-else>
          <!-- Active events -->
          <div v-if="polyActiveEvents.length" class="space-y-3">
            <NuxtLink
              v-for="ev in polyActiveEvents"
              :key="ev.id"
              :to="`/admin/markets/poly/${ev.id}`"
              class="block p-4 border rounded-lg hover:border-primary-500 transition-colors cursor-pointer"
            >
              <div class="flex items-center gap-3">
                <img
                  v-if="ev.image"
                  :src="ev.image"
                  class="w-10 h-10 rounded object-cover shrink-0"
                  alt=""
                />
                <div class="flex-1 min-w-0">
                  <span class="font-semibold truncate block">{{ ev.title || ev.slug }}</span>
                  <div class="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
                    <span>{{ ev.market_count ?? 0 }} market{{ (ev.market_count ?? 0) !== 1 ? 's' : '' }}</span>
                    <span v-if="ev.end_date">Ends {{ new Date(ev.end_date).toLocaleDateString() }}</span>
                  </div>
                </div>
              </div>
            </NuxtLink>
          </div>

          <div v-else class="text-gray-500 text-sm p-4 border border-dashed rounded-lg">
            No active events. All stored events have expired.
          </div>

          <!-- Expired events toggle -->
          <div v-if="polyExpiredEvents.length" class="mt-6">
            <button
              class="flex items-center gap-2 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
              @click="showExpired = !showExpired"
            >
              <UIcon
                name="i-lucide-chevron-right"
                class="w-4 h-4 transition-transform"
                :class="{ 'rotate-90': showExpired }"
              />
              Expired events ({{ polyExpiredEvents.length }})
            </button>

            <div v-if="showExpired" class="space-y-3 mt-3">
              <NuxtLink
                v-for="ev in polyExpiredEvents"
                :key="ev.id"
                :to="`/admin/markets/poly/${ev.id}`"
                class="block p-4 border rounded-lg hover:border-primary-500 transition-colors cursor-pointer opacity-60"
              >
                <div class="flex items-center gap-3">
                  <img
                    v-if="ev.image"
                    :src="ev.image"
                    class="w-10 h-10 rounded object-cover shrink-0"
                    alt=""
                  />
                  <div class="flex-1 min-w-0">
                    <span class="font-semibold truncate block">{{ ev.title || ev.slug }}</span>
                    <div class="flex items-center gap-3 text-xs text-gray-500 mt-0.5">
                      <span>{{ ev.market_count ?? 0 }} market{{ (ev.market_count ?? 0) !== 1 ? 's' : '' }}</span>
                        <span v-if="ev.end_date">Ended {{ new Date(ev.end_date).toLocaleDateString() }}</span>
                      <UBadge v-if="ev.closed" color="neutral" variant="soft" size="xs">Closed</UBadge>
                    </div>
                  </div>
                </div>
              </NuxtLink>
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>
