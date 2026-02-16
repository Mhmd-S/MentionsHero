<script setup lang="ts">
import type { SessionDetail } from '~/composables/useTrading'

const props = defineProps<{
  sessions: SessionDetail[]
}>()

function getMeta(session: SessionDetail): Record<string, any> {
  return session.session.simulation_metadata || {}
}

function formatDuration(seconds: number | null | undefined): string {
  if (!seconds) return '0s'
  const s = Math.round(seconds)
  const m = Math.floor(s / 60)
  const rem = s % 60
  if (m > 0) return `${m}m ${rem}s`
  return `${rem}s`
}

// Collect all unique market_ids across sessions for per-market comparison
const allMarketIds = computed(() => {
  const ids = new Set<string>()
  for (const session of props.sessions) {
    const perMarket = getMeta(session).per_market || []
    for (const m of perMarket) {
      if (m.market_id) ids.add(m.market_id)
    }
  }
  return Array.from(ids)
})

function getMarketResult(session: SessionDetail, marketId: string): Record<string, any> | null {
  const perMarket = getMeta(session).per_market || []
  return perMarket.find((m: any) => m.market_id === marketId) || null
}

// Config comparison: find keys that differ
const configKeys = computed(() => {
  const allKeys = new Set<string>()
  for (const session of props.sessions) {
    const config = session.session.config || {}
    for (const key of Object.keys(config)) {
      if (key !== 'market_ids' && key !== 'event_id') allKeys.add(key)
    }
  }
  return Array.from(allKeys)
})

const differingConfigKeys = computed(() =>
  configKeys.value.filter(key => {
    const values = props.sessions.map(s => JSON.stringify((s.session.config || {})[key]))
    return new Set(values).size > 1
  })
)
</script>

<template>
  <div class="space-y-4">
    <h3 class="text-sm font-semibold">Simulation Comparison ({{ sessions.length }} runs)</h3>

    <!-- Summary metrics comparison -->
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-xs text-gray-500 border-b">
            <th class="pb-2 pr-4">Metric</th>
            <th v-for="(session, i) in sessions" :key="session.session.id" class="pb-2 pr-4">
              Run {{ i + 1 }}
              <div class="text-[10px] text-gray-400 font-normal truncate max-w-[120px]">
                {{ session.session.video_title || session.session.id.slice(0, 8) }}
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr class="border-b border-gray-100 dark:border-gray-800">
            <td class="py-2 pr-4 text-xs text-gray-500">Total P&L</td>
            <td
              v-for="session in sessions"
              :key="session.session.id + '-pnl'"
              class="py-2 pr-4 font-medium"
              :class="(getMeta(session).total_pnl_usd || 0) >= 0 ? 'text-green-600' : 'text-red-600'"
            >
              ${{ (getMeta(session).total_pnl_usd || 0).toFixed(2) }}
              ({{ (getMeta(session).total_pnl_pct || 0) >= 0 ? '+' : '' }}{{ (getMeta(session).total_pnl_pct || 0).toFixed(1) }}%)
            </td>
          </tr>
          <tr class="border-b border-gray-100 dark:border-gray-800">
            <td class="py-2 pr-4 text-xs text-gray-500">Win Rate</td>
            <td v-for="session in sessions" :key="session.session.id + '-wr'" class="py-2 pr-4">
              {{ (getMeta(session).win_rate || 0).toFixed(0) }}%
            </td>
          </tr>
          <tr class="border-b border-gray-100 dark:border-gray-800">
            <td class="py-2 pr-4 text-xs text-gray-500">Positions</td>
            <td v-for="session in sessions" :key="session.session.id + '-pos'" class="py-2 pr-4">
              {{ getMeta(session).total_positions || 0 }}
              <span class="text-xs text-gray-400">
                ({{ getMeta(session).winning_positions || 0 }}W / {{ getMeta(session).losing_positions || 0 }}L)
              </span>
            </td>
          </tr>
          <tr class="border-b border-gray-100 dark:border-gray-800">
            <td class="py-2 pr-4 text-xs text-gray-500">Pipeline Time</td>
            <td v-for="session in sessions" :key="session.session.id + '-time'" class="py-2 pr-4">
              {{ formatDuration(getMeta(session).total_pipeline_duration_s) }}
            </td>
          </tr>
          <tr class="border-b border-gray-100 dark:border-gray-800">
            <td class="py-2 pr-4 text-xs text-gray-500">Transcript Download</td>
            <td v-for="session in sessions" :key="session.session.id + '-td'" class="py-2 pr-4">
              {{ formatDuration(getMeta(session).transcript_download_duration_s) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Config differences -->
    <div v-if="differingConfigKeys.length" class="border rounded-lg p-4">
      <h4 class="text-xs font-semibold text-gray-500 mb-2">Config Differences</h4>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs text-gray-500 border-b">
              <th class="pb-2 pr-4">Parameter</th>
              <th v-for="(_, i) in sessions" :key="'cfg-h-' + i" class="pb-2 pr-4">Run {{ i + 1 }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="key in differingConfigKeys" :key="key" class="border-b border-gray-100 dark:border-gray-800">
              <td class="py-1 pr-4 text-xs text-gray-500">{{ key.replace(/_/g, ' ') }}</td>
              <td v-for="session in sessions" :key="session.session.id + '-cfg-' + key" class="py-1 pr-4 font-mono text-xs">
                {{ (session.session.config || {})[key] ?? '-' }}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Per-market comparison -->
    <div v-if="allMarketIds.length" class="border rounded-lg p-4">
      <h4 class="text-xs font-semibold text-gray-500 mb-2">Per-Market P&L</h4>
      <div class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-left text-xs text-gray-500 border-b">
              <th class="pb-2 pr-4">Market</th>
              <th v-for="(_, i) in sessions" :key="'mkt-h-' + i" class="pb-2 pr-4">Run {{ i + 1 }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="marketId in allMarketIds" :key="marketId" class="border-b border-gray-100 dark:border-gray-800">
              <td class="py-1 pr-4 text-xs text-gray-400 font-mono">{{ marketId.slice(0, 8) }}...</td>
              <td v-for="session in sessions" :key="session.session.id + '-mkt-' + marketId" class="py-1 pr-4">
                <template v-if="getMarketResult(session, marketId)">
                  <span
                    class="font-medium"
                    :class="(getMarketResult(session, marketId)!.pnl_pct || 0) >= 0 ? 'text-green-600' : 'text-red-600'"
                  >
                    {{ (getMarketResult(session, marketId)!.pnl_pct || 0) >= 0 ? '+' : '' }}{{ (getMarketResult(session, marketId)!.pnl_pct || 0).toFixed(1) }}%
                  </span>
                </template>
                <span v-else class="text-gray-300">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>
