<script setup lang="ts">
import type { SwingAnalysisResult } from '~/composables/usePolymarket'
import type { Persona } from '~/composables/usePersonas'

definePageMeta({ layout: 'admin' })

const { analyzeSwings, listStoredEvents } = usePolymarket()
const { fetchPersonas } = usePersonas()

const loading = ref(false)
const result = ref<SwingAnalysisResult | null>(null)

// Filters
const personas = ref<Persona[]>([])
const events = ref<{ id: string; title: string | null }[]>([])
const selectedPersonaId = ref<string | undefined>()
const selectedEventId = ref<string | undefined>()

// View mode
const viewMode = ref<'spikes' | 'terms'>('spikes')

// Expanded
const expandedTerm = ref<string | null>(null)

// Sort for spikes
const spikeSortBy = ref<'spike_magnitude' | 'spike_time'>('spike_magnitude')
const spikeSortDir = ref<'asc' | 'desc'>('desc')

const sortedSpikes = computed(() => {
  if (!result.value) return []
  const spikes = [...result.value.spikes]
  spikes.sort((a, b) => {
    let aVal: number, bVal: number
    if (spikeSortBy.value === 'spike_magnitude') {
      aVal = Math.abs(a.spike_magnitude)
      bVal = Math.abs(b.spike_magnitude)
    } else {
      aVal = a.spike_time.localeCompare(b.spike_time)
      bVal = 0
      return spikeSortDir.value === 'asc' ? aVal : -aVal
    }
    if (aVal < bVal) return spikeSortDir.value === 'asc' ? -1 : 1
    if (aVal > bVal) return spikeSortDir.value === 'asc' ? 1 : -1
    return 0
  })
  return spikes
})

// Sort for term profiles
const termSortBy = ref<'avg_magnitude' | 'spike_count' | 'max_magnitude'>('avg_magnitude')
const termSortDir = ref<'asc' | 'desc'>('desc')

const sortedProfiles = computed(() => {
  if (!result.value) return []
  const profiles = [...result.value.profiles]
  profiles.sort((a, b) => {
    const aVal = Math.abs(a[termSortBy.value] as number ?? 0)
    const bVal = Math.abs(b[termSortBy.value] as number ?? 0)
    if (aVal < bVal) return termSortDir.value === 'asc' ? -1 : 1
    if (aVal > bVal) return termSortDir.value === 'asc' ? 1 : -1
    return 0
  })
  return profiles
})

function toggleTermSort(field: typeof termSortBy.value) {
  if (termSortBy.value === field) {
    termSortDir.value = termSortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    termSortBy.value = field
    termSortDir.value = 'desc'
  }
}

function sortIcon(active: boolean, dir: 'asc' | 'desc') {
  if (!active) return 'i-lucide-arrow-up-down'
  return dir === 'asc' ? 'i-lucide-arrow-up' : 'i-lucide-arrow-down'
}

onMounted(async () => {
  const [p, e] = await Promise.all([fetchPersonas(), listStoredEvents()])
  personas.value = p
  events.value = e.map((ev: any) => ({ id: ev.id, title: ev.title }))
})

async function handleRun() {
  loading.value = true
  result.value = null
  expandedTerm.value = null
  try {
    result.value = await analyzeSwings({
      persona_id: selectedPersonaId.value,
      event_id: selectedEventId.value,
    })
  } finally {
    loading.value = false
  }
}

function magColor(mag: number): string {
  if (mag > 0.01) return 'text-green-500'
  if (mag < -0.01) return 'text-red-500'
  return 'text-neutral-500'
}

function formatMag(mag: number): string {
  const sign = mag >= 0 ? '+' : ''
  return `${sign}${(mag * 100).toFixed(1)}c`
}

function toggleExpand(term: string) {
  expandedTerm.value = expandedTerm.value === term ? null : term
}
</script>

