<script lang="ts">
definePageMeta({ layout: 'admin', ssr: false })
</script>

<script setup lang="ts">
import type { ProcurementRun } from '~/composables/useProcurementRuns'

const { personas, fetchPersonas } = usePersonas()
const {
  runs,
  loading,
  startPolling,
  stopPolling,
  cancelRun,
  deleteRun,
  retryRun,
  POLL_INTERVAL_MS,
} = useProcurementRuns()
const toast = useToast()

const selectedPersonaId = ref<string>('')
const selectedPersona = computed(
  () => personas.value.find((p) => p.id === selectedPersonaId.value) || null,
)
const personaOptions = computed(() => personas.value.map((p) => ({ value: p.id, label: p.name })))
const personaNames = computed<Record<string, string>>(() =>
  Object.fromEntries(personas.value.map((p) => [p.id, p.name])),
)

const cancellingId = ref<string | null>(null)
const deletingId = ref<string | null>(null)
const retryingId = ref<string | null>(null)

function repoll() {
  stopPolling()
  if (selectedPersonaId.value) {
    startPolling({ persona_id: selectedPersonaId.value, limit: 50 })
  }
}
watch(selectedPersonaId, repoll)

async function handleCancel(run: ProcurementRun) {
  if (!window.confirm('Cancel this run? The worker exits at the next item boundary.')) return
  cancellingId.value = run.id
  try {
    await cancelRun(run.id)
    toast.add({ title: 'Cancel requested', color: 'warning' })
  } catch (e: any) {
    toast.add({ title: 'Cancel failed', description: e?.data?.detail || e?.message, color: 'error' })
  } finally {
    cancellingId.value = null
  }
}

async function handleDelete(run: ProcurementRun) {
  if (!window.confirm('Delete this run record? This cannot be undone.')) return
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

onMounted(async () => {
  await fetchPersonas()
  const trump = personas.value.find((p) => /trump/i.test(p.name))
  selectedPersonaId.value = trump?.id || personas.value[0]?.id || ''
})

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div>
    <div class="mb-6">
      <h1 class="text-2xl font-bold">Analytical Procurement</h1>
      <p class="text-gray-500 mt-1 text-sm">
        Scrape real Truth Social posts and Fox News articles for a persona over a date range
        (e.g. January → now). Runs stream live below and on the
        <NuxtLink to="/admin/operations" class="text-primary hover:underline">Operations</NuxtLink>
        dashboard.
      </p>
    </div>

    <div class="mb-6 max-w-sm">
      <UFormField label="Persona">
        <USelectMenu
          v-model="selectedPersonaId"
          :items="personaOptions"
          value-key="value"
          placeholder="Select a persona"
          class="w-full"
        />
      </UFormField>
    </div>

    <UAlert
      v-if="!selectedPersonaId"
      color="info"
      variant="subtle"
      title="Select a persona to begin"
      icon="i-lucide-info"
      class="mb-6"
    />

    <div v-else class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <AnalyticalSourcePanel
        :persona="selectedPersona"
        source-type="truth_social"
        title="Truth Social"
        icon="i-lucide-megaphone"
        description="Real @realDonaldTrump posts via the public Truth Social API."
      />
      <AnalyticalSourcePanel
        :persona="selectedPersona"
        source-type="news_fox"
        title="Fox News"
        icon="i-lucide-newspaper"
        description="Fox articles about the persona, via Fox's dated sitemap."
      />
    </div>

    <div v-if="selectedPersonaId" class="mt-8">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-lg font-semibold">Recent runs</h2>
        <span class="text-xs text-gray-500">Auto-refreshes every {{ POLL_INTERVAL_MS / 1000 }}s</span>
      </div>
      <UCard>
        <AnalyticalProcurementRunTable
          :runs="runs"
          :persona-names="personaNames"
          :loading="loading"
          :cancelling-id="cancellingId"
          :deleting-id="deletingId"
          :retrying-id="retryingId"
          empty-text="No runs yet for this persona. Trigger a scrape above."
          @cancel="handleCancel"
          @delete="handleDelete"
          @retry="handleRetry"
        />
      </UCard>
    </div>
  </div>
</template>
