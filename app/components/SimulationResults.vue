<script setup lang="ts">
import type { SessionDetail } from '~/composables/useTrading'

const props = defineProps<{
  sessionDetail: SessionDetail
}>()

const meta = computed(() => props.sessionDetail.session.simulation_metadata || {})

const pnlColor = computed(() => {
  const pnl = meta.value.total_pnl_usd || 0
  return pnl >= 0 ? 'text-green-600' : 'text-red-600'
})

const pnlBgColor = computed(() => {
  const pnl = meta.value.total_pnl_usd || 0
  return pnl >= 0 ? 'bg-green-50 dark:bg-green-950 border-green-200 dark:border-green-800' : 'bg-red-50 dark:bg-red-950 border-red-200 dark:border-red-800'
})

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return '0s'
  const s = Math.round(seconds)
  const m = Math.floor(s / 60)
  const rem = s % 60
  if (m > 0) return `${m}m ${rem}s`
  return `${rem}s`
}

const perMarket = computed(() => meta.value.per_market || [])

const timingBars = computed(() => {
  const total = meta.value.total_pipeline_duration_s || 1
  const td = meta.value.transcript_download_duration_s || 0
  const an = meta.value.analysis_duration_s || 0
  return [
    { label: 'Transcript Download', value: td, pct: (td / total) * 100, color: 'bg-blue-500' },
    { label: 'Analysis', value: an, pct: (an / total) * 100, color: 'bg-amber-500' },
  ]
})
</script>

<template>
  <div class="space-y-4">
    <!-- P&L Summary -->
    <div :class="['border rounded-lg p-4', pnlBgColor]">
      <div class="flex items-center justify-between mb-3">
        <h3 class="text-sm font-semibold">Simulation P&L</h3>
        <UBadge :color="(meta.total_pnl_usd || 0) >= 0 ? 'success' : 'error'" variant="soft">
          {{ (meta.total_pnl_usd || 0) >= 0 ? 'Profit' : 'Loss' }}
        </UBadge>
      </div>
      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div>
          <div class="text-xs text-gray-500">Total P&L</div>
          <div :class="['text-xl font-bold', pnlColor]">
            ${{ (meta.total_pnl_usd || 0).toFixed(2) }}
          </div>
          <div :class="['text-sm', pnlColor]">
            {{ (meta.total_pnl_pct || 0) >= 0 ? '+' : '' }}{{ (meta.total_pnl_pct || 0).toFixed(1) }}%
          </div>
        </div>
        <div>
          <div class="text-xs text-gray-500">Win Rate</div>
          <div class="text-xl font-bold">{{ (meta.win_rate || 0).toFixed(0) }}%</div>
        </div>
        <div>
          <div class="text-xs text-gray-500">Positions</div>
          <div class="text-xl font-bold">{{ meta.total_positions || 0 }}</div>
          <div class="text-xs text-gray-400">
            <span class="text-green-600">{{ meta.winning_positions || 0 }}W</span>
            /
            <span class="text-red-600">{{ meta.losing_positions || 0 }}L</span>
          </div>
        </div>
        <div>
          <div class="text-xs text-gray-500">Pipeline Time</div>
          <div class="text-xl font-bold">{{ formatDuration(meta.total_pipeline_duration_s) }}</div>
        </div>
      </div>
    </div>

    <!-- Pipeline Timing -->
    <div class="border rounded-lg p-4">
      <h3 class="text-sm font-semibold mb-3">Pipeline Timing</h3>
      <div class="space-y-2">
        <div v-for="bar in timingBars" :key="bar.label" class="flex items-center gap-3">
          <span class="text-xs text-gray-500 w-24 shrink-0">{{ bar.label }}</span>
          <div class="flex-1 bg-gray-100 dark:bg-gray-800 rounded-full h-4 overflow-hidden">
            <div
              :class="[bar.color, 'h-full rounded-full transition-all']"
              :style="{ width: Math.max(bar.pct, 2) + '%' }"
            />
          </div>
          <span class="text-xs text-gray-500 w-16 text-right shrink-0">{{ formatDuration(bar.value) }}</span>
        </div>
      </div>
    </div>

    <!-- Per-Market P&L Table -->
    <div v-if="perMarket.length" class="border rounded-lg p-4">
      <h3 class="text-sm font-semibold mb-3">Per-Market Results</h3>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs text-gray-500 border-b">
              <th class="pb-2 pr-3">Market</th>
              <th class="pb-2 pr-3">Term</th>
              <th class="pb-2 pr-3">Buy</th>
              <th class="pb-2 pr-3">Sell</th>
              <th class="pb-2 pr-3">P&L</th>
              <th class="pb-2">Trigger</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in perMarket" :key="i" class="border-b border-gray-100 dark:border-gray-800">
              <td class="py-2 pr-3 text-xs max-w-[200px] truncate">{{ row.market_id?.slice(0, 8) }}...</td>
              <td class="py-2 pr-3 text-xs font-medium">{{ row.term }}</td>
              <td class="py-2 pr-3">${{ row.buy_price?.toFixed(3) }}</td>
              <td class="py-2 pr-3">${{ row.sell_price?.toFixed(3) }}</td>
              <td
                class="py-2 pr-3 font-medium"
                :class="(row.pnl_pct || 0) >= 0 ? 'text-green-600' : 'text-red-600'"
              >
                {{ (row.pnl_pct || 0) >= 0 ? '+' : '' }}{{ (row.pnl_pct || 0).toFixed(1) }}%
                <span class="text-xs text-gray-400 ml-1">${{ (row.pnl_usd || 0).toFixed(2) }}</span>
              </td>
              <td class="py-2">
                <UBadge
                  :color="row.triggered_by === 'profit_target' ? 'success' : row.triggered_by === 'stop_loss' ? 'error' : 'neutral'"
                  variant="subtle"
                  size="xs"
                >{{ (row.triggered_by || '').replace(/_/g, ' ') }}</UBadge>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Timeline (if available) -->
    <SimulationTimeline
      v-if="sessionDetail.timeline_events?.length"
      :timeline-events="sessionDetail.timeline_events"
      :simulation-metadata="meta"
    />
  </div>
</template>
