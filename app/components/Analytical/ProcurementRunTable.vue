<script setup lang="ts">
/**
 * Reusable procurement-run status table.
 *
 * Pure presentation: the parent owns the run list (and its polling) and the
 * cancel/delete/retry API calls — this component emits `cancel`/`delete`/`retry`
 * with the run. Used by both the Operations dashboard and the Analytical page.
 *
 * Each row with an error or item-level failures can be expanded to reveal the
 * top-level error_message plus a breakdown of `details` (counts per action and
 * a list of the failed items) — so "what went wrong" is visible without
 * digging into the DB.
 */
import type { ProcurementRun } from '~/composables/useProcurementRuns'
import {
  estimateCostUsd,
  formatCostUsd,
  estimateEtaSeconds,
  formatDurationSeconds,
  summarizeDetails,
  isRetryable,
  hasDetail,
} from '~/composables/useProcurementRuns'

const props = withDefaults(
  defineProps<{
    runs: ProcurementRun[]
    personaNames?: Record<string, string>
    loading?: boolean
    cancellingId?: string | null
    deletingId?: string | null
    retryingId?: string | null
    emptyText?: string
  }>(),
  {
    personaNames: () => ({}),
    loading: false,
    cancellingId: null,
    deletingId: null,
    retryingId: null,
    emptyText: 'No procurement runs yet.',
  },
)

const emit = defineEmits<{
  cancel: [run: ProcurementRun]
  delete: [run: ProcurementRun]
  retry: [run: ProcurementRun]
}>()

const COLSPAN = 11

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

/** Colour a per-item action: green = success, amber = timeout, red = hard failure. */
function actionColor(action: string): 'success' | 'warning' | 'error' | 'neutral' {
  if (action === 'extracted' || action === 'tagged') return 'success'
  if (action.endsWith('_timeout')) return 'warning'
  if (action.endsWith('_failed') || action === 'error') return 'error'
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

function rowTint(run: ProcurementRun): string {
  if (run.status === 'running') return 'bg-blue-50/40 dark:bg-blue-950/20'
  if (run.status === 'failed') return 'bg-red-50/40 dark:bg-red-950/20'
  return ''
}

// Local expand state — which rows are showing their detail panel.
const expanded = ref<Record<string, boolean>>({})
function toggle(run: ProcurementRun): void {
  if (!hasDetail(run)) return
  expanded.value[run.id] = !expanded.value[run.id]
}

function summary(run: ProcurementRun) {
  return summarizeDetails(run.details)
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
            <th class="py-2 pr-2 w-6"></th>
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
          <template v-for="run in runs" :key="run.id">
            <tr
              class="border-b border-gray-100 dark:border-gray-900"
              :class="[rowTint(run), { 'border-b-0': expanded[run.id] }]"
            >
              <td class="py-2 pr-2 align-top">
                <button
                  v-if="hasDetail(run)"
                  type="button"
                  class="text-gray-400 hover:text-gray-700 dark:hover:text-gray-200"
                  :title="expanded[run.id] ? 'Hide details' : 'Show what went wrong'"
                  @click="toggle(run)"
                >
                  <UIcon
                    :name="expanded[run.id] ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
                    class="size-4"
                  />
                </button>
              </td>
              <td class="py-2 pr-4">
                <UBadge :color="SOURCE_TYPE_COLOR[run.source_type] || 'neutral'" variant="subtle">
                  {{ run.source_type.replace(/_/g, ' ') }}
                </UBadge>
                <span v-if="(run.attempt || 1) > 1" class="ml-1 text-xs text-gray-400" title="Retry attempt">
                  #{{ run.attempt }}
                </span>
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
                <div class="flex items-center justify-end gap-1">
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
                  <template v-else>
                    <UButton
                      v-if="isRetryable(run)"
                      variant="ghost"
                      size="xs"
                      color="primary"
                      icon="i-lucide-rotate-cw"
                      :loading="retryingId === run.id"
                      title="Re-run this ingestion with the same parameters"
                      @click="emit('retry', run)"
                    >
                      Retry
                    </UButton>
                    <UButton
                      variant="ghost"
                      size="xs"
                      color="error"
                      icon="i-lucide-trash-2"
                      :loading="deletingId === run.id"
                      @click="emit('delete', run)"
                    >
                      Delete
                    </UButton>
                  </template>
                </div>
              </td>
            </tr>

            <tr
              v-if="expanded[run.id]"
              class="border-b border-gray-100 dark:border-gray-900"
              :class="rowTint(run)"
            >
              <td :colspan="COLSPAN" class="px-4 pb-3 pt-0">
                <div class="rounded-md bg-gray-50 dark:bg-gray-900/50 p-3">
                  <div
                    v-if="(run.attempt || 1) > 1 || run.retry_of"
                    class="text-xs text-gray-500 mb-2"
                  >
                    Attempt {{ run.attempt || 1 }}<span v-if="run.retry_of"> · retry of {{ run.retry_of?.slice(0, 8) }}</span>
                  </div>

                  <div
                    v-if="run.error_message"
                    class="mb-3 rounded-md border border-red-200 dark:border-red-900 bg-red-50 dark:bg-red-950/30 p-2"
                  >
                    <div class="text-xs font-medium uppercase tracking-wide text-red-600 dark:text-red-400 mb-0.5">
                      Error
                    </div>
                    <div class="whitespace-pre-wrap break-words font-mono text-xs text-red-700 dark:text-red-300">
                      {{ run.error_message }}
                    </div>
                  </div>

                  <div v-if="Object.keys(summary(run).counts).length" class="flex flex-wrap gap-1.5 mb-2">
                    <UBadge
                      v-for="(count, action) in summary(run).counts"
                      :key="action"
                      :color="actionColor(action)"
                      variant="subtle"
                      size="sm"
                    >
                      {{ action.replace(/_/g, ' ') }}: {{ count }}
                    </UBadge>
                  </div>

                  <div v-if="summary(run).failures.length">
                    <div class="text-xs uppercase tracking-wide text-gray-500 mb-1">
                      Failed items ({{ summary(run).failures.length }})
                    </div>
                    <div class="max-h-60 overflow-y-auto rounded-md border border-gray-200 dark:border-gray-800 divide-y divide-gray-100 dark:divide-gray-800">
                      <div
                        v-for="(f, idx) in summary(run).failures"
                        :key="idx"
                        class="px-2 py-1.5 text-xs"
                      >
                        <div class="flex items-center gap-2">
                          <UBadge :color="actionColor(f.action)" variant="subtle" size="sm">
                            {{ f.action.replace(/_/g, ' ') }}
                          </UBadge>
                          <span class="truncate text-gray-700 dark:text-gray-300">{{ f.name }}</span>
                        </div>
                        <div class="mt-0.5 font-mono text-gray-500 break-words">{{ f.error }}</div>
                      </div>
                    </div>
                  </div>
                  <div v-else-if="!run.error_message" class="text-xs text-gray-500">
                    No item-level errors recorded.
                  </div>
                </div>
              </td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </div>
</template>
