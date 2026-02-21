<script setup lang="ts">
import { useKalshi, type KalshiSeries, type DiscoveredSeries } from '~/composables/useKalshi'
import { usePersonas } from '~/composables/usePersonas'

const { fetchAllSeries, addSeriesByTicker, deleteSeries, discoverSeries } = useKalshi()
const { personas, fetchPersonas } = usePersonas()

const seriesList = ref<KalshiSeries[]>([])
const loading = ref(true)

// Add Series modal
const showAddModal = ref(false)
const adding = ref<string | null>(null)
const discovered = ref<DiscoveredSeries[]>([])
const loadingDiscovery = ref(false)
const filterText = ref('')

// Tag filtering (Mentions sub-tags: Politicians, Earnings, Sports)
const selectedTag = ref<string | null>(null)
const tagOptions = [
  { label: 'All', value: '' },
  { label: 'Politicians', value: 'Politicians' },
  { label: 'Earnings', value: 'Earnings' },
  { label: 'Sports', value: 'Sports' },
]

const addedTickers = computed(() => new Set(seriesList.value.map(s => s.ticker)))

const filteredDiscovered = computed(() => {
  const q = filterText.value.toLowerCase().trim()
  const list = discovered.value.filter(d => !addedTickers.value.has(d.ticker))
  if (!q) return list
  return list.filter(d =>
    (d.title || '').toLowerCase().includes(q) ||
    d.ticker.toLowerCase().includes(q)
  )
})

async function loadSeries() {
  loading.value = true
  try {
    seriesList.value = await fetchAllSeries()
  } finally {
    loading.value = false
  }
}

async function openAddModal() {
  showAddModal.value = true
  filterText.value = ''
  if (discovered.value.length === 0) {
    await loadDiscovery()
  }
}

async function loadDiscovery() {
  loadingDiscovery.value = true
  try {
    const tags = selectedTag.value ? [selectedTag.value] : undefined
    discovered.value = await discoverSeries(tags)
  } finally {
    loadingDiscovery.value = false
  }
}

async function handleSelectSeries(item: DiscoveredSeries) {
  if (addedTickers.value.has(item.ticker) || adding.value) return
  adding.value = item.ticker
  try {
    const result = await addSeriesByTicker(item.ticker)
    if (result) {
      showAddModal.value = false
      await loadSeries()
    } else {
      alert('Failed to add series. Try again.')
    }
  } finally {
    adding.value = null
  }
}

async function handleDelete(id: string, title: string | null) {
  if (!confirm(`Delete series "${title || 'Untitled'}"?`)) return
  await deleteSeries(id)
  await loadSeries()
}

function getPersonaName(id: string): string {
  const p = personas.value.find(p => p.id === id)
  return p?.name || id.slice(0, 8)
}

function statusColor(status: string) {
  if (status === 'active') return 'success'
  if (['closed', 'determined', 'finalized'].includes(status)) return 'error'
  return 'neutral'
}

watch(selectedTag, () => {
  loadDiscovery()
})

onMounted(async () => {
  await Promise.all([loadSeries(), fetchPersonas()])
})
</script>

<template>
  <div class="max-w-7xl mx-auto">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-3xl font-bold mb-1">Markets</h1>
        <p class="text-gray-500 text-base">Kalshi mentions series and markets</p>
      </div>
      <UButton icon="i-heroicons-plus" @click="openAddModal">Add Series</UButton>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center p-8">
      <UIcon name="i-heroicons-arrow-path" class="w-6 h-6 animate-spin" />
    </div>

    <!-- Empty state -->
    <div v-else-if="seriesList.length === 0" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
      No series added yet. Click "Add Series" to get started.
    </div>

    <!-- Series cards -->
    <div v-else class="space-y-3">
      <NuxtLink
        v-for="s in seriesList"
        :key="s.id"
        :to="`/markets/${s.id}`"
        class="block p-4 border rounded-lg hover:border-primary-500 transition-colors cursor-pointer"
      >
        <div class="flex items-start gap-3">
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <span class="font-semibold truncate">{{ s.title || s.ticker }}</span>
              <UBadge v-if="s.frequency" color="primary" variant="subtle" size="xs">{{ s.frequency }}</UBadge>
              <UBadge :color="statusColor(s.status)" variant="subtle" size="xs">{{ s.status }}</UBadge>
            </div>
            <div class="flex items-center gap-3 text-xs text-gray-500">
              <span>{{ s.event_count || 0 }} event{{ (s.event_count || 0) !== 1 ? 's' : '' }}</span>
              <div v-if="s.persona_ids?.length" class="flex items-center gap-1">
                <UBadge
                  v-for="pid in s.persona_ids"
                  :key="pid"
                  color="neutral"
                  variant="soft"
                  size="xs"
                >{{ getPersonaName(pid) }}</UBadge>
              </div>
            </div>
          </div>
          <UButton
            size="xs"
            variant="ghost"
            color="error"
            icon="i-heroicons-trash"
            @click.prevent="handleDelete(s.id, s.title)"
          />
        </div>
      </NuxtLink>
    </div>

    <!-- Add Series Modal -->
    <UModal v-model:open="showAddModal">
      <template #content>
        <div class="p-6">
          <h3 class="text-lg font-semibold mb-4">Add Mentions Series</h3>
          <p class="text-base text-gray-500 mb-3">
            Discover Kalshi mentions series.
          </p>

          <!-- Tag filter -->
          <div class="flex gap-2 mb-3">
            <USelectMenu
              v-model="selectedTag"
              :items="tagOptions"
              placeholder="Filter by tag..."
              class="w-48"
              value-key="value"
            />
          </div>

          <!-- Filter -->
          <UInput
            v-model="filterText"
            placeholder="Filter series..."
            class="w-full mb-3"
            icon="i-heroicons-magnifying-glass"
          />

          <!-- Loading discovery -->
          <div v-if="loadingDiscovery" class="flex items-center justify-center p-8">
            <UIcon name="i-heroicons-arrow-path" class="w-6 h-6 animate-spin" />
          </div>

          <!-- No results -->
          <div v-else-if="filteredDiscovered.length === 0 && discovered.length > 0" class="p-4 text-center text-gray-500 border border-dashed rounded-lg">
            {{ filterText ? 'No series match your filter.' : 'All discovered series are already added.' }}
          </div>

          <!-- Series list -->
          <div v-else-if="filteredDiscovered.length > 0" class="max-h-80 overflow-y-auto space-y-1 border rounded-lg">
            <div
              v-for="d in filteredDiscovered"
              :key="d.ticker"
              class="flex items-center gap-2 p-2.5 hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
              @click="handleSelectSeries(d)"
            >
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium truncate">{{ d.title || d.ticker }}</div>
                <div class="text-xs text-gray-500">
                  {{ d.ticker }}
                </div>
              </div>
              <UButton
                size="xs"
                icon="i-heroicons-plus"
                :loading="adding === d.ticker"
                :disabled="adding !== null && adding !== d.ticker"
                @click.stop="handleSelectSeries(d)"
              >Add</UButton>
            </div>
          </div>

          <div class="flex justify-end mt-6">
            <UButton variant="ghost" @click="showAddModal = false">Cancel</UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
