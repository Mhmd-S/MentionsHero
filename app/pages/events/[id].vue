<script setup lang="ts">
import { usePolymarket, type SeriesDetail, type PolymarketEvent, type PersonaEventMarket } from '~/composables/usePolymarket'
import { usePersonas } from '~/composables/usePersonas'

const route = useRoute()
const seriesId = route.params.id as string

const {
  getSeriesDetail, refreshSeries, refreshEvent,
  linkPersonaToSeries, unlinkPersonaFromSeries,
  getEventWithAnalysis,
} = usePolymarket()
const { personas, fetchPersonas } = usePersonas()

const detail = ref<SeriesDetail | null>(null)
const loading = ref(true)
const refreshing = ref(false)
const refreshingEvent = ref(false)

// Event selection
const selectedEventId = ref<string | null>(null)
const eventData = ref<{ event: PolymarketEvent; markets: PersonaEventMarket[] | any[] } | null>(null)
const loadingEvent = ref(false)

// Persona selection
const selectedPersonaId = ref<string | null>(null)

// Link persona modal
const showLinkModal = ref(false)
const linkPersonaId = ref<string | null>(null)
const linking = ref(false)

async function loadDetail() {
  loading.value = true
  try {
    detail.value = await getSeriesDetail(seriesId)
    if (detail.value?.events.length && !selectedEventId.value) {
      // Find the active event (first with non-null end_date in the future, or just the first)
      const now = new Date()
      const activeEvent = detail.value.events.find(e => {
        if (!e.end_date) return true
        return new Date(e.end_date) > now
      })
      selectedEventId.value = activeEvent?.id || detail.value.events[0]?.id || null
    }
    // Set default persona
    if (detail.value?.persona_ids.length && !selectedPersonaId.value) {
      selectedPersonaId.value = detail.value.persona_ids[0]
    }
  } finally {
    loading.value = false
  }
}

async function loadEventData() {
  if (!selectedEventId.value) {
    eventData.value = null
    return
  }
  loadingEvent.value = true
  try {
    eventData.value = await getEventWithAnalysis(
      seriesId,
      selectedEventId.value,
      selectedPersonaId.value || undefined,
    )
  } finally {
    loadingEvent.value = false
  }
}

async function handleRefreshSeries() {
  refreshing.value = true
  try {
    detail.value = await refreshSeries(seriesId)
  } finally {
    refreshing.value = false
  }
}

async function handleRefreshEvent() {
  if (!selectedEventId.value) return
  refreshingEvent.value = true
  try {
    await refreshEvent(seriesId, selectedEventId.value)
    await loadEventData()
  } finally {
    refreshingEvent.value = false
  }
}

async function handleLinkPersona() {
  if (!linkPersonaId.value) return
  linking.value = true
  try {
    await linkPersonaToSeries(seriesId, linkPersonaId.value)
    showLinkModal.value = false
    linkPersonaId.value = null
    await loadDetail()
  } finally {
    linking.value = false
  }
}

async function handleUnlinkPersona(personaId: string) {
  await unlinkPersonaFromSeries(seriesId, personaId)
  if (selectedPersonaId.value === personaId) {
    selectedPersonaId.value = null
  }
  await loadDetail()
}

function getPersonaName(id: string): string {
  const p = personas.value.find(p => p.id === id)
  return p?.name || id.slice(0, 8)
}

// Available personas for linking (not already linked)
const availablePersonas = computed(() => {
  const linkedIds = new Set(detail.value?.persona_ids || [])
  return personas.value.filter(p => !linkedIds.has(p.id))
})

// Persona select options
const personaOptions = computed(() => {
  return (detail.value?.persona_ids || []).map(id => ({
    label: getPersonaName(id),
    value: id,
  }))
})

// Event select options
const eventOptions = computed(() => {
  return (detail.value?.events || []).map(e => ({
    label: e.title || e.slug,
    value: e.id,
  }))
})

// Watch for event/persona changes to reload
watch([selectedEventId, selectedPersonaId], () => {
  loadEventData()
})

onMounted(async () => {
  await fetchPersonas()
  await loadDetail()
})
</script>

