<script setup lang="ts">
import { usePolymarket, type SeriesDetail, type PolymarketEvent, type PersonaEventMarket } from '~/composables/usePolymarket'
import { usePersonas } from '~/composables/usePersonas'
import { useFileTree } from '~/composables/useFileTree'

const route = useRoute()
const seriesId = route.params.id as string

const {
  getSeriesDetail, refreshSeries, refreshEvent,
  linkPersonaToSeries, unlinkPersonaFromSeries,
  getEventWithAnalysis, loadPastEvents,
} = usePolymarket()
const { personas, fetchPersonas } = usePersonas()
const { folders, fetchFolders } = useFileTree()
const toast = useToast()

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
const linkFolderId = ref<string | undefined>(undefined)
const linking = ref(false)

// Folder options for the link modal (top-level folders)
const folderOptions = computed(() =>
  folders.value.filter(f => !f.parent_id).map(f => ({ label: f.name, value: f.id }))
)

// Load past events state
const loadingPastEvents = ref(false)

async function loadDetail() {
  loading.value = true
  try {
    detail.value = await getSeriesDetail(seriesId)
    if (detail.value?.events.length && !selectedEventId.value) {
      const now = new Date()
      const activeEvent = detail.value.events.find(e => {
        if (!e.end_date) return true
        return new Date(e.end_date) > now
      })
      selectedEventId.value = activeEvent?.id || detail.value.events[0]?.id || null
    }
    if (detail.value?.persona_ids.length && !selectedPersonaId.value) {
      selectedPersonaId.value = detail.value.persona_ids[0] ?? null
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
    await linkPersonaToSeries(seriesId, linkPersonaId.value, linkFolderId.value)
    showLinkModal.value = false
    linkPersonaId.value = null
    linkFolderId.value = undefined
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

async function handleLoadPastEvents() {
  loadingPastEvents.value = true
  try {
    const result = await loadPastEvents(seriesId)
    if (result) {
      toast.add({ title: `Added ${result.added} past events`, description: `${result.total_matching} matching`, color: 'info' })
      if (result.detail) {
        detail.value = result.detail
      } else {
        await loadDetail()
      }
    }
  } finally {
    loadingPastEvents.value = false
  }
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

// Event select options: show date for closed, title for active. Active first, then closed by end_date desc.
const eventOptions = computed(() => {
  const events = detail.value?.events || []
  const now = new Date()

  const sorted = [...events].sort((a, b) => {
    const aActive = !a.end_date || new Date(a.end_date) > now
    const bActive = !b.end_date || new Date(b.end_date) > now
    if (aActive && !bActive) return -1
    if (!aActive && bActive) return 1
    const aDate = a.end_date ? new Date(a.end_date).getTime() : 0
    const bDate = b.end_date ? new Date(b.end_date).getTime() : 0
    return bDate - aDate
  })

  return sorted.map(e => {
    const isActive = !e.end_date || new Date(e.end_date) > now
    if (isActive) {
      return { label: e.title || e.slug, value: e.id }
    }
    const dateStr = e.end_date ? new Date(e.end_date).toLocaleDateString() : 'closed'
    return { label: dateStr, value: e.id }
  })
})

// Watch for event/persona changes to reload
watch([selectedEventId, selectedPersonaId], () => {
  loadEventData()
})

onMounted(async () => {
  await Promise.all([fetchPersonas(), fetchFolders()])
  await loadDetail()
  // Automatically backfill past events from Gamma (re-associates orphaned events too)
  handleLoadPastEvents()
})
</script>

<template>
  <div class="max-w-6xl mx-auto">
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
          :model-value="selectedEventId ?? undefined"
          :items="eventOptions"
          placeholder="Select event..."
          class="w-64"
          value-key="value"
          label-key="label"
          @update:model-value="selectedEventId = $event ?? null"
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
          <div v-else class="space-y-4">
            <div class="space-y-2">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Persona</label>
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

            <div class="space-y-1">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Transcript Folder (optional)</label>
              <USelectMenu
                v-model="linkFolderId"
                :items="folderOptions"
                value-key="value"
                placeholder="All transcripts"
                class="w-full"
              />
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
