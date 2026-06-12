<script setup lang="ts">
/**
 * Reusable procurement-run status table.
 *
 * Pure presentation: the parent owns the run list (and its polling) and the
 * cancel/delete API calls — this component emits `cancel`/`delete` with the run.
 * Used by both the Operations dashboard and the Analytical page.
 */
import type { ProcurementRun } from '~/composables/useProcurementRuns'
import {
  estimateCostUsd,
  formatCostUsd,
  estimateEtaSeconds,
  formatDurationSeconds,
} from '~/composables/useProcurementRuns'

const props = withDefaults(
  defineProps<{
    runs: ProcurementRun[]
    personaNames?: Record<string, string>
    loading?: boolean
    cancellingId?: string | null
    deletingId?: string | null
    emptyText?: string
  }>(),
  {
    personaNames: () => ({}),
    loading: false,
    cancellingId: null,
    deletingId: null,
    emptyText: 'No procurement runs yet.',
  },
)

const emit = defineEmits<{ cancel: [run: ProcurementRun]; delete: [run: ProcurementRun] }>()

const SOURCE_TYPE_COLOR: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'neutral' | 'error'> = {
  metadata_backfill: 'primary',
  news_ddgs: 'info',
  news_gdelt: 'info',
  news_newsapi: 'info',
  news_fox: 'error',
  truth_social: 'warning',
  event_tag_auto: 'success',
}

function statusColor(status: string) {
  if (status === 'running') return 'info'
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'error'
  if (status === 'cancelled') return 'warning'
  return 'neutral'
}

function personaLabel(id: string): string {
  return props.personaNames[id] || id.slice(0, 8)
}

function relativeTime(iso: string | null): string {
  if (!iso) return '—'
  const ms = Date.now() - new Date(iso).getTime()
  if (ms < 60_000) return `${Math.round(ms / 1000)}s ago`
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m ago`
  if (ms < 86_400_000) return `${Math.round(ms / 3_600_000)}h ago`
  return `${Math.round(ms / 86_400_000)}d ago`
}

function runDuration(run: ProcurementRun): number {
  if (!run.started_at) return 0
  const end = run.completed_at ? new Date(run.completed_at).getTime() : Date.now()
  return Math.round((end - new Date(run.started_at).getTime()) / 1000)
}

function progressPercent(run: ProcurementRun): number {
  if (run.items_found === 0) return 0
  return Math.min(100, Math.round(((run.items_new + run.items_skipped) / run.items_found) * 100))
}
</script>

<template>
  <div>
    <div v-if="loading && runs.length === 0" class="py-8 flex justify-center">
      <UIcon name="i-lucide-loader" class="size-6 animate-spin" />
    </div>

    <div v-else-if="runs.length === 0" class="py-8 text-center text-gray-500">
      {{ emptyText }}
    </div>

    <div v-else class="overflow-x-auto">
      <table class="min-w-full text-sm">
        <thead>
          <tr class="border-b border-gray-200 dark:border-gray-800 text-left text-xs uppercase tracking-wide text-gray-500">
            <th class="py-2 pr-4">Source</th>
            <th class="py-2 pr-4">Persona</th>
            <th class="py-2 pr-4">Status</th>
            <th class="py-2 pr-4">Progress</th>
            <th class="py-2 pr-4">Current item</th>
            <th class="py-2 pr-4">ETA</th>
            <th class="py-2 pr-4">Tokens · cost</th>
            <th class="py-2 pr-4">Duration</th>
            <th class="py-2 pr-4">Started</th>
            <th class="py-2 pr-2 text-right">Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="run in runs"
            :key="run.id"
            class="border-b border-gray-100 dark:border-gray-900 last:border-0"
            :class="run.status === 'running' ? 'bg-blue-50/40 dark:bg-blue-950/20' : ''"
          >
            <td class="py-2 pr-4">
              <UBadge :color="SOURCE_TYPE_COLOR[run.source_type] || 'neutral'" variant="subtle">
                {{ run.source_type.replace(/_/g, ' ') }}
              </UBadge>
            </td>
            <td class="py-2 pr-4">
              {{ personaLabel(run.persona_id) }}
            </td>
            <td class="py-2 pr-4">
              <UBadge :color="statusColor(run.status)" variant="subtle">
                <span v-if="run.status === 'running'" class="inline-block size-1.5 rounded-full bg-current animate-pulse mr-1"></span>
                {{ run.status }}
              </UBadge>
            </td>
            <td class="py-2 pr-4 whitespace-nowrap">
              <div class="flex items-center gap-2">
                <span class="font-medium tabular-nums">
                  {{ run.items_new + run.items_skipped }} / {{ run.items_found }}
                </span>
                <div v-if="run.items_found > 0" class="w-20 h-1.5 bg-gray-200 dark:bg-gray-800 rounded-full overflow-hidden">
                  <div
                    class="h-full bg-primary transition-all"
                    :style="{ width: `${progressPercent(run)}%` }"
                  ></div>
                </div>
              </div>
              <div v-if="run.items_skipped > 0" class="text-xs text-gray-500 mt-0.5">
                {{ run.items_skipped }} existing
              </div>
            </td>
            <td class="py-2 pr-4 max-w-xs truncate text-gray-600 dark:text-gray-400">
              <template v-if="run.status === 'running' && run.current_item_name">
                <span class="text-xs text-gray-400">[{{ run.current_item_index }}]</span>
                {{ run.current_item_name }}
              </template>
              <span v-else class="text-gray-400">—</span>
            </td>
            <td class="py-2 pr-4 whitespace-nowrap tabular-nums">
              {{ formatDurationSeconds(estimateEtaSeconds(run)) }}
            </td>
            <td class="py-2 pr-4 whitespace-nowrap">
              <div class="tabular-nums">
                {{ (run.prompt_tokens + run.completion_tokens).toLocaleString() }}
              </div>
              <div class="text-xs text-gray-500 tabular-nums">
                {{ formatCostUsd(estimateCostUsd(run.prompt_tokens, run.completion_tokens)) }}
              </div>
            </td>
            <td class="py-2 pr-4 whitespace-nowrap tabular-nums">
              {{ formatDurationSeconds(runDuration(run)) }}
            </td>
            <td class="py-2 pr-4 whitespace-nowrap text-gray-500">
              {{ relativeTime(run.started_at) }}
            </td>
            <td class="py-2 pr-2 whitespace-nowrap text-right">
              <UButton
                v-if="run.status === 'running'"
                variant="ghost"
                size="xs"
                color="warning"
                icon="i-lucide-square"
                :loading="cancellingId === run.id"
                :disabled="run.cancel_requested"
                :title="run.cancel_requested ? 'Cancel already requested' : 'Cancel this run'"
                @click="emit('cancel', run)"
              >
                {{ run.cancel_requested ? 'Cancelling…' : 'Cancel' }}
              </UButton>
              <UButton
                v-else
                variant="ghost"
                size="xs"
                color="error"
                icon="i-lucide-trash-2"
                :loading="deletingId === run.id"
                @click="emit('delete', run)"
              >
                Delete
              </UButton>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
