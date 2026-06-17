<script lang="ts">
definePageMeta({ layout: 'admin', ssr: false })
</script>

<script setup lang="ts">
import type { ProcurementRun, SourceType, RunStatusExtended } from '~/composables/useProcurementRuns'

const {
  runs,
  loading,
  error,
  listRuns,
  startPolling,
  stopPolling,
  cancelRun,
  deleteRun,
  retryRun,
  resetStaleRuns,
  estimateCostUsd,
  formatCostUsd,
  POLL_INTERVAL_MS,
} = useProcurementRuns()
const toast = useToast()
const { personas, fetchPersonas } = usePersonas()

const sourceTypeFilter = ref<SourceType | ''>('')
const personaIdFilter = ref<string>('')
const statusFilter = ref<RunStatusExtended | ''>('')

const STATUS_OPTIONS: { value: RunStatusExtended | ''; label: string }[] = [
  { value: '', label: 'All statuses' },
  { value: 'running', label: 'Running' },
  { value: 'failed', label: 'Failed' },
  { value: 'completed', label: 'Completed' },
  { value: 'cancelled', label: 'Cancelled' },
]

const SOURCE_TYPE_OPTIONS: { value: SourceType | ''; label: string }[] = [
  { value: '', label: 'All sources' },
  { value: 'metadata_backfill', label: 'Metadata backfill' },
  { value: 'truth_social', label: 'Truth Social' },
  { value: 'news_fox', label: 'News (Fox)' },
  { value: 'news_ddgs', label: 'News (DDG)' },
  { value: 'event_tag_auto', label: 'Event tag auto' },
  { value: 'news_gdelt', label: 'News (GDELT)' },
  { value: 'news_newsapi', label: 'News (NewsAPI)' },
]

const personaOptions = computed(() => [
  { value: '', label: 'All personas' },
  ...personas.value.map((p) => ({ value: p.id, label: p.name })),
])

const personaNames = computed<Record<string, string>>(() => {
  const m: Record<string, string> = {}
  for (const p of personas.value) m[p.id] = p.name
  return m
})

const cancellingId = ref<string | null>(null)
const deletingId = ref<string | null>(null)
const retryingId = ref<string | null>(null)
const resettingStale = ref(false)

async function handleCancel(run: ProcurementRun) {
  if (!window.confirm(`Cancel this run? The worker will exit at the next item boundary.`)) return
  cancellingId.value = run.id
  try {
    await cancelRun(run.id)
    toast.add({ title: 'Cancel requested', description: 'The worker will exit shortly.', color: 'warning' })
  } catch (e: any) {
    toast.add({ title: 'Cancel failed', description: e?.data?.detail || e?.message, color: 'error' })
  } finally {
    cancellingId.value = null
  }
}

async function handleDelete(run: ProcurementRun) {
  if (!window.confirm(`Delete this run record? This cannot be undone.`)) return
  deletingId.value = run.id
  try {
    await deleteRun(run.id)
    toast.add({ title: 'Deleted', color: 'success' })
  } catch (e: any) {
    toast.add({ title: 'Delete failed', description: e?.data?.detail || e?.message, color: 'error' })
  } finally {
    deletingId.value = null
  }
}

async function handleRetry(run: ProcurementRun) {
  retryingId.value = run.id
  try {
    const r = await retryRun(run.id)
    toast.add({
      title: 'Retry started',
      description: `A new ${r.source_type.replace(/_/g, ' ')} run was queued.`,
      color: 'success',
    })
  } catch (e: any) {
    toast.add({ title: 'Retry failed', description: e?.data?.detail || e?.message, color: 'error' })
  } finally {
    retryingId.value = null
  }
}

