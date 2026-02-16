<script setup lang="ts">
import { usePersonas, type Persona } from '~/composables/usePersonas'
import { usePolymarket, type PolymarketSeries } from '~/composables/usePolymarket'
import {
  useTrading,
  type TradingSession, type SessionDetail, type TradingMarket, type ChannelMonitorStatus,
  type PolymarketEvent,
} from '~/composables/useTrading'

const { personas, fetchPersonas } = usePersonas()
const { fetchAllSeries } = usePolymarket()
const {
  getActiveSession, getSessionHistory, startSession, stopSession, getSessionDetail, streamSession,
  getMarketsForSeries, getChannelMonitorStatus,
  startSimulation, getSimulationHistory, compareSimulations, getEventsForSeries, getMarketsForEvent,
} = useTrading()

// === Top-level tab ===
const activeTab = ref('live')

// === Shared state ===
const allSeries = ref<PolymarketSeries[]>([])
const loading = ref(true)

// Channel monitor status
const monitorStatus = ref<ChannelMonitorStatus | null>(null)

// === Live Trading State ===
const activeSessionId = ref<string | null>(null)
const sessionDetail = ref<SessionDetail | null>(null)
const historyList = ref<TradingSession[]>([])
const expandedHistoryId = ref<string | null>(null)
const expandedHistoryDetail = ref<SessionDetail | null>(null)
const starting = ref(false)
const stopping = ref(false)
let stopStream: (() => void) | null = null

// Live form state
const selectedPersonaId = ref<string | undefined>(undefined)
const selectedSeriesId = ref<string | undefined>(undefined)
const youtubeUrl = ref('')
const videoTitle = ref('')
const showAdvanced = ref(false)
const configProfitTarget = ref<number | undefined>(undefined)
const configStopLoss = ref<number | undefined>(undefined)
const configMaxPrice = ref<number | undefined>(undefined)
const configBuyAmount = ref<number | undefined>(undefined)
const configMaxPositions = ref<number | undefined>(undefined)
const configPollInterval = ref<number | undefined>(undefined)

// Live market selection state
const seriesMarkets = ref<TradingMarket[]>([])
const seriesEvent = ref<Record<string, any> | null>(null)
const selectedMarketIds = ref<string[]>([])
const loadingMarkets = ref(false)

// View state: show result of a completed session before resetting to form
const viewingResult = ref(false)

// Log auto-scroll
const logEl = ref<HTMLElement | null>(null)

// === Simulation State ===
const simSessionId = ref<string | null>(null)
const simSessionDetail = ref<SessionDetail | null>(null)
const simHistoryList = ref<TradingSession[]>([])
const simExpandedHistoryId = ref<string | null>(null)
const simExpandedHistoryDetail = ref<SessionDetail | null>(null)
const simStarting = ref(false)
let simStopStream: (() => void) | null = null

// Simulation form state
const simPersonaId = ref<string | undefined>(undefined)
const simSeriesId = ref<string | undefined>(undefined)
const simEventId = ref<string | undefined>(undefined)
const simYoutubeUrl = ref('')
const simVideoTitle = ref('')
const simShowAdvanced = ref(false)
const simConfigProfitTarget = ref<number | undefined>(undefined)
const simConfigStopLoss = ref<number | undefined>(undefined)
const simConfigMaxPrice = ref<number | undefined>(undefined)
const simConfigBuyAmount = ref<number | undefined>(undefined)
const simConfigMaxPositions = ref<number | undefined>(undefined)

// Simulation event/market selection
const simEvents = ref<PolymarketEvent[]>([])
const simMarkets = ref<TradingMarket[]>([])
const simSelectedMarketIds = ref<string[]>([])
const simLoadingEvents = ref(false)
const simLoadingMarkets = ref(false)
const simViewingResult = ref(false)

// Simulation compare
const simCompareMode = ref(false)
const simCompareIds = ref<string[]>([])
const simCompareData = ref<SessionDetail[]>([])
const simComparing = ref(false)

// === Computed ===
const personaOptions = computed(() =>
  personas.value.map(p => ({ label: p.name, value: p.id }))
)

const filteredSeriesOptions = computed(() => {
  if (!selectedPersonaId.value) return []
  return allSeries.value
    .filter(s => s.persona_ids?.includes(selectedPersonaId.value!))
    .map(s => ({ label: s.title || s.slug, value: s.id }))
})

const simFilteredSeriesOptions = computed(() => {
  if (!simPersonaId.value) return []
  return allSeries.value
    .filter(s => s.persona_ids?.includes(simPersonaId.value!))
    .map(s => ({ label: s.title || s.slug, value: s.id }))
})

const simEventOptions = computed(() =>
  simEvents.value.map(e => ({
    label: e.title || e.slug,
    value: e.id,
    description: e.end_date ? `Ends ${new Date(e.end_date).toLocaleDateString()}` : undefined,
  }))
)

const canStart = computed(() =>
  selectedPersonaId.value && selectedSeriesId.value && youtubeUrl.value.trim()
)

const canStartSim = computed(() =>
  simPersonaId.value && simSeriesId.value && simEventId.value && simYoutubeUrl.value.trim()
)

const isActive = computed(() => {
  const status = sessionDetail.value?.session?.status
  return status === 'pending' || status === 'downloading' || status === 'transcribing' || status === 'analyzing'
})

const isSimActive = computed(() => {
  const status = simSessionDetail.value?.session?.status
  return status === 'pending' || status === 'downloading' || status === 'transcribing' || status === 'analyzing'
})

const stageProgress = computed(() => sessionDetail.value?.session?.stage_progress || {})
const simStageProgress = computed(() => simSessionDetail.value?.session?.stage_progress || {})

const statusLabel = computed(() => {
  const status = sessionDetail.value?.session?.status
  const detail = stageProgress.value.status_detail
  if (detail) return detail
  switch (status) {
    case 'pending': return 'Starting...'
    case 'downloading': return 'Downloading audio...'
    case 'transcribing': return 'Transcribing audio...'
    case 'analyzing': return 'Analyzing transcript...'
    default: return status || ''
  }
})

const simStatusLabel = computed(() => {
  const status = simSessionDetail.value?.session?.status
  const detail = simStageProgress.value.status_detail
  if (detail) return detail
  switch (status) {
    case 'pending': return 'Starting simulation...'
    case 'downloading': return 'Downloading transcript...'
    case 'analyzing': return 'Simulating trades...'
    default: return status || ''
  }
})

