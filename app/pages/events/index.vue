<script setup lang="ts">
import { usePolymarket, type PolymarketSeries, type GammaSeriesResult } from '~/composables/usePolymarket'
import { usePersonas } from '~/composables/usePersonas'

const { fetchAllSeries, addSeriesBySlug, deleteSeries, searchSeries, extractSlugFromInput } = usePolymarket()
const { personas, fetchPersonas } = usePersonas()

const seriesList = ref<PolymarketSeries[]>([])
const loading = ref(true)

// Add Series modal
const showAddModal = ref(false)
const addInput = ref('')
const adding = ref(false)
const searchResults = ref<GammaSeriesResult[]>([])
const searching = ref(false)
let searchTimeout: ReturnType<typeof setTimeout> | null = null

async function loadSeries() {
  loading.value = true
  try {
    seriesList.value = await fetchAllSeries()
  } finally {
    loading.value = false
  }
}

function handleSearchInput() {
  if (searchTimeout) clearTimeout(searchTimeout)
  const q = addInput.value.trim()
  if (!q || q.length < 2) {
    searchResults.value = []
    return
  }
  searchTimeout = setTimeout(async () => {
    searching.value = true
    try {
      searchResults.value = await searchSeries(q)
    } finally {
      searching.value = false
    }
  }, 400)
}

async function handleAddBySlug() {
  const slug = extractSlugFromInput(addInput.value)
  if (!slug) return
  adding.value = true
  try {
    const result = await addSeriesBySlug(slug)
    if (result) {
      showAddModal.value = false
      addInput.value = ''
      searchResults.value = []
      await loadSeries()
    } else {
      alert('Failed to add series. Check the slug and try again.')
    }
  } finally {
    adding.value = false
  }
}

async function handleAddFromSearch(result: GammaSeriesResult) {
  adding.value = true
  try {
    const added = await addSeriesBySlug(result.slug)
    if (added) {
      showAddModal.value = false
      addInput.value = ''
      searchResults.value = []
      await loadSeries()
    }
  } finally {
    adding.value = false
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

onMounted(async () => {
  await Promise.all([loadSeries(), fetchPersonas()])
})
</script>

<template>
  <div class="max-w-7xl mx-auto">
    <!-- Header -->
    <div class="flex items-center justify-between mb-6">
      <div>
        <h1 class="text-3xl font-bold mb-1">Events</h1>
        <p class="text-gray-500 text-base">Polymarket series, events, and markets</p>
      </div>
      <UButton icon="i-heroicons-plus" @click="showAddModal = true">Add Series</UButton>
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
        :to="`/events/${s.id}`"
        class="block p-4 border rounded-lg hover:border-primary-500 transition-colors cursor-pointer"
      >
        <div class="flex items-start gap-3">
          <img v-if="s.image" :src="s.image" :alt="s.title || ''" class="w-12 h-12 rounded object-cover shrink-0" />
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1">
              <span class="font-semibold truncate">{{ s.title || s.slug }}</span>
              <UBadge v-if="s.recurrence" color="primary" variant="subtle" size="xs">{{ s.recurrence }}</UBadge>
              <UBadge v-if="s.closed" color="error" variant="subtle" size="xs">Closed</UBadge>
              <UBadge v-else-if="s.active" color="success" variant="subtle" size="xs">Active</UBadge>
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
          <h3 class="text-lg font-semibold mb-4">Add Polymarket Series</h3>
          <p class="text-base text-gray-500 mb-4">
            Enter a series slug, URL, or search by keyword.
          </p>
          <UFormField label="Series slug, URL, or search">
            <UInput
              v-model="addInput"
              placeholder="e.g. white-house-press-briefing or search..."
              class="w-full"
              @input="handleSearchInput"
              @keyup.enter="handleAddBySlug()"
            />
          </UFormField>

          <!-- Search results -->
          <div v-if="searching" class="flex items-center justify-center p-4">
            <UIcon name="i-heroicons-arrow-path" class="w-4 h-4 animate-spin" />
          </div>
          <div v-else-if="searchResults.length > 0" class="mt-3 max-h-64 overflow-y-auto space-y-1">
            <div
              v-for="r in searchResults"
              :key="r.id"
              class="flex items-center gap-2 p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer"
              @click="handleAddFromSearch(r)"
            >
              <img v-if="r.image" :src="r.image" class="w-8 h-8 rounded object-cover shrink-0" />
              <div class="flex-1 min-w-0">
                <div class="text-sm font-medium truncate">{{ r.title || r.slug }}</div>
                <div class="text-xs text-gray-500">
                  <span v-if="r.recurrence">{{ r.recurrence }}</span>
                  <span v-if="r.active"> &middot; Active</span>
                </div>
              </div>
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <UButton variant="ghost" @click="showAddModal = false">Cancel</UButton>
            <UButton
              :loading="adding"
              :disabled="!extractSlugFromInput(addInput)"
              @click="handleAddBySlug()"
            >Add</UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
