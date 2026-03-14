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

// Expanded profile
const expandedTerm = ref<string | null>(null)

// Sort
const sortBy = ref<'edge' | 'mentioned_in' | 'avg_swing_when_mentioned' | 'consistency'>('edge')
const sortDir = ref<'asc' | 'desc'>('desc')

const sortedProfiles = computed(() => {
  if (!result.value) return []
  const profiles = [...result.value.profiles]
  profiles.sort((a, b) => {
    let aVal = a[sortBy.value] ?? 0
    let bVal = b[sortBy.value] ?? 0
    // Sort edge by absolute value
    if (sortBy.value === 'edge') {
      aVal = Math.abs(aVal as number)
      bVal = Math.abs(bVal as number)
    }
    if (aVal < bVal) return sortDir.value === 'asc' ? -1 : 1
    if (aVal > bVal) return sortDir.value === 'asc' ? 1 : -1
    return 0
  })
  return profiles
})

function toggleSort(field: typeof sortBy.value) {
  if (sortBy.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = field
    sortDir.value = 'desc'
  }
}

function sortIcon(field: typeof sortBy.value) {
  if (sortBy.value !== field) return 'i-lucide-arrow-up-down'
  return sortDir.value === 'asc' ? 'i-lucide-arrow-up' : 'i-lucide-arrow-down'
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

function swingColor(swing: number): string {
  if (swing > 0.01) return 'text-green-500'
  if (swing < -0.01) return 'text-red-500'
  return 'text-neutral-500'
}

function formatSwing(swing: number): string {
  const sign = swing >= 0 ? '+' : ''
  return `${sign}${(swing * 100).toFixed(1)}c`
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
        How do market prices move when specific words are said in briefings?
        Measures price swing in the {{ 6 }}h window after each briefing.
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
      <div class="w-56">
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
        label="Analyze Swings"
        icon="i-lucide-activity"
        :loading="loading"
        @click="handleRun"
      />
    </div>

    <!-- Results -->
    <template v-if="result">
      <!-- Summary -->
      <div class="flex gap-6 text-sm">
        <div>
          <span class="text-neutral-500">Markets analyzed:</span>
          <span class="font-medium ml-1">{{ result.total_markets_analyzed }}</span>
        </div>
        <div>
          <span class="text-neutral-500">Briefings matched:</span>
          <span class="font-medium ml-1">{{ result.total_briefings }}</span>
        </div>
        <div>
          <span class="text-neutral-500">Terms with data:</span>
          <span class="font-medium ml-1">{{ result.profiles.length }}</span>
        </div>
      </div>

      <!-- Profiles Table -->
      <div v-if="sortedProfiles.length" class="space-y-1">
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-neutral-200 dark:border-neutral-800 text-left">
                <th class="py-2 pr-3">Term</th>
                <th class="py-2 pr-3">Event</th>
                <th class="py-2 pr-3 cursor-pointer select-none" @click="toggleSort('mentioned_in')">
                  <span class="inline-flex items-center gap-1">
                    Mentioned
                    <UIcon :name="sortIcon('mentioned_in')" class="size-3" />
                  </span>
                </th>
                <th class="py-2 pr-3 cursor-pointer select-none" @click="toggleSort('avg_swing_when_mentioned')">
                  <span class="inline-flex items-center gap-1">
                    Avg Swing (said)
                    <UIcon :name="sortIcon('avg_swing_when_mentioned')" class="size-3" />
                  </span>
                </th>
                <th class="py-2 pr-3">Avg Swing (absent)</th>
                <th class="py-2 pr-3 cursor-pointer select-none" @click="toggleSort('edge')">
                  <span class="inline-flex items-center gap-1">
                    Edge
                    <UIcon :name="sortIcon('edge')" class="size-3" />
                  </span>
                </th>
                <th class="py-2 pr-3">Range</th>
                <th class="py-2 pr-3 cursor-pointer select-none" @click="toggleSort('consistency')">
                  <span class="inline-flex items-center gap-1">
                    Std Dev
                    <UIcon :name="sortIcon('consistency')" class="size-3" />
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              <template v-for="profile in sortedProfiles" :key="profile.term">
                <tr
                  class="border-b border-neutral-100 dark:border-neutral-900 cursor-pointer hover:bg-neutral-50 dark:hover:bg-neutral-900/50"
                  @click="toggleExpand(profile.term)"
                >
                  <td class="py-2 pr-3 font-mono text-xs font-medium">
                    <span class="inline-flex items-center gap-1">
                      <UIcon
                        :name="expandedTerm === profile.term ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
                        class="size-3 text-neutral-400"
                      />
                      {{ profile.term }}
                    </span>
                  </td>
                  <td class="py-2 pr-3 text-xs text-neutral-500 max-w-[200px] truncate">{{ profile.event_title }}</td>
                  <td class="py-2 pr-3">
                    {{ profile.mentioned_in }} / {{ profile.total_briefings }}
                  </td>
                  <td class="py-2 pr-3 font-mono" :class="swingColor(profile.avg_swing_when_mentioned)">
                    {{ formatSwing(profile.avg_swing_when_mentioned) }}
                  </td>
                  <td class="py-2 pr-3 font-mono" :class="swingColor(profile.avg_swing_when_absent)">
                    {{ formatSwing(profile.avg_swing_when_absent) }}
                  </td>
                  <td class="py-2 pr-3 font-mono font-semibold" :class="swingColor(profile.edge)">
                    {{ formatSwing(profile.edge) }}
                  </td>
                  <td class="py-2 pr-3 text-xs text-neutral-500">
                    {{ formatSwing(profile.min_swing) }} → {{ formatSwing(profile.max_swing) }}
                  </td>
                  <td class="py-2 pr-3 font-mono text-xs">
                    {{ (profile.consistency * 100).toFixed(1) }}c
                  </td>
                </tr>

                <!-- Expanded detail -->
                <tr v-if="expandedTerm === profile.term">
                  <td colspan="8" class="p-4 bg-neutral-50 dark:bg-neutral-900/30">
                    <div class="space-y-4">
                      <!-- Co-occurring terms -->
                      <div v-if="profile.top_co_terms.length">
                        <h4 class="text-xs font-semibold uppercase text-neutral-500 mb-2">Co-occurring terms</h4>
                        <div class="flex flex-wrap gap-2">
                          <div
                            v-for="co in profile.top_co_terms"
                            :key="co.term"
                            class="text-xs rounded-md border border-neutral-200 dark:border-neutral-700 px-2 py-1"
                          >
                            <span class="font-mono">{{ co.term }}</span>
                            <span class="text-neutral-400 ml-1">({{ co.co_count }}x)</span>
                            <span class="font-mono ml-1" :class="swingColor(co.avg_combined_swing)">
                              {{ formatSwing(co.avg_combined_swing) }}
                            </span>
                          </div>
                        </div>
                      </div>

                      <!-- Individual briefing swings -->
                      <div v-if="profile.swing_events.length">
                        <h4 class="text-xs font-semibold uppercase text-neutral-500 mb-2">
                          Briefings where mentioned ({{ profile.swing_events.length }})
                        </h4>
                        <table class="w-full text-xs">
                          <thead>
                            <tr class="border-b border-neutral-200 dark:border-neutral-800 text-left">
                              <th class="py-1 pr-3">Date</th>
                              <th class="py-1 pr-3">Briefing</th>
                              <th class="py-1 pr-3">Mentions</th>
                              <th class="py-1 pr-3">Before</th>
                              <th class="py-1 pr-3">After</th>
                              <th class="py-1 pr-3">Swing</th>
                              <th class="py-1 pr-3">Co-terms</th>
                            </tr>
                          </thead>
                          <tbody>
                            <tr
                              v-for="(se, i) in profile.swing_events"
                              :key="i"
                              class="border-b border-neutral-100 dark:border-neutral-900"
                            >
                              <td class="py-1 pr-3">{{ se.transcript_date }}</td>
                              <td class="py-1 pr-3 max-w-[200px] truncate">{{ se.transcript_name }}</td>
                              <td class="py-1 pr-3">{{ se.mention_count }}</td>
                              <td class="py-1 pr-3 font-mono">{{ (se.price_before * 100).toFixed(1) }}c</td>
                              <td class="py-1 pr-3 font-mono">{{ (se.price_after * 100).toFixed(1) }}c</td>
                              <td class="py-1 pr-3 font-mono font-medium" :class="swingColor(se.swing)">
                                {{ formatSwing(se.swing) }}
                              </td>
                              <td class="py-1 pr-3">
                                <span v-for="ct in se.co_terms" :key="ct" class="inline-block text-xs bg-neutral-100 dark:bg-neutral-800 rounded px-1 mr-1">
                                  {{ ct }}
                                </span>
                              </td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </div>

      <div v-else class="text-center py-8 text-neutral-500">
        No swing data found. Markets may not have enough price history overlapping with briefing dates.
      </div>
    </template>

    <!-- Empty state -->
    <div v-else-if="!loading" class="text-center py-12 text-neutral-500">
      <UIcon name="i-lucide-activity" class="size-12 mx-auto mb-3 opacity-50" />
      <p>Select filters and analyze to see how prices move when words are said.</p>
      <p class="text-xs mt-1">Correlates transcript mentions with CLOB price movements.</p>
    </div>
  </div>
</template>
