<script setup lang="ts">
/**
 * Generic per-source procurement panel — composed once per source on the
 * Analytical page (Truth Social, Fox News). Owns: the trigger form, a compact
 * live-run banner for THIS source, and the browsable result list.
 *
 * Run polling is owned by the parent page (single persona-scoped poller); this
 * panel just reads the shared `runs` state and filters to its own source_type.
 */
import type { Persona } from '~/composables/usePersonas'
import type { ScrapeSourceType } from '~/composables/useAnalyticalProcurement'
import { useProcurementRuns } from '~/composables/useProcurementRuns'

const props = defineProps<{
  persona: Persona | null
  sourceType: ScrapeSourceType
  title: string
  icon: string
  description?: string
}>()

const { scrape, listTruthSocial, listNews } = useAnalyticalProcurement()
const { runs, cancelRun } = useProcurementRuns()
const toast = useToast()

const items = ref<any[]>([])
const listLoading = ref(false)
const scrapeLoading = ref(false)
const cancelling = ref(false)

const isTruthSocial = computed(() => props.sourceType === 'truth_social')

/** This source's runs for the selected persona, newest-first (shared state). */
const myRuns = computed(() =>
  runs.value.filter(
    (r) => r.source_type === props.sourceType && r.persona_id === props.persona?.id,
  ),
)
const activeRun = computed(() => myRuns.value.find((r) => r.status === 'running') || null)

const progressPercent = computed(() => {
  const r = activeRun.value
  if (!r || r.items_found === 0) return 0
  return Math.min(100, Math.round(((r.items_new + r.items_skipped) / r.items_found) * 100))
})

async function loadList() {
  if (!props.persona) {
    items.value = []
    return
  }
  listLoading.value = true
  try {
    items.value = isTruthSocial.value
      ? await listTruthSocial({ personaId: props.persona.id, limit: 200 })
      : await listNews({ personaId: props.persona.id, limit: 200 })
  } catch (e: any) {
    toast.add({ title: 'Failed to load', description: e?.data?.detail || e?.message, color: 'error' })
  } finally {
    listLoading.value = false
  }
}

async function onScrape(payload: { startDate: string; endDate: string }) {
  if (!props.persona) {
    toast.add({ title: 'Select a persona first', color: 'warning' })
    return
  }
  scrapeLoading.value = true
  try {
    await scrape({
      personaId: props.persona.id,
      sourceType: props.sourceType,
      startDate: payload.startDate,
      endDate: payload.endDate,
    })
    toast.add({
      title: `${props.title} scrape started`,
      description: 'Live progress appears below and on the Operations dashboard.',
      color: 'success',
    })
  } catch (e: any) {
    toast.add({ title: 'Scrape failed to start', description: e?.data?.detail || e?.message, color: 'error' })
  } finally {
    scrapeLoading.value = false
  }
}

async function onCancel() {
  if (!activeRun.value) return
  cancelling.value = true
  try {
    await cancelRun(activeRun.value.id)
    toast.add({ title: 'Cancel requested', color: 'warning' })
  } catch (e: any) {
    toast.add({ title: 'Cancel failed', description: e?.data?.detail || e?.message, color: 'error' })
  } finally {
    cancelling.value = false
  }
}

// Reload the list whenever the persona changes…
watch(() => props.persona?.id, () => loadList(), { immediate: true })

// …and whenever this source's active run finishes (running → terminal).
watch(
  () => activeRun.value?.id,
  (now, prev) => {
    if (prev && !now) loadList()
  },
)
</script>

<template>
  <UCard>
    <template #header>
      <div class="flex items-start justify-between gap-3">
        <div class="flex items-start gap-2">
          <UIcon :name="icon" class="size-5 mt-0.5 text-primary shrink-0" />
          <div>
            <h3 class="font-semibold">{{ title }}</h3>
            <p v-if="description" class="text-xs text-gray-500 mt-0.5">{{ description }}</p>
          </div>
        </div>
        <UBadge color="neutral" variant="subtle">{{ items.length }} stored</UBadge>
      </div>
    </template>

    <div class="space-y-4">
      <AnalyticalProcurementForm
        :loading="scrapeLoading || !!activeRun"
        :submit-label="activeRun ? 'Running…' : 'Scrape range'"
        @scrape="onScrape"
      />

      <!-- Compact live-run banner for this source -->
      <div
        v-if="activeRun"
        class="rounded-md border border-blue-200 dark:border-blue-900 bg-blue-50/50 dark:bg-blue-950/20 p-3"
      >
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-2 text-sm">
            <span class="inline-block size-1.5 rounded-full bg-blue-500 animate-pulse"></span>
            <span class="tabular-nums font-medium">
              {{ activeRun.items_new + activeRun.items_skipped }} / {{ activeRun.items_found || '…' }}
            </span>
            <span class="text-gray-500">found · {{ activeRun.items_new }} new</span>
          </div>
          <UButton
            size="xs"
            color="warning"
            variant="ghost"
            icon="i-lucide-square"
            :loading="cancelling"
            :disabled="activeRun.cancel_requested"
            @click="onCancel"
          >
            {{ activeRun.cancel_requested ? 'Cancelling…' : 'Cancel' }}
          </UButton>
        </div>
        <div v-if="activeRun.items_found > 0" class="w-full h-1.5 bg-blue-100 dark:bg-blue-900 rounded-full overflow-hidden mt-2">
          <div class="h-full bg-blue-500 transition-all" :style="{ width: `${progressPercent}%` }"></div>
        </div>
        <p v-if="activeRun.current_item_name" class="text-xs text-gray-500 mt-1 truncate">
          {{ activeRun.current_item_name }}
        </p>
      </div>

      <div class="flex items-center justify-between">
        <span class="text-xs uppercase tracking-wide text-gray-500">Stored items</span>
        <UButton
          variant="ghost"
          size="xs"
          icon="i-lucide-refresh-cw"
          :loading="listLoading"
          @click="loadList"
        >
          Refresh
        </UButton>
      </div>

      <div class="max-h-[28rem] overflow-y-auto pr-1">
        <AnalyticalTruthSocialPostList v-if="isTruthSocial" :posts="items" :loading="listLoading" />
        <AnalyticalNewsItemList v-else :items="items" :loading="listLoading" />
      </div>
    </div>
  </UCard>
</template>
