<script setup lang="ts">
import type { TimelineEvent } from '~/composables/useTrading'

const props = defineProps<{
  timelineEvents: TimelineEvent[]
  simulationMetadata: Record<string, any>
}>()

const sortedEvents = computed(() =>
  [...props.timelineEvents].sort((a, b) => a.simulated_timestamp - b.simulated_timestamp)
)

const timeRange = computed(() => {
  if (!sortedEvents.value.length) return { start: 0, end: 1, duration: 1 }
  const start = sortedEvents.value[0].simulated_timestamp
  const end = sortedEvents.value[sortedEvents.value.length - 1].simulated_timestamp
  const duration = Math.max(end - start, 1)
  return { start, end, duration }
})

function getPosition(ts: number): number {
  return ((ts - timeRange.value.start) / timeRange.value.duration) * 100
}

function formatTs(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString()
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`
  const m = Math.floor(seconds / 60)
  const s = Math.round(seconds % 60)
  return `${m}m ${s}s`
}

const eventConfig: Record<string, { color: string; icon: string; label: string }> = {
  pipeline_start: { color: 'bg-gray-400', icon: '', label: 'Start' },
  transcript_download_start: { color: 'bg-blue-400', icon: '', label: 'Transcript DL Start' },
  transcript_download_end: { color: 'bg-blue-600', icon: '', label: 'Transcript DL End' },
  analysis_start: { color: 'bg-amber-400', icon: '', label: 'Analysis Start' },
  sim_buy: { color: 'bg-green-500', icon: '', label: 'Buy' },
  sim_sell: { color: 'bg-red-500', icon: '', label: 'Sell' },
  simulation_complete: { color: 'bg-gray-600', icon: '', label: 'Complete' },
}

function getEventConfig(type: string) {
  return eventConfig[type] || { color: 'bg-gray-300', icon: '', label: type }
}

// Group overlapping events vertically
const pipelinePhases = computed(() => {
  const phases: { label: string; color: string; startPct: number; widthPct: number; duration: string }[] = []
  const events = sortedEvents.value

  const findEvent = (type: string) => events.find(e => e.event_type === type)

  const tdStart = findEvent('transcript_download_start')
  const tdEnd = findEvent('transcript_download_end')
  if (tdStart && tdEnd) {
    phases.push({
      label: 'Transcript Download',
      color: 'bg-blue-200 dark:bg-blue-900',
      startPct: getPosition(tdStart.simulated_timestamp),
      widthPct: getPosition(tdEnd.simulated_timestamp) - getPosition(tdStart.simulated_timestamp),
      duration: formatDuration(tdEnd.simulated_timestamp - tdStart.simulated_timestamp),
    })
  }

  return phases
})

// Trade events (buys and sells)
const tradeEvents = computed(() =>
  sortedEvents.value.filter(e => e.event_type === 'sim_buy' || e.event_type === 'sim_sell')
)
</script>

<template>
  <div class="border rounded-lg p-4">
    <h3 class="text-sm font-semibold mb-3">Simulation Timeline</h3>

    <div v-if="!sortedEvents.length" class="text-sm text-gray-400">No timeline events.</div>

    <div v-else class="space-y-3">
      <!-- Phase bars -->
      <div class="relative h-8 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
        <div
          v-for="(phase, i) in pipelinePhases"
          :key="i"
          :class="[phase.color, 'absolute h-full rounded-full flex items-center justify-center']"
          :style="{ left: phase.startPct + '%', width: Math.max(phase.widthPct, 2) + '%' }"
        >
          <span v-if="phase.widthPct > 15" class="text-[10px] font-medium truncate px-1">
            {{ phase.label }} ({{ phase.duration }})
          </span>
        </div>
      </div>

      <!-- Event dots on a timeline rail -->
      <div class="relative h-10">
        <!-- Rail line -->
        <div class="absolute top-4 left-0 right-0 h-0.5 bg-gray-200 dark:bg-gray-700" />

        <!-- Event markers -->
        <div
          v-for="event in sortedEvents"
          :key="event.id"
          class="absolute -translate-x-1/2 group"
          :style="{ left: getPosition(event.simulated_timestamp) + '%' }"
        >
          <div
            :class="[getEventConfig(event.event_type).color, 'w-3 h-3 rounded-full mt-2.5 cursor-pointer ring-2 ring-white dark:ring-gray-900']"
          />
          <!-- Tooltip -->
          <div class="hidden group-hover:block absolute bottom-full mb-2 left-1/2 -translate-x-1/2 z-10 whitespace-nowrap">
            <div class="bg-gray-900 text-white text-xs rounded px-2 py-1 shadow-lg">
              <div class="font-medium">{{ getEventConfig(event.event_type).label }}</div>
              <div class="text-gray-300">{{ formatTs(event.simulated_timestamp) }}</div>
              <div v-if="event.payload?.term" class="text-gray-300">Term: {{ event.payload.term }}</div>
              <div v-if="event.payload?.price" class="text-gray-300">Price: ${{ event.payload.price.toFixed(3) }}</div>
              <div v-if="event.payload?.pnl_pct != null" :class="event.payload.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'">
                P&L: {{ event.payload.pnl_pct >= 0 ? '+' : '' }}{{ event.payload.pnl_pct.toFixed(1) }}%
              </div>
              <div v-if="event.payload?.duration_s" class="text-gray-300">{{ formatDuration(event.payload.duration_s) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Trade events list -->
      <div v-if="tradeEvents.length" class="space-y-1 pt-2">
        <div v-for="event in tradeEvents" :key="event.id" class="flex items-center gap-2 text-xs">
          <div
            :class="[event.event_type === 'sim_buy' ? 'bg-green-500' : 'bg-red-500', 'w-2 h-2 rounded-full shrink-0']"
          />
          <span class="text-gray-400 w-20 shrink-0">{{ formatTs(event.simulated_timestamp) }}</span>
          <UBadge
            :color="event.event_type === 'sim_buy' ? 'success' : 'error'"
            variant="soft"
            size="xs"
          >{{ event.event_type === 'sim_buy' ? 'BUY' : 'SELL' }}</UBadge>
          <span v-if="event.payload?.term" class="font-medium">{{ event.payload.term }}</span>
          <span v-if="event.payload?.price" class="text-gray-400">${{ event.payload.price.toFixed(3) }}</span>
          <span
            v-if="event.payload?.pnl_pct != null"
            :class="event.payload.pnl_pct >= 0 ? 'text-green-600' : 'text-red-600'"
          >{{ event.payload.pnl_pct >= 0 ? '+' : '' }}{{ event.payload.pnl_pct.toFixed(1) }}%</span>
        </div>
      </div>

      <!-- Legend -->
      <div class="flex flex-wrap gap-3 pt-1 text-[10px] text-gray-400">
        <div class="flex items-center gap-1">
          <div class="w-2 h-2 rounded-full bg-blue-500" /> Transcript Download
        </div>
        <div class="flex items-center gap-1">
          <div class="w-2 h-2 rounded-full bg-amber-500" /> Analysis
        </div>
        <div class="flex items-center gap-1">
          <div class="w-2 h-2 rounded-full bg-green-500" /> Buy
        </div>
        <div class="flex items-center gap-1">
          <div class="w-2 h-2 rounded-full bg-red-500" /> Sell
        </div>
      </div>
    </div>
  </div>
</template>