async function handleResetStale() {
  resettingStale.value = true
  try {
    const r = await resetStaleRuns()
    toast.add({
      title: r.reset > 0 ? `Reset ${r.reset} stale run(s)` : 'No stale runs found',
      color: r.reset > 0 ? 'warning' : 'info',
    })
  } catch (e: any) {
    toast.add({ title: 'Reset failed', description: e?.data?.detail || e?.message, color: 'error' })
  } finally {
    resettingStale.value = false
  }
}

function refresh() {
  const opts: Parameters<typeof listRuns>[0] = {}
  if (sourceTypeFilter.value) opts.source_type = sourceTypeFilter.value
  if (personaIdFilter.value) opts.persona_id = personaIdFilter.value
  if (statusFilter.value) opts.status = statusFilter.value
  return listRuns(opts)
}

watch([sourceTypeFilter, personaIdFilter, statusFilter], () => {
  refresh()
})

const totalCostUsd = computed(() =>
  runs.value.reduce(
    (acc, r) => acc + estimateCostUsd(r.prompt_tokens, r.completion_tokens),
    0,
  ),
)

const totalTokens = computed(() =>
  runs.value.reduce(
    (acc, r) => acc + r.prompt_tokens + r.completion_tokens,
    0,
  ),
)

onMounted(async () => {
  await fetchPersonas()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div>
    <div class="mb-8 flex items-start justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold">Operations</h1>
        <p class="text-gray-500 mt-1 text-sm">
          Live status of analytical procurement runs. Auto-refreshes every {{ POLL_INTERVAL_MS / 1000 }}s.
        </p>
      </div>
      <div class="flex gap-2">
        <UButton
          variant="outline"
          color="warning"
          icon="i-lucide-zap-off"
          size="sm"
          :loading="resettingStale"
          title="Mark any 'running' row with no heartbeat in 2+ minutes as cancelled"
          @click="handleResetStale"
        >
          Reset stale
        </UButton>
        <UButton
          variant="outline"
          icon="i-lucide-refresh-cw"
          size="sm"
          :loading="loading"
          @click="refresh"
        >
          Refresh
        </UButton>
      </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <UCard>
        <div class="text-xs text-gray-500 uppercase tracking-wide">Runs shown</div>
        <div class="text-2xl font-semibold mt-1">{{ runs.length }}</div>
      </UCard>
      <UCard>
        <div class="text-xs text-gray-500 uppercase tracking-wide">Total tokens (in + out)</div>
        <div class="text-2xl font-semibold mt-1">{{ totalTokens.toLocaleString() }}</div>
      </UCard>
      <UCard>
        <div class="text-xs text-gray-500 uppercase tracking-wide">Estimated cost</div>
        <div class="text-2xl font-semibold mt-1">{{ formatCostUsd(totalCostUsd) }}</div>
      </UCard>
    </div>

    <div class="flex flex-wrap items-end gap-3 mb-4">
      <UFormField label="Source type">
        <USelectMenu
          v-model="sourceTypeFilter"
          :items="SOURCE_TYPE_OPTIONS"
          value-key="value"
          class="w-56"
        />
      </UFormField>
      <UFormField label="Persona">
        <USelectMenu
          v-model="personaIdFilter"
          :items="personaOptions"
          value-key="value"
          class="w-56"
        />
      </UFormField>
      <UFormField label="Status">
        <USelectMenu
          v-model="statusFilter"
          :items="STATUS_OPTIONS"
          value-key="value"
          class="w-44"
        />
      </UFormField>
    </div>

    <UAlert
      v-if="error"
      color="error"
      :title="error"
      class="mb-4"
    />

    <UCard>
      <AnalyticalProcurementRunTable
        :runs="runs"
        :persona-names="personaNames"
        :loading="loading"
        :cancelling-id="cancellingId"
        :deleting-id="deletingId"
        :retrying-id="retryingId"
        empty-text="No procurement runs yet. Trigger one from the Analytical page or the persona detail page (Backfill metadata)."
        @cancel="handleCancel"
        @delete="handleDelete"
        @retry="handleRetry"
      />
    </UCard>
  </div>
</template>