const elapsedTime = computed(() => {
  const session = sessionDetail.value?.session
  if (!session?.started_at) return null
  const start = new Date(session.started_at).getTime()
  const end = session.ended_at ? new Date(session.ended_at).getTime() : Date.now()
  return Math.floor((end - start) / 1000)
})

const openPositions = computed(() =>
  (sessionDetail.value?.positions || []).filter(p => p.status === 'open')
)

const statusColor = computed(() => {
  const status = sessionDetail.value?.session?.status
  if (status === 'completed') return 'success' as const
  if (status === 'failed') return 'error' as const
  if (status === 'cancelled') return 'warning' as const
  return 'info' as const
})

const isAutoStarted = computed(() => {
  if (!sessionDetail.value?.logs) return false
  return sessionDetail.value.logs.some(l => l.event_type === 'auto_started')
})

// === Methods ===
function formatDuration(seconds: number | null): string {
  if (!seconds) return '0s'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

function truncate(str: string, len: number): string {
  if (str.length <= len) return str
  return str.slice(0, len) + '...'
}

function formatTimestamp(ts: string | null): string {
  if (!ts) return ''
  return new Date(ts).toLocaleString()
}

function parseOutcomePrices(pricesStr: string | null): [number, number] | null {
  if (!pricesStr) return null
  try {
    const arr = JSON.parse(pricesStr)
    if (Array.isArray(arr) && arr.length >= 2) return [parseFloat(arr[0]), parseFloat(arr[1])]
  } catch { /* ignore */ }
  return null
}

function toggleMarket(marketId: string) {
  const idx = selectedMarketIds.value.indexOf(marketId)
  if (idx >= 0) {
    selectedMarketIds.value.splice(idx, 1)
  } else {
    selectedMarketIds.value.push(marketId)
  }
}

function selectAllMarkets() {
  selectedMarketIds.value = seriesMarkets.value
    .filter(m => m.active && !m.closed)
    .map(m => m.id)
}

function deselectAllMarkets() {
  selectedMarketIds.value = []
}

// Simulation market helpers
function simToggleMarket(marketId: string) {
  const idx = simSelectedMarketIds.value.indexOf(marketId)
  if (idx >= 0) {
    simSelectedMarketIds.value.splice(idx, 1)
  } else {
    simSelectedMarketIds.value.push(marketId)
  }
}

function simSelectAllMarkets() {
  simSelectedMarketIds.value = simMarkets.value
    .filter(m => m.search_terms.length > 0)
    .map(m => m.id)
}

function simDeselectAllMarkets() {
  simSelectedMarketIds.value = []
}

// Live streaming
function connectStream(sessionId: string) {
  if (stopStream) stopStream()
  stopStream = streamSession(sessionId, (detail) => {
    sessionDetail.value = detail
    const status = detail.session?.status
    if (status === 'completed' || status === 'failed' || status === 'cancelled') {
      viewingResult.value = true
      if (stopStream) {
        stopStream()
        stopStream = null
      }
      loadHistory()
    }
  })
}

// Simulation streaming
function connectSimStream(sessionId: string) {
  if (simStopStream) simStopStream()
  simStopStream = streamSession(sessionId, (detail) => {
    simSessionDetail.value = detail
    const status = detail.session?.status
    if (status === 'completed' || status === 'failed' || status === 'cancelled') {
      simViewingResult.value = true
      if (simStopStream) {
        simStopStream()
        simStopStream = null
      }
      loadSimHistory()
    }
  })
}

// Live actions
async function handleStart() {
  if (!canStart.value) return
  starting.value = true
  try {
    const config: Record<string, any> = {}
    if (configProfitTarget.value != null) config.profit_target_pct = configProfitTarget.value
    if (configStopLoss.value != null) config.stop_loss_pct = configStopLoss.value
    if (configMaxPrice.value != null) config.max_price_to_buy = configMaxPrice.value
    if (configBuyAmount.value != null) config.buy_amount_usd = configBuyAmount.value
    if (configMaxPositions.value != null) config.max_concurrent_positions = configMaxPositions.value
    if (configPollInterval.value != null) config.price_poll_interval_s = configPollInterval.value

    const activeMarkets = seriesMarkets.value.filter(m => m.active && !m.closed)
    const allSelected = selectedMarketIds.value.length === activeMarkets.length
    const marketIds = allSelected ? [] : selectedMarketIds.value

    const result = await startSession({
      youtube_url: youtubeUrl.value,
      persona_id: selectedPersonaId.value!,
      series_id: selectedSeriesId.value!,
      market_ids: marketIds.length > 0 ? marketIds : undefined,
      video_title: videoTitle.value || undefined,
      config: Object.keys(config).length > 0 ? config : undefined,
    })

    if (result) {
      activeSessionId.value = result.session_id
      viewingResult.value = false
      const detail = await getSessionDetail(result.session_id)
      if (detail) sessionDetail.value = detail
      connectStream(result.session_id)
    }
  } finally {
    starting.value = false
  }
}

async function handleStop() {
  stopping.value = true
  try {
    await stopSession()
  } finally {
    stopping.value = false
  }
}

function handleNewSession() {
  activeSessionId.value = null
  sessionDetail.value = null
  viewingResult.value = false
  youtubeUrl.value = ''
  videoTitle.value = ''
}

async function loadHistory() {
  historyList.value = await getSessionHistory()
}

async function toggleHistoryExpand(sessionId: string) {
  if (expandedHistoryId.value === sessionId) {
    expandedHistoryId.value = null
    expandedHistoryDetail.value = null
    return
  }
  expandedHistoryId.value = sessionId
  expandedHistoryDetail.value = null
  const detail = await getSessionDetail(sessionId)
  expandedHistoryDetail.value = detail
}

// Simulation actions
async function handleStartSim() {
  if (!canStartSim.value) return
  simStarting.value = true
  try {
    const config: Record<string, any> = {}
    if (simConfigProfitTarget.value != null) config.profit_target_pct = simConfigProfitTarget.value
    if (simConfigStopLoss.value != null) config.stop_loss_pct = simConfigStopLoss.value
    if (simConfigMaxPrice.value != null) config.max_price_to_buy = simConfigMaxPrice.value
    if (simConfigBuyAmount.value != null) config.buy_amount_usd = simConfigBuyAmount.value
    if (simConfigMaxPositions.value != null) config.max_concurrent_positions = simConfigMaxPositions.value

    const allMarkets = simMarkets.value.filter(m => m.search_terms.length > 0)
    const allSelected = simSelectedMarketIds.value.length === allMarkets.length
    const marketIds = allSelected ? [] : simSelectedMarketIds.value

    const result = await startSimulation({
      youtube_url: simYoutubeUrl.value,
      persona_id: simPersonaId.value!,
      series_id: simSeriesId.value!,
      event_id: simEventId.value!,
      market_ids: marketIds.length > 0 ? marketIds : undefined,
      video_title: simVideoTitle.value || undefined,
      config: Object.keys(config).length > 0 ? config : undefined,
    })

    if (result) {
      simSessionId.value = result.session_id
      simViewingResult.value = false
      const detail = await getSessionDetail(result.session_id)
      if (detail) simSessionDetail.value = detail
      connectSimStream(result.session_id)
    }
  } finally {
    simStarting.value = false
  }
}

function handleNewSim() {
  simSessionId.value = null
  simSessionDetail.value = null
  simViewingResult.value = false
  simYoutubeUrl.value = ''
  simVideoTitle.value = ''
}

async function loadSimHistory() {
  simHistoryList.value = await getSimulationHistory()
}

async function toggleSimHistoryExpand(sessionId: string) {
  if (simExpandedHistoryId.value === sessionId) {
    simExpandedHistoryId.value = null
    simExpandedHistoryDetail.value = null
    return
  }
  simExpandedHistoryId.value = sessionId
  simExpandedHistoryDetail.value = null
  const detail = await getSessionDetail(sessionId)
  simExpandedHistoryDetail.value = detail
}

function toggleSimCompare(sessionId: string) {
  const idx = simCompareIds.value.indexOf(sessionId)
  if (idx >= 0) {
    simCompareIds.value.splice(idx, 1)
  } else {
    simCompareIds.value.push(sessionId)
  }
}

async function runCompare() {
  if (simCompareIds.value.length < 2) return
  simComparing.value = true
  try {
    simCompareData.value = await compareSimulations(simCompareIds.value)
  } finally {
    simComparing.value = false
  }
}

function historyStatusColor(status: string) {
  if (status === 'completed') return 'success' as const
  if (status === 'failed') return 'error' as const
  if (status === 'cancelled') return 'warning' as const
  if (['downloading', 'transcribing', 'analyzing', 'pending'].includes(status)) return 'info' as const
  return 'neutral' as const
}

// Auto-scroll logs
watch(() => sessionDetail.value?.logs, () => {
  nextTick(() => {
    if (logEl.value) {
      logEl.value.scrollTop = logEl.value.scrollHeight
    }
  })
})

// Reset series and markets when persona changes (live)
watch(selectedPersonaId, () => {
  selectedSeriesId.value = undefined
  seriesMarkets.value = []
  seriesEvent.value = null
  selectedMarketIds.value = []
})

// Load markets when series changes (live)
watch(selectedSeriesId, async (newId) => {
  seriesMarkets.value = []
  seriesEvent.value = null
  selectedMarketIds.value = []
  if (!newId) return

  loadingMarkets.value = true
  try {
    const result = await getMarketsForSeries(newId)
    if (result) {
      seriesEvent.value = result.event
      seriesMarkets.value = result.markets
      selectedMarketIds.value = result.markets
        .filter(m => m.active && !m.closed && m.search_terms.length > 0)
        .map(m => m.id)
    }
  } finally {
    loadingMarkets.value = false
  }
})

// Simulation watchers
watch(simPersonaId, () => {
  simSeriesId.value = undefined
  simEventId.value = undefined
  simEvents.value = []
  simMarkets.value = []
  simSelectedMarketIds.value = []
})

watch(simSeriesId, async (newId) => {
  simEventId.value = undefined
  simEvents.value = []
  simMarkets.value = []
  simSelectedMarketIds.value = []
  if (!newId) return

  simLoadingEvents.value = true
  try {
    simEvents.value = await getEventsForSeries(newId)
  } finally {
    simLoadingEvents.value = false
  }
})

watch(simEventId, async (newId) => {
  simMarkets.value = []
  simSelectedMarketIds.value = []
  if (!newId) return

  simLoadingMarkets.value = true
  try {
    const result = await getMarketsForEvent(newId)
    if (result) {
      simMarkets.value = result.markets
      simSelectedMarketIds.value = result.markets
        .filter(m => m.search_terms.length > 0)
        .map(m => m.id)
    }
  } finally {
    simLoadingMarkets.value = false
  }
})

// Lifecycle
onMounted(async () => {
  loading.value = true
  try {
    await Promise.all([
      fetchPersonas(),
      fetchAllSeries().then(s => { allSeries.value = s }),
      loadHistory(),
      loadSimHistory(),
      getChannelMonitorStatus().then(s => { monitorStatus.value = s }),
    ])

    // Check for active live session
    const active = await getActiveSession()
    if (active) {
      activeSessionId.value = active.id
      const detail = await getSessionDetail(active.id)
      if (detail) sessionDetail.value = detail
      const status = active.status
      if (['pending', 'downloading', 'transcribing', 'analyzing'].includes(status)) {
        connectStream(active.id)
      } else {
        viewingResult.value = true
      }
    }
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  if (stopStream) stopStream()
  if (simStopStream) simStopStream()
})
</script>

<template>
  <div class="max-w-7xl mx-auto">
    <!-- Header -->
    <div class="flex items-center justify-between mb-2">
      <div class="flex items-center gap-3">
        <h1 class="text-3xl font-bold">Trading Bot</h1>
        <UBadge color="success" variant="soft" size="sm">DRY RUN</UBadge>
      </div>
      <!-- Channel Monitor Status -->
      <div v-if="monitorStatus" class="flex items-center gap-2 text-sm">
        <span
          class="inline-block w-2 h-2 rounded-full"
          :class="monitorStatus.running ? 'bg-green-500' : 'bg-gray-400'"
        />
        <span class="text-gray-500">
          Channel Monitor: {{ monitorStatus.running ? `Active (${monitorStatus.watched_personas} channels)` : 'Stopped' }}
        </span>
      </div>
    </div>
    <p class="text-gray-500 text-base mb-6">
      Download &amp; transcribe a YouTube video, detect terms, and trade Polymarket positions.
    </p>

    <div v-if="loading" class="flex items-center justify-center p-12">
      <UIcon name="i-heroicons-arrow-path" class="w-6 h-6 animate-spin" />
    </div>

    <template v-else>
      <!-- Tabs -->
      <UTabs
        v-model="activeTab"
        :items="[
          { label: 'Live Trading', value: 'live' },
          { label: 'Simulation', value: 'simulation' }
        ]"
        class="mb-6"
      />

      <!-- ==================== LIVE TRADING TAB ==================== -->
      <div v-if="activeTab === 'live'">
        <!-- Setup Form (no active session and not viewing a result) -->
        <div v-if="!activeSessionId && !viewingResult" class="space-y-6">
          <div class="border rounded-lg p-6 space-y-4">
            <h2 class="text-lg font-semibold">New Session</h2>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div class="space-y-1">
                <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Persona</label>
                <USelectMenu
                  v-model="selectedPersonaId"
                  :items="personaOptions"
                  value-key="value"
                  placeholder="Select a persona"
                  class="w-full"
                />
              </div>
              <div class="space-y-1">
                <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Series</label>
                <USelectMenu
                  v-model="selectedSeriesId"
                  :items="filteredSeriesOptions"
                  value-key="value"
                  :placeholder="selectedPersonaId ? 'Select a series' : 'Select persona first'"
                  :disabled="!selectedPersonaId"
                  class="w-full"
                />
              </div>
            </div>

            <!-- Market Selection -->
            <div v-if="selectedSeriesId" class="space-y-2">
              <div class="flex items-center justify-between">
                <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Markets to Trade</label>
                <div v-if="seriesMarkets.length > 0" class="flex gap-2">
                  <button type="button" class="text-xs text-primary hover:underline" @click="selectAllMarkets">
                    Select All
                  </button>
                  <button type="button" class="text-xs text-gray-400 hover:underline" @click="deselectAllMarkets">
                    Deselect All
                  </button>
                </div>
              </div>

              <div v-if="seriesEvent" class="text-xs text-gray-400">
                Newest event: {{ seriesEvent.title || seriesEvent.slug }}
              </div>

              <div v-if="loadingMarkets" class="flex items-center gap-2 text-sm text-gray-400 py-2">
                <UIcon name="i-heroicons-arrow-path" class="w-4 h-4 animate-spin" />
                Loading markets...
              </div>

              <div v-else-if="seriesMarkets.length === 0" class="text-sm text-gray-400 py-2">
                No markets found for the newest event in this series.
              </div>

              <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  v-for="market in seriesMarkets"
                  :key="market.id"
                  type="button"
                  class="text-left p-3 rounded-lg border transition-colors"
                  :class="market.closed
                    ? 'opacity-50 cursor-not-allowed border-gray-200 dark:border-gray-700'
                    : selectedMarketIds.includes(market.id)
                      ? 'border-primary ring-2 ring-primary/30 bg-primary/5'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-400'"
                  :disabled="market.closed"
                  @click="!market.closed && toggleMarket(market.id)"
                >
                  <div class="text-sm font-medium mb-1">{{ market.question || market.slug || market.id }}</div>
                  <div class="flex items-center gap-2 flex-wrap">
                    <template v-if="parseOutcomePrices(market.outcome_prices)">
                      <span class="text-xs font-mono text-green-600">
                        YES {{ (parseOutcomePrices(market.outcome_prices)![0] * 100).toFixed(0) }}c
                      </span>
                      <span class="text-xs font-mono text-red-600">
                        NO {{ (parseOutcomePrices(market.outcome_prices)![1] * 100).toFixed(0) }}c
                      </span>
                    </template>
                    <UBadge v-if="market.closed" color="error" variant="subtle" size="xs">Closed</UBadge>
                    <UBadge v-else-if="market.active" color="success" variant="subtle" size="xs">Active</UBadge>
                    <UBadge v-if="market.search_terms.length > 0" color="primary" variant="subtle" size="xs">
                      {{ market.search_terms.length }} terms
                    </UBadge>
                    <UBadge v-else color="warning" variant="subtle" size="xs">No terms</UBadge>
                  </div>
                </button>
              </div>

              <div v-if="seriesMarkets.length > 0" class="text-xs text-gray-400">
                {{ selectedMarketIds.length }} of {{ seriesMarkets.filter(m => m.active && !m.closed).length }} active markets selected
              </div>
            </div>

            <div class="space-y-1">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">YouTube URL</label>
              <UInput v-model="youtubeUrl" placeholder="https://youtube.com/watch?v=..." class="w-full" />
            </div>

            <div class="space-y-1">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Video Title (optional)</label>
              <UInput v-model="videoTitle" placeholder="Auto-detected if left blank" class="w-full" />
            </div>

            <!-- Advanced Config -->
            <div class="border rounded-lg">
              <button
                type="button"
                class="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg"
                @click="showAdvanced = !showAdvanced"
              >
                <span>Advanced Config</span>
                <UIcon :name="showAdvanced ? 'i-heroicons-chevron-up' : 'i-heroicons-chevron-down'" class="w-4 h-4" />
              </button>
              <div v-if="showAdvanced" class="px-3 pb-3 space-y-3">
                <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Profit Target (%)</label>
                    <UInput v-model.number="configProfitTarget" type="number" placeholder="30" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Stop Loss (%)</label>
                    <UInput v-model.number="configStopLoss" type="number" placeholder="20" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Max Buy Price</label>
                    <UInput v-model.number="configMaxPrice" type="number" step="0.01" placeholder="0.90" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Buy Amount (USD)</label>
                    <UInput v-model.number="configBuyAmount" type="number" placeholder="5" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Max Positions</label>
                    <UInput v-model.number="configMaxPositions" type="number" placeholder="10" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Poll Interval (s)</label>
                    <UInput v-model.number="configPollInterval" type="number" placeholder="10" />
                  </div>
                </div>
              </div>
            </div>

            <div class="flex justify-end">
              <UButton :disabled="!canStart" :loading="starting" @click="handleStart">
                Start Session
              </UButton>
            </div>
          </div>
        </div>

        <!-- Live Session -->
        <div v-else-if="isActive && sessionDetail" class="space-y-4">
          <UAlert
            v-if="isAutoStarted"
            color="info"
            variant="subtle"
            title="This session was auto-started by the channel monitor."
            icon="i-heroicons-information-circle"
          />

          <div class="flex items-center justify-between border rounded-lg p-4">
            <div class="flex items-center gap-3">
              <UIcon name="i-heroicons-arrow-path" class="w-5 h-5 animate-spin text-primary" />
              <span class="text-sm font-medium">{{ statusLabel }}</span>
              <span v-if="sessionDetail.session.video_title" class="text-sm text-gray-500">
                &mdash; {{ sessionDetail.session.video_title }}
              </span>
            </div>
            <div class="flex items-center gap-3">
              <span v-if="elapsedTime != null" class="text-xs text-gray-400">{{ formatDuration(elapsedTime) }}</span>
              <UButton size="sm" color="error" variant="soft" :loading="stopping" @click="handleStop">
                Stop Session
              </UButton>
            </div>
          </div>

          <div class="grid grid-cols-3 gap-3">
            <div class="border rounded-lg p-3">
              <div class="text-xs text-gray-500">Terms Detected</div>
              <div class="text-xl font-bold">{{ stageProgress.terms_detected || 0 }}</div>
            </div>
            <div class="border rounded-lg p-3">
              <div class="text-xs text-gray-500">Trades Placed</div>
              <div class="text-xl font-bold">{{ stageProgress.trades_placed || 0 }}</div>
            </div>
            <div class="border rounded-lg p-3">
              <div class="text-xs text-gray-500">Open Positions</div>
              <div class="text-xl font-bold">{{ stageProgress.positions_open || 0 }}</div>
            </div>
          </div>

          <div v-if="stageProgress.transcript_preview" class="border rounded-lg p-3">
            <div class="text-xs text-gray-500 mb-1">Transcript Preview</div>
            <div class="text-sm font-mono bg-gray-50 dark:bg-gray-900 rounded p-2 max-h-40 overflow-y-auto whitespace-pre-wrap">
              {{ stageProgress.transcript_preview }}
            </div>
          </div>

          <div v-if="openPositions.length" class="border rounded-lg p-3">
            <div class="text-xs text-gray-500 mb-2">Open Positions</div>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="text-left text-xs text-gray-500 border-b">
                    <th class="pb-1 pr-3">Token</th>
                    <th class="pb-1 pr-3">Buy Price</th>
                    <th class="pb-1 pr-3">Current</th>
                    <th class="pb-1 pr-3">P&L</th>
                    <th class="pb-1">Status</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="pos in openPositions" :key="pos.id" class="border-b border-gray-100 dark:border-gray-800">
                    <td class="py-1 pr-3 font-mono text-xs">{{ truncate(pos.token_id || '-', 12) }}</td>
                    <td class="py-1 pr-3">${{ pos.buy_price.toFixed(3) }}</td>
                    <td class="py-1 pr-3">${{ pos.current_price.toFixed(3) }}</td>
                    <td class="py-1 pr-3" :class="pos.profit_loss_pct != null && pos.profit_loss_pct >= 0 ? 'text-green-600' : 'text-red-600'">
                      {{ pos.profit_loss_pct != null ? pos.profit_loss_pct.toFixed(1) + '%' : '-' }}
                    </td>
                    <td class="py-1"><UBadge variant="subtle" size="xs">{{ pos.status }}</UBadge></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div v-if="sessionDetail.trades.length" class="border rounded-lg p-3">
            <div class="text-xs text-gray-500 mb-2">Recent Trades</div>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="text-left text-xs text-gray-500 border-b">
                    <th class="pb-1 pr-3">Side</th>
                    <th class="pb-1 pr-3">Term</th>
                    <th class="pb-1 pr-3">Price</th>
                    <th class="pb-1 pr-3">Amount</th>
                    <th class="pb-1 pr-3">Order</th>
                    <th class="pb-1">Trigger</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="trade in sessionDetail.trades.slice(0, 20)" :key="trade.id" class="border-b border-gray-100 dark:border-gray-800">
                    <td class="py-1 pr-3">
                      <UBadge :color="trade.side === 'buy' ? 'success' : 'error'" variant="soft" size="xs">
                        {{ trade.side.toUpperCase() }}
                      </UBadge>
                    </td>
                    <td class="py-1 pr-3 text-xs">{{ trade.detected_term || '-' }}</td>
                    <td class="py-1 pr-3">${{ trade.price.toFixed(3) }}</td>
                    <td class="py-1 pr-3">${{ trade.amount_usd.toFixed(2) }}</td>
                    <td class="py-1 pr-3 font-mono text-xs">{{ truncate(trade.order_id || '-', 10) }}</td>
                    <td class="py-1">
                      <UBadge variant="subtle" size="xs">{{ trade.triggered_by.replace('_', ' ') }}</UBadge>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div v-if="sessionDetail.logs.length" class="border rounded-lg p-3">
            <div class="text-xs text-gray-500 mb-2">Event Log</div>
            <div
              ref="logEl"
              class="text-xs font-mono bg-gray-50 dark:bg-gray-900 rounded p-2 max-h-60 overflow-y-auto space-y-0.5"
            >
              <div v-for="log in [...sessionDetail.logs].reverse()" :key="log.id" class="flex gap-2">
                <span class="text-gray-400 shrink-0">{{ log.created_at ? new Date(log.created_at).toLocaleTimeString() : '' }}</span>
                <span class="text-primary font-medium">{{ log.event_type }}</span>
                <span class="text-gray-500 truncate">{{ JSON.stringify(log.payload).slice(0, 120) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Session Result -->
        <div v-else-if="viewingResult && sessionDetail" class="space-y-4">
          <UAlert
            v-if="isAutoStarted"
            color="info"
            variant="subtle"
            title="This session was auto-started by the channel monitor."
            icon="i-heroicons-information-circle"
          />

          <div class="border rounded-lg p-4 space-y-4">
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-3">
                <UBadge :color="statusColor" variant="soft">{{ sessionDetail.session.status }}</UBadge>
                <span v-if="sessionDetail.session.video_title" class="text-sm text-gray-500">
                  {{ sessionDetail.session.video_title }}
                </span>
              </div>
              <UButton size="sm" @click="handleNewSession">Start New Session</UButton>
            </div>

            <div v-if="sessionDetail.session.error_message" class="text-sm text-red-600 dark:text-red-400">
              {{ sessionDetail.session.error_message }}
            </div>

            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
              <div>
                <div class="text-gray-500 text-xs">Terms Detected</div>
                <div class="font-medium">{{ stageProgress.terms_detected || 0 }}</div>
              </div>
              <div>
                <div class="text-gray-500 text-xs">Trades</div>
                <div class="font-medium">{{ sessionDetail.trades.length }}</div>
              </div>
              <div>
                <div class="text-gray-500 text-xs">Positions</div>
                <div class="font-medium">{{ sessionDetail.positions.length }}</div>
              </div>
              <div>
                <div class="text-gray-500 text-xs">Elapsed</div>
                <div class="font-medium">{{ elapsedTime != null ? formatDuration(elapsedTime) : '-' }}</div>
              </div>
            </div>

            <div v-if="stageProgress.transcript_preview" class="border rounded-lg p-3">
              <div class="text-xs text-gray-500 mb-1">Transcript Preview</div>
              <div class="text-sm font-mono bg-gray-50 dark:bg-gray-900 rounded p-2 max-h-40 overflow-y-auto whitespace-pre-wrap">
                {{ stageProgress.transcript_preview }}
              </div>
            </div>
          </div>

          <div v-if="sessionDetail.positions.length" class="border rounded-lg p-3">
            <div class="text-xs text-gray-500 mb-2">Positions</div>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="text-left text-xs text-gray-500 border-b">
                    <th class="pb-1 pr-3">Token</th>
                    <th class="pb-1 pr-3">Buy</th>
                    <th class="pb-1 pr-3">Close</th>
                    <th class="pb-1 pr-3">P&L</th>
                    <th class="pb-1">Status</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="pos in sessionDetail.positions" :key="pos.id" class="border-b border-gray-100 dark:border-gray-800">
                    <td class="py-1 pr-3 font-mono text-xs">{{ truncate(pos.token_id || '-', 12) }}</td>
                    <td class="py-1 pr-3">${{ pos.buy_price.toFixed(3) }}</td>
                    <td class="py-1 pr-3">${{ pos.current_price.toFixed(3) }}</td>
                    <td class="py-1 pr-3" :class="pos.profit_loss_pct != null && pos.profit_loss_pct >= 0 ? 'text-green-600' : 'text-red-600'">
                      {{ pos.profit_loss_pct != null ? pos.profit_loss_pct.toFixed(1) + '%' : '-' }}
                    </td>
                    <td class="py-1">
                      <UBadge
                        :color="pos.status === 'closed_profit' ? 'success' : pos.status === 'closed_loss' ? 'error' : 'neutral'"
                        variant="subtle"
                        size="xs"
                      >{{ pos.status.replace(/_/g, ' ') }}</UBadge>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div v-if="sessionDetail.trades.length" class="border rounded-lg p-3">
            <div class="text-xs text-gray-500 mb-2">Trades</div>
            <div class="overflow-x-auto">
              <table class="w-full text-sm">
                <thead>
                  <tr class="text-left text-xs text-gray-500 border-b">
                    <th class="pb-1 pr-3">Side</th>
                    <th class="pb-1 pr-3">Term</th>
                    <th class="pb-1 pr-3">Price</th>
                    <th class="pb-1 pr-3">Amount</th>
                    <th class="pb-1 pr-3">Order</th>
                    <th class="pb-1">Trigger</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="trade in sessionDetail.trades" :key="trade.id" class="border-b border-gray-100 dark:border-gray-800">
                    <td class="py-1 pr-3">
                      <UBadge :color="trade.side === 'buy' ? 'success' : 'error'" variant="soft" size="xs">
                        {{ trade.side.toUpperCase() }}
                      </UBadge>
                    </td>
                    <td class="py-1 pr-3 text-xs">{{ trade.detected_term || '-' }}</td>
                    <td class="py-1 pr-3">${{ trade.price.toFixed(3) }}</td>
                    <td class="py-1 pr-3">${{ trade.amount_usd.toFixed(2) }}</td>
                    <td class="py-1 pr-3 font-mono text-xs">{{ truncate(trade.order_id || '-', 10) }}</td>
                    <td class="py-1">
                      <UBadge variant="subtle" size="xs">{{ trade.triggered_by.replace(/_/g, ' ') }}</UBadge>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- Session History -->
        <div v-if="historyList.length" class="mt-8">
          <h2 class="text-lg font-semibold mb-3">Session History</h2>
          <div class="border rounded-lg divide-y">
            <div v-for="session in historyList" :key="session.id">
              <button
                type="button"
                class="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                @click="toggleHistoryExpand(session.id)"
              >
                <div class="flex items-center gap-3 min-w-0">
                  <UBadge :color="historyStatusColor(session.status)" variant="subtle" size="xs">
                    {{ session.status }}
                  </UBadge>
                  <span class="text-sm truncate">{{ session.video_title || session.youtube_url }}</span>
                </div>
                <div class="flex items-center gap-3 shrink-0 text-xs text-gray-400">
                  <span>{{ session.stage_progress?.terms_detected || 0 }} terms</span>
                  <span>{{ session.stage_progress?.trades_placed || 0 }} trades</span>
                  <span>{{ formatTimestamp(session.created_at) }}</span>
                  <UIcon
                    :name="expandedHistoryId === session.id ? 'i-heroicons-chevron-up' : 'i-heroicons-chevron-down'"
                    class="w-4 h-4"
                  />
                </div>
              </button>

              <div v-if="expandedHistoryId === session.id" class="px-4 pb-4 space-y-3">
                <div v-if="!expandedHistoryDetail" class="flex items-center justify-center p-4">
                  <UIcon name="i-heroicons-arrow-path" class="w-4 h-4 animate-spin" />
                </div>
                <template v-else>
                  <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                    <div>
                      <div class="text-gray-500 text-xs">Terms</div>
                      <div class="font-medium">{{ expandedHistoryDetail.session.stage_progress?.terms_detected || 0 }}</div>
                    </div>
                    <div>
                      <div class="text-gray-500 text-xs">Trades</div>
                      <div class="font-medium">{{ expandedHistoryDetail.trades.length }}</div>
                    </div>
                    <div>
                      <div class="text-gray-500 text-xs">Positions</div>
                      <div class="font-medium">{{ expandedHistoryDetail.positions.length }}</div>
                    </div>
                    <div v-if="expandedHistoryDetail.session.error_message">
                      <div class="text-gray-500 text-xs">Error</div>
                      <div class="font-medium text-red-600 text-xs">{{ expandedHistoryDetail.session.error_message }}</div>
                    </div>
                  </div>

                  <div v-if="expandedHistoryDetail.trades.length" class="overflow-x-auto">
                    <table class="w-full text-sm">
                      <thead>
                        <tr class="text-left text-xs text-gray-500 border-b">
                          <th class="pb-1 pr-3">Side</th>
                          <th class="pb-1 pr-3">Term</th>
                          <th class="pb-1 pr-3">Price</th>
                          <th class="pb-1 pr-3">Amount</th>
                          <th class="pb-1">Trigger</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr v-for="trade in expandedHistoryDetail.trades" :key="trade.id" class="border-b border-gray-100 dark:border-gray-800">
                          <td class="py-1 pr-3">
                            <UBadge :color="trade.side === 'buy' ? 'success' : 'error'" variant="soft" size="xs">
                              {{ trade.side.toUpperCase() }}
                            </UBadge>
                          </td>
                          <td class="py-1 pr-3 text-xs">{{ trade.detected_term || '-' }}</td>
                          <td class="py-1 pr-3">${{ trade.price.toFixed(3) }}</td>
                          <td class="py-1 pr-3">${{ trade.amount_usd.toFixed(2) }}</td>
                          <td class="py-1">
                            <UBadge variant="subtle" size="xs">{{ trade.triggered_by.replace(/_/g, ' ') }}</UBadge>
                          </td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ==================== SIMULATION TAB ==================== -->
      <div v-if="activeTab === 'simulation'">
        <!-- Simulation Setup Form -->
        <div v-if="!simSessionId && !simViewingResult && !simCompareMode" class="space-y-6">
          <div class="border rounded-lg p-6 space-y-4">
            <h2 class="text-lg font-semibold">New Simulation</h2>
            <p class="text-sm text-gray-500">
              Re-process a YouTube video against a resolved past event to evaluate strategy performance with historical prices.
            </p>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div class="space-y-1">
                <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Persona</label>
                <USelectMenu
                  v-model="simPersonaId"
                  :items="personaOptions"
                  value-key="value"
                  placeholder="Select a persona"
                  class="w-full"
                />
              </div>
              <div class="space-y-1">
                <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Series</label>
                <USelectMenu
                  v-model="simSeriesId"
                  :items="simFilteredSeriesOptions"
                  value-key="value"
                  :placeholder="simPersonaId ? 'Select a series' : 'Select persona first'"
                  :disabled="!simPersonaId"
                  class="w-full"
                />
              </div>
            </div>

            <!-- Event Selector -->
            <div v-if="simSeriesId" class="space-y-1">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Past Event</label>
              <div v-if="simLoadingEvents" class="flex items-center gap-2 text-sm text-gray-400 py-2">
                <UIcon name="i-heroicons-arrow-path" class="w-4 h-4 animate-spin" />
                Loading events...
              </div>
              <div v-else-if="simEvents.length === 0" class="text-sm text-gray-400 py-2">
                No events found for this series.
              </div>
              <USelectMenu
                v-else
                v-model="simEventId"
                :items="simEventOptions"
                value-key="value"
                placeholder="Select a past event"
                class="w-full"
              />
            </div>

            <!-- Market Selection (from selected event, including closed) -->
            <div v-if="simEventId" class="space-y-2">
              <div class="flex items-center justify-between">
                <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Markets to Simulate</label>
                <div v-if="simMarkets.length > 0" class="flex gap-2">
                  <button type="button" class="text-xs text-primary hover:underline" @click="simSelectAllMarkets">
                    Select All
                  </button>
                  <button type="button" class="text-xs text-gray-400 hover:underline" @click="simDeselectAllMarkets">
                    Deselect All
                  </button>
                </div>
              </div>

              <div v-if="simLoadingMarkets" class="flex items-center gap-2 text-sm text-gray-400 py-2">
                <UIcon name="i-heroicons-arrow-path" class="w-4 h-4 animate-spin" />
                Loading markets...
              </div>

              <div v-else-if="simMarkets.length === 0" class="text-sm text-gray-400 py-2">
                No markets found for this event.
              </div>

              <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <button
                  v-for="market in simMarkets"
                  :key="market.id"
                  type="button"
                  class="text-left p-3 rounded-lg border transition-colors"
                  :class="simSelectedMarketIds.includes(market.id)
                    ? 'border-primary ring-2 ring-primary/30 bg-primary/5'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-400'"
                  @click="simToggleMarket(market.id)"
                >
                  <div class="text-sm font-medium mb-1">{{ market.question || market.slug || market.id }}</div>
                  <div class="flex items-center gap-2 flex-wrap">
                    <template v-if="parseOutcomePrices(market.outcome_prices)">
                      <span class="text-xs font-mono text-green-600">
                        YES {{ (parseOutcomePrices(market.outcome_prices)![0] * 100).toFixed(0) }}c
                      </span>
                      <span class="text-xs font-mono text-red-600">
                        NO {{ (parseOutcomePrices(market.outcome_prices)![1] * 100).toFixed(0) }}c
                      </span>
                    </template>
                    <UBadge v-if="market.closed" color="neutral" variant="subtle" size="xs">Resolved</UBadge>
                    <UBadge v-else-if="market.active" color="success" variant="subtle" size="xs">Active</UBadge>
                    <UBadge v-if="market.resolved_outcome" color="info" variant="subtle" size="xs">
                      {{ market.resolved_outcome }}
                    </UBadge>
                    <UBadge v-if="market.search_terms.length > 0" color="primary" variant="subtle" size="xs">
                      {{ market.search_terms.length }} terms
                    </UBadge>
                    <UBadge v-else color="warning" variant="subtle" size="xs">No terms</UBadge>
                  </div>
                </button>
              </div>

              <div v-if="simMarkets.length > 0" class="text-xs text-gray-400">
                {{ simSelectedMarketIds.length }} of {{ simMarkets.filter(m => m.search_terms.length > 0).length }} markets with terms selected
              </div>
            </div>

            <div class="space-y-1">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">YouTube URL</label>
              <UInput v-model="simYoutubeUrl" placeholder="https://youtube.com/watch?v=..." class="w-full" />
            </div>

            <div class="space-y-1">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Video Title (optional)</label>
              <UInput v-model="simVideoTitle" placeholder="Auto-detected if left blank" class="w-full" />
            </div>

            <!-- Advanced Config -->
            <div class="border rounded-lg">
              <button
                type="button"
                class="w-full flex items-center justify-between px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 rounded-lg"
                @click="simShowAdvanced = !simShowAdvanced"
              >
                <span>Advanced Config</span>
                <UIcon :name="simShowAdvanced ? 'i-heroicons-chevron-up' : 'i-heroicons-chevron-down'" class="w-4 h-4" />
              </button>
              <div v-if="simShowAdvanced" class="px-3 pb-3 space-y-3">
                <div class="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Profit Target (%)</label>
                    <UInput v-model.number="simConfigProfitTarget" type="number" placeholder="30" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Stop Loss (%)</label>
                    <UInput v-model.number="simConfigStopLoss" type="number" placeholder="20" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Max Buy Price</label>
                    <UInput v-model.number="simConfigMaxPrice" type="number" step="0.01" placeholder="0.90" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Buy Amount (USD)</label>
                    <UInput v-model.number="simConfigBuyAmount" type="number" placeholder="5" />
                  </div>
                  <div class="space-y-1">
                    <label class="text-xs text-gray-500">Max Positions</label>
                    <UInput v-model.number="simConfigMaxPositions" type="number" placeholder="10" />
                  </div>
                </div>
              </div>
            </div>

            <div class="flex justify-end">
              <UButton :disabled="!canStartSim" :loading="simStarting" @click="handleStartSim">
                Run Simulation
              </UButton>
            </div>
          </div>
        </div>

        <!-- Simulation Progress -->
        <div v-else-if="isSimActive && simSessionDetail" class="space-y-4">
          <div class="flex items-center justify-between border rounded-lg p-4">
            <div class="flex items-center gap-3">
              <UIcon name="i-heroicons-arrow-path" class="w-5 h-5 animate-spin text-primary" />
              <span class="text-sm font-medium">{{ simStatusLabel }}</span>
              <UBadge color="info" variant="subtle" size="xs">SIMULATION</UBadge>
            </div>
          </div>

          <div class="grid grid-cols-3 gap-3">
            <div class="border rounded-lg p-3">
              <div class="text-xs text-gray-500">Terms Detected</div>
              <div class="text-xl font-bold">{{ simStageProgress.terms_detected || 0 }}</div>
            </div>
            <div class="border rounded-lg p-3">
              <div class="text-xs text-gray-500">Trades Simulated</div>
              <div class="text-xl font-bold">{{ simStageProgress.trades_placed || 0 }}</div>
            </div>
            <div class="border rounded-lg p-3">
              <div class="text-xs text-gray-500">Positions</div>
              <div class="text-xl font-bold">{{ simStageProgress.positions_open || 0 }}</div>
            </div>
          </div>

          <div v-if="simStageProgress.transcript_preview" class="border rounded-lg p-3">
            <div class="text-xs text-gray-500 mb-1">Transcript Preview</div>
            <div class="text-sm font-mono bg-gray-50 dark:bg-gray-900 rounded p-2 max-h-40 overflow-y-auto whitespace-pre-wrap">
              {{ simStageProgress.transcript_preview }}
            </div>
          </div>
        </div>

        <!-- Simulation Result -->
        <div v-else-if="simViewingResult && simSessionDetail" class="space-y-4">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3">
              <UBadge :color="simSessionDetail.session.status === 'completed' ? 'success' : 'error'" variant="soft">
                {{ simSessionDetail.session.status }}
              </UBadge>
              <UBadge color="info" variant="subtle" size="xs">SIMULATION</UBadge>
              <span v-if="simSessionDetail.session.video_title" class="text-sm text-gray-500">
                {{ simSessionDetail.session.video_title }}
              </span>
            </div>
            <UButton size="sm" @click="handleNewSim">New Simulation</UButton>
          </div>

          <div v-if="simSessionDetail.session.error_message" class="text-sm text-red-600 dark:text-red-400">
            {{ simSessionDetail.session.error_message }}
          </div>

          <SimulationResults
            v-if="simSessionDetail.session.status === 'completed'"
            :session-detail="simSessionDetail"
          />
        </div>

        <!-- Compare Mode -->
        <div v-else-if="simCompareMode" class="space-y-4">
          <div class="flex items-center justify-between">
            <h2 class="text-lg font-semibold">Compare Simulations</h2>
            <UButton size="sm" variant="soft" @click="simCompareMode = false; simCompareData = []; simCompareIds = []">
              Back
            </UButton>
          </div>

          <div v-if="simComparing" class="flex items-center justify-center p-8">
            <UIcon name="i-heroicons-arrow-path" class="w-5 h-5 animate-spin" />
          </div>

          <SimulationCompare
            v-else-if="simCompareData.length"
            :sessions="simCompareData"
          />
        </div>

        <!-- Simulation History -->
        <div v-if="simHistoryList.length && !isSimActive" class="mt-8">
          <div class="flex items-center justify-between mb-3">
            <h2 class="text-lg font-semibold">Simulation History</h2>
            <div class="flex items-center gap-2">
              <UButton
                v-if="simCompareIds.length >= 2"
                size="xs"
                variant="soft"
                :loading="simComparing"
                @click="simCompareMode = true; runCompare()"
              >
                Compare ({{ simCompareIds.length }})
              </UButton>
            </div>
          </div>
          <div class="border rounded-lg divide-y">
            <div v-for="session in simHistoryList" :key="session.id">
              <div class="flex items-center">
                <!-- Compare checkbox -->
                <div class="px-3">
                  <input
                    type="checkbox"
                    :checked="simCompareIds.includes(session.id)"
                    class="rounded border-gray-300"
                    @change="toggleSimCompare(session.id)"
                  />
                </div>
                <button
                  type="button"
                  class="flex-1 flex items-center justify-between px-4 py-3 text-left hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
                  @click="toggleSimHistoryExpand(session.id)"
                >
                  <div class="flex items-center gap-3 min-w-0">
                    <UBadge :color="historyStatusColor(session.status)" variant="subtle" size="xs">
                      {{ session.status }}
                    </UBadge>
                    <span class="text-sm truncate">{{ session.video_title || session.youtube_url }}</span>
                    <span
                      v-if="session.simulation_metadata?.total_pnl_usd != null"
                      class="text-sm font-medium"
                      :class="session.simulation_metadata.total_pnl_usd >= 0 ? 'text-green-600' : 'text-red-600'"
                    >
                      ${{ session.simulation_metadata.total_pnl_usd.toFixed(2) }}
                    </span>
                  </div>
                  <div class="flex items-center gap-3 shrink-0 text-xs text-gray-400">
                    <span>{{ session.stage_progress?.terms_detected || 0 }} terms</span>
                    <span>{{ session.stage_progress?.trades_placed || 0 }} trades</span>
                    <span>{{ formatTimestamp(session.created_at) }}</span>
                    <UIcon
                      :name="simExpandedHistoryId === session.id ? 'i-heroicons-chevron-up' : 'i-heroicons-chevron-down'"
                      class="w-4 h-4"
                    />
                  </div>
                </button>
              </div>

              <div v-if="simExpandedHistoryId === session.id" class="px-4 pb-4 space-y-3">
                <div v-if="!simExpandedHistoryDetail" class="flex items-center justify-center p-4">
                  <UIcon name="i-heroicons-arrow-path" class="w-4 h-4 animate-spin" />
                </div>
                <SimulationResults
                  v-else-if="simExpandedHistoryDetail.session.status === 'completed'"
                  :session-detail="simExpandedHistoryDetail"
                />
                <template v-else>
                  <div v-if="simExpandedHistoryDetail.session.error_message" class="text-sm text-red-600">
                    {{ simExpandedHistoryDetail.session.error_message }}
                  </div>
                </template>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