<template>
  <div class="p-6 max-w-7xl space-y-6">
    <div>
      <h1 class="text-2xl font-bold">Swing Analysis</h1>
      <p class="text-sm text-neutral-500 mt-1">
        Detect price spikes and trace them back to words said in the transcript.
      </p>
    </div>

    <!-- Filters -->
    <div class="flex flex-wrap items-end gap-4">
      <div class="w-56">
        <label class="block text-xs font-medium mb-1">Persona</label>
        <USelectMenu
          v-model="selectedPersonaId"
          :items="[{ label: 'All Personas', value: undefined }, ...personas.map(p => ({ label: p.name, value: p.id }))]"
          value-key="value"
          placeholder="All transcripts"
          class="w-full"
        />
      </div>
      <div class="min-w-96">
        <label class="block text-xs font-medium mb-1">Event</label>
        <USelectMenu
          v-model="selectedEventId"
          :items="[{ label: 'All Events', value: undefined }, ...events.map(e => ({ label: e.title || 'Untitled', value: e.id }))]"
          value-key="value"
          placeholder="All Events"
          class="w-full"
        />
      </div>
      <UButton
        label="Analyze"
        icon="i-lucide-activity"
        :loading="loading"
        @click="handleRun"
      />
    </div>

    <!-- Results -->
    <template v-if="result">
      <!-- Summary -->
      <div class="flex flex-wrap gap-6 text-sm">
        <div>
          <span class="text-neutral-500">Markets:</span>
          <span class="font-medium ml-1">{{ result.total_markets_analyzed }}</span>
        </div>
        <div>
          <span class="text-neutral-500">Briefings:</span>
          <span class="font-medium ml-1">{{ result.total_briefings }}</span>
          <span class="text-neutral-400 ml-1">/ {{ result.total_transcripts_available }}</span>
        </div>
        <div>
          <span class="text-neutral-500">Spikes detected:</span>
          <span class="font-medium ml-1">{{ result.total_spikes_detected }}</span>
        </div>
        <div>
          <span class="text-neutral-500">Terms linked:</span>
          <span class="font-medium ml-1">{{ result.profiles.length }}</span>
        </div>
      </div>

      <!-- View toggle -->
      <div class="flex gap-1">
        <UButton
          :variant="viewMode === 'spikes' ? 'solid' : 'ghost'"
          size="sm"
          label="Spikes"
          icon="i-lucide-zap"
          @click="viewMode = 'spikes'"
        />
        <UButton
          :variant="viewMode === 'terms' ? 'solid' : 'ghost'"
          size="sm"
          label="By Term"
          icon="i-lucide-hash"
          @click="viewMode = 'terms'"
        />
      </div>

      <!-- ============ SPIKES VIEW ============ -->
      <div v-if="viewMode === 'spikes' && sortedSpikes.length" class="space-y-1">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-neutral-200 dark:border-neutral-800 text-left">
                <th class="py-2 pr-3">Market</th>
                <th class="py-2 pr-3 cursor-pointer select-none" @click="spikeSortBy = 'spike_magnitude'; spikeSortDir = spikeSortDir === 'asc' ? 'desc' : 'asc'">
                  <span class="inline-flex items-center gap-1">
                    Spike
                    <UIcon :name="sortIcon(spikeSortBy === 'spike_magnitude', spikeSortDir)" class="size-3" />
                  </span>
                </th>
                <th class="py-2 pr-3">Price</th>
                <th class="py-2 pr-3 cursor-pointer select-none" @click="spikeSortBy = 'spike_time'; spikeSortDir = spikeSortDir === 'asc' ? 'desc' : 'asc'">
                  <span class="inline-flex items-center gap-1">
                    Time
                    <UIcon :name="sortIcon(spikeSortBy === 'spike_time', spikeSortDir)" class="size-3" />
                  </span>
                </th>
                <th class="py-2 pr-3">What Was Said</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(spike, i) in sortedSpikes"
                :key="i"
                class="border-b border-neutral-100 dark:border-neutral-900"
              >
                <td class="py-2 pr-3 text-xs max-w-60 truncate" :title="spike.market_question || ''">
                  {{ spike.market_question }}
                </td>
                <td class="py-2 pr-3 font-mono font-semibold whitespace-nowrap" :class="magColor(spike.spike_magnitude)">
                  {{ formatMag(spike.spike_magnitude) }}
                </td>
                <td class="py-2 pr-3 font-mono text-xs text-neutral-500 whitespace-nowrap">
                  {{ (spike.price_before * 100).toFixed(0) }}c → {{ (spike.price_after * 100).toFixed(0) }}c
                </td>
                <td class="py-2 pr-3 font-mono text-xs whitespace-nowrap">{{ spike.spike_time }}</td>
                <td class="py-2 pr-3 text-xs">
                  <div class="text-neutral-600 dark:text-neutral-400">
                    <span v-if="spike.speaker" class="font-semibold text-neutral-800 dark:text-neutral-200">{{ spike.speaker }}: </span>
                    {{ spike.text_before_spike }}
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- ============ TERMS VIEW ============ -->
      <div v-if="viewMode === 'terms' && sortedProfiles.length" class="space-y-1">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-neutral-200 dark:border-neutral-800 text-left">
                <th class="py-2 pr-3">Term</th>
                <th class="py-2 pr-3">Event</th>
                <th class="py-2 pr-3 cursor-pointer select-none" @click="toggleTermSort('spike_count')">
                  <span class="inline-flex items-center gap-1">
                    Spikes
                    <UIcon :name="sortIcon(termSortBy === 'spike_count', termSortDir)" class="size-3" />
                  </span>
                </th>
                <th class="py-2 pr-3 cursor-pointer select-none" @click="toggleTermSort('avg_magnitude')">
                  <span class="inline-flex items-center gap-1">
                    Avg Spike
                    <UIcon :name="sortIcon(termSortBy === 'avg_magnitude', termSortDir)" class="size-3" />
                  </span>
                </th>
                <th class="py-2 pr-3 cursor-pointer select-none" @click="toggleTermSort('max_magnitude')">
                  <span class="inline-flex items-center gap-1">
                    Max Spike
                    <UIcon :name="sortIcon(termSortBy === 'max_magnitude', termSortDir)" class="size-3" />
                  </span>
                </th>
                <th class="py-2 pr-3">Std Dev</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="profile in sortedProfiles" :key="profile.term + profile.event_title">
                <tr
                  class="border-b border-neutral-100 dark:border-neutral-900 cursor-pointer hover:bg-neutral-50 dark:hover:bg-neutral-900/50"
                  @click="toggleExpand(profile.term + profile.event_title)"
                >
                  <td class="py-2 pr-3 font-mono text-xs font-medium">
                    <span class="inline-flex items-center gap-1">
                      <UIcon
                        :name="expandedTerm === (profile.term + profile.event_title) ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
                        class="size-3 text-neutral-400"
                      />
                      {{ profile.term }}
                    </span>
                  </td>
                  <td class="py-2 pr-3 text-xs text-neutral-500 max-w-[200px] truncate">{{ profile.event_title }}</td>
                  <td class="py-2 pr-3">{{ profile.spike_count }}</td>
                  <td class="py-2 pr-3 font-mono" :class="magColor(profile.avg_magnitude)">
                    {{ formatMag(profile.avg_magnitude) }}
                  </td>
                  <td class="py-2 pr-3 font-mono" :class="magColor(profile.max_magnitude)">
                    {{ formatMag(profile.max_magnitude) }}
                  </td>
                  <td class="py-2 pr-3 font-mono text-xs">
                    {{ (profile.consistency * 100).toFixed(1) }}c
                  </td>
                </tr>

                <!-- Expanded: show individual spikes for this term -->
                <tr v-if="expandedTerm === (profile.term + profile.event_title)">
                  <td colspan="6" class="p-4 bg-neutral-50 dark:bg-neutral-900/30">
                    <table class="w-full text-xs">
                      <thead>
                        <tr class="border-b border-neutral-200 dark:border-neutral-800 text-left">
                          <th class="py-1 pr-3">Spike</th>
                          <th class="py-1 pr-3">Price</th>
                          <th class="py-1 pr-3">Time</th>
                          <th class="py-1 pr-3">Speaker</th>
                          <th class="py-1 pr-3">What Was Said</th>
                          <th class="py-1 pr-3">Briefing</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr
                          v-for="(s, si) in profile.spikes"
                          :key="si"
                          class="border-b border-neutral-100 dark:border-neutral-900"
                        >
                          <td class="py-1 pr-3 font-mono font-medium" :class="magColor(s.spike_magnitude)">
                            {{ formatMag(s.spike_magnitude) }}
                          </td>
                          <td class="py-1 pr-3 font-mono text-neutral-500">
                            {{ (s.price_before * 100).toFixed(0) }} → {{ (s.price_after * 100).toFixed(0) }}c
                          </td>
                          <td class="py-1 pr-3 font-mono">{{ s.transcript_time }}</td>
                          <td class="py-1 pr-3">{{ s.speaker }}</td>
                          <td class="py-1 pr-3 max-w-md">
                            <div class="line-clamp-3 text-neutral-600 dark:text-neutral-400">
                              {{ s.text_before_spike.slice(0, 300) }}
                            </div>
                          </td>
                          <td class="py-1 pr-3 text-neutral-500 max-w-[150px] truncate">
                            {{ s.transcript_name }}
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>

      <div v-if="(viewMode === 'spikes' && !sortedSpikes.length) || (viewMode === 'terms' && !sortedProfiles.length)" class="text-center py-8 text-neutral-500">
        No spike data found. Markets may not have enough price history overlapping with briefing times.
      </div>
    </template>

    <!-- Empty state -->
    <div v-else-if="!loading" class="text-center py-12 text-neutral-500">
      <UIcon name="i-lucide-activity" class="size-12 mx-auto mb-3 opacity-50" />
      <p>Select filters and analyze to detect price spikes and trace them to words.</p>
      <p class="text-xs mt-1">Uses Gemini to match transcripts to events and infer timing.</p>
    </div>
  </div>
</template>
