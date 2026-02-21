<script setup lang="ts">
import { useKalshi, type BrowsedEvent } from '~/composables/useKalshi'

const { browseEvents } = useKalshi()

const grouped = ref<Record<string, BrowsedEvent[]>>({})
const loading = ref(true)
const search = ref('')

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

const filtered = computed(() => {
  const q = search.value.trim()
  const result: Record<string, BrowsedEvent[]> = {}
  for (const cat of categories) {
    const events = grouped.value[cat] ?? []
    const matched = events.filter(ev => matchesSearch(ev, q))
    if (matched.length) result[cat] = matched
  }
  return result
})

const activeCategories = computed(() =>
  categories.filter(cat => (filtered.value[cat]?.length ?? 0) > 0)
)

async function load() {
  loading.value = true
  try {
    grouped.value = await browseEvents()
  } finally {
    loading.value = false
  }
}

const totalEvents = computed(() =>
  Object.values(grouped.value).reduce((sum, arr) => sum + arr.length, 0)
)

const filteredEventCount = computed(() =>
  Object.values(filtered.value).reduce((sum, arr) => sum + arr.length, 0)
)

onMounted(load)
</script>

<template>
  <div class="max-w-7xl mx-auto">
    <!-- Header -->
    <div class="mb-6 flex items-end justify-between gap-4">
      <div>
        <h1 class="text-3xl font-bold mb-1">Markets</h1>
        <p class="text-gray-500 text-base">Kalshi mentions markets</p>
      </div>
      <UInput
        v-model="search"
        icon="i-heroicons-magnifying-glass"
        placeholder="Search events & markets..."
        class="w-72"
        :disabled="loading"
      />
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center p-8">
      <UIcon name="i-heroicons-arrow-path" class="w-6 h-6 animate-spin" />
    </div>

    <!-- Empty state (no data at all) -->
    <div v-else-if="totalEvents === 0" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
      No open mentions events available.
    </div>

    <!-- No search results -->
    <div v-else-if="filteredEventCount === 0" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
      No events matching "{{ search.trim() }}".
    </div>

    <!-- Events grouped by category -->
    <div v-else class="space-y-8">
      <div v-for="cat in activeCategories" :key="cat">
        <h2 class="text-lg font-semibold mb-3">{{ cat }}</h2>
        <div class="space-y-3">
          <NuxtLink
            v-for="ev in filtered[cat]"
            :key="ev.event_ticker"
            :to="`/markets/${ev.event_ticker}`"
            class="block p-4 border rounded-lg hover:border-primary-500 transition-colors cursor-pointer"
          >
            <div class="flex items-start gap-3">
              <div class="flex-1 min-w-0">
                <div class="flex items-center gap-2 mb-1">
                  <span class="font-semibold truncate">{{ ev.event_title || ev.series_title }}</span>
                </div>
                <div class="flex items-center gap-3 text-xs text-gray-500">
                  <span v-if="ev.event_subtitle">{{ ev.event_subtitle }}</span>
                  <span>{{ ev.active_market_count }} market{{ ev.active_market_count !== 1 ? 's' : '' }}</span>
                </div>
                <!-- Top markets preview -->
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
</template>