<template>
  <div class="max-w-7xl mx-auto">
    <!-- Back button -->
    <NuxtLink to="/events"
      class="inline-flex items-center gap-1 text-gray-500 hover:text-gray-900 dark:hover:text-gray-100 transition-colors mb-4">
      <UIcon name="i-heroicons-chevron-left" class="w-5 h-5" />
      <span class="text-base">Events</span>
    </NuxtLink>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center p-8">
      <UIcon name="i-heroicons-arrow-path" class="w-6 h-6 animate-spin" />
    </div>

    <div v-else-if="!detail" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
      Series not found.
    </div>

    <template v-else>
      <!-- Series header -->
      <div class="flex items-start gap-4 mb-6">
        <img v-if="detail.series.image" :src="detail.series.image" :alt="detail.series.title || ''"
          class="w-16 h-16 rounded-lg object-cover shrink-0" />
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-1">
            <h1 class="text-3xl font-bold truncate">{{ detail.series.title || detail.series.slug }}</h1>
            <UBadge v-if="detail.series.recurrence" color="primary" variant="subtle">{{ detail.series.recurrence }}</UBadge>
            <UBadge v-if="detail.series.closed" color="error" variant="subtle">Closed</UBadge>
            <UBadge v-else-if="detail.series.active" color="success" variant="subtle">Active</UBadge>
          </div>
          <p v-if="detail.series.description" class="text-gray-500 text-sm line-clamp-2">{{ detail.series.description }}</p>
        </div>
        <UButton
          size="sm"
          variant="ghost"
          icon="i-heroicons-arrow-path"
          :loading="refreshing"
          @click="handleRefreshSeries"
        />
      </div>

      <!-- Persona selector -->
      <div class="flex items-center gap-3 mb-4">
        <span class="text-sm font-medium text-gray-600 dark:text-gray-400">Personas:</span>
        <div class="flex items-center gap-1">
          <UBadge
            v-for="pid in detail.persona_ids"
            :key="pid"
            :color="selectedPersonaId === pid ? 'primary' : 'neutral'"
            :variant="selectedPersonaId === pid ? 'solid' : 'soft'"
            class="cursor-pointer"
            @click="selectedPersonaId = selectedPersonaId === pid ? null : pid"
          >
            {{ getPersonaName(pid) }}
            <UIcon
              name="i-heroicons-x-mark"
              class="w-3 h-3 ml-1"
              @click.stop="handleUnlinkPersona(pid)"
            />
          </UBadge>
        </div>
        <UButton size="xs" variant="ghost" icon="i-heroicons-plus" @click="showLinkModal = true">Link Persona</UButton>
      </div>

      <!-- Event selector -->
      <div class="flex items-center gap-3 mb-4">
        <span class="text-sm font-medium text-gray-600 dark:text-gray-400">Event:</span>
        <USelectMenu
          v-if="eventOptions.length > 0"
          v-model="selectedEventId"
          :items="eventOptions"
          placeholder="Select event..."
          class="w-80"
          value-key="value"
          label-key="label"
        />
        <span v-else class="text-sm text-gray-500">No events</span>
        <UButton
          v-if="selectedEventId"
          size="xs"
          variant="ghost"
          icon="i-heroicons-arrow-path"
          :loading="refreshingEvent"
          @click="handleRefreshEvent"
        />
      </div>

      <!-- Markets section -->
      <div v-if="loadingEvent" class="flex items-center justify-center p-8">
        <UIcon name="i-heroicons-arrow-path" class="w-6 h-6 animate-spin" />
      </div>

      <div v-else-if="!eventData || !eventData.markets?.length" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        {{ selectedEventId ? 'No markets for this event.' : 'Select an event to view markets.' }}
      </div>

      <div v-else class="space-y-3">
        <template v-for="m in eventData.markets" :key="m.market?.id">
          <!-- With persona analysis (has term_results) -->
          <template v-if="m.term_results">
            <TermSection
              v-for="term in (m.search_config?.search_terms || []).length ? (m.search_config?.search_terms || []) : ['']"
              :key="`${m.market.id}-${term}`"
              :market-id="m.market.id"
              :question="m.market.question"
              :search-term="term"
              :term-result="m.term_results?.find((tr: any) => tr.search_term === term) || null"
              :outcome-price="m.market.outcome_prices?.[0] || null"
              :persona-id="selectedPersonaId || ''"
              :resolved-outcome="m.market.resolved_outcome"
              :closed-time="m.market.closed_time"
            />
          </template>
          <!-- Without persona analysis (raw market data) -->
          <div v-else class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <div class="flex items-center justify-between gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-800/50">
              <span class="text-sm font-medium truncate flex-1">{{ m.question || m.market?.question || '-' }}</span>
              <div class="flex items-center gap-2 shrink-0">
                <UBadge v-if="m.resolved_outcome || m.market?.resolved_outcome" :color="(m.resolved_outcome || m.market?.resolved_outcome) === 'YES' ? 'success' : 'error'" variant="subtle" size="xs">
                  {{ m.resolved_outcome || m.market?.resolved_outcome }}
                </UBadge>
                <span v-if="m.outcome_prices?.[0] || m.market?.outcome_prices?.[0]" class="text-sm font-semibold text-primary">
                  {{ (parseFloat(m.outcome_prices?.[0] || m.market?.outcome_prices?.[0]) * 100).toFixed(0) }}%
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

    <!-- Link Persona Modal -->
    <UModal v-model:open="showLinkModal">
      <template #content>
        <div class="p-6">
          <h3 class="text-lg font-semibold mb-4">Link Persona to Series</h3>

          <div v-if="availablePersonas.length === 0" class="text-gray-500 text-sm">
            All personas are already linked.
          </div>
          <div v-else class="space-y-2">
            <div
              v-for="p in availablePersonas"
              :key="p.id"
              class="flex items-center gap-2 p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer"
              :class="{ 'ring-2 ring-primary': linkPersonaId === p.id }"
              @click="linkPersonaId = p.id"
            >
              <span class="font-medium text-sm">{{ p.name }}</span>
              <span v-if="p.description" class="text-xs text-gray-500 truncate">{{ p.description }}</span>
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <UButton variant="ghost" @click="showLinkModal = false">Cancel</UButton>
            <UButton :loading="linking" :disabled="!linkPersonaId" @click="handleLinkPersona">Link</UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
