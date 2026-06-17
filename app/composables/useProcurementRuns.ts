/**
 * Composable for the Operations dashboard.
 *
 * Wraps GET /api/analytical/procurement-runs and provides:
 *   - Shared `runs` state (via useState)
 *   - Auto-polling at POLL_INTERVAL_MS while any run is active
 *   - Cost + ETA helpers
 *
 * Caller owns lifecycle: call start() on mount and stop() on unmount.
 */

const POLL_INTERVAL_MS = 4000

export type RunStatus = 'running' | 'completed' | 'failed'

export type SourceType =
  | 'truth_social'
  | 'news_ddgs'
  | 'news_gdelt'
  | 'news_newsapi'
  | 'news_fox'
  | 'event_tag_auto'
  | 'metadata_backfill'

export type RunStatusExtended = RunStatus | 'cancelled'

/**
 * One entry in `procurement_runs.details` — heterogeneous across source types
 * (metadata backfill, event-tag auto, scrape) but with a common `action` key
 * and best-effort `error`/`errors` fields. Typed loosely on purpose.
 */
export interface RunDetailItem {
  action?: string
  name?: string | null
  transcript_id?: string
  error?: string | null
  errors?: Array<{ call?: string; error?: string; finish_reason?: string | null }>
  event_type?: string | null
  // scrape-path failure shapes
  label?: string
  chunk_size?: number
  attempts?: number
  items_found_before_failure?: number
  [k: string]: unknown
}

export interface ProcurementRun {
  id: string
  source_type: SourceType
  persona_id: string
  status: RunStatusExtended
  items_found: number
  items_new: number
  items_skipped: number
  current_item_index: number | null
  current_item_name: string | null
  prompt_tokens: number
  completion_tokens: number
  cancel_requested: boolean
  error_message: string | null
  details: RunDetailItem[]
  params?: Record<string, unknown>
  retry_of?: string | null
  attempt?: number
  started_at: string | null
  completed_at: string | null
  updated_at: string | null
}

export interface ListRunsOptions {
  source_type?: SourceType
  persona_id?: string
  status?: RunStatusExtended
  limit?: number
}

/** Actions in `details` that represent a successful item (everything else is a failure). */
const SUCCESS_ACTIONS = new Set(['extracted', 'tagged'])

/** Source types whose runs the backend can re-launch via the retry endpoint. */
const RETRYABLE_SOURCE_TYPES = new Set<SourceType>([
  'truth_social',
  'news_fox',
  'metadata_backfill',
  'event_tag_auto',
])

export interface DetailSummary {
  counts: Record<string, number>
  failures: Array<{ name: string; action: string; error: string }>
}

/** Group a run's `details` by action and pull out a flat list of failures. */
export function summarizeDetails(details: RunDetailItem[] | undefined | null): DetailSummary {
  const counts: Record<string, number> = {}
  const failures: DetailSummary['failures'] = []
  for (const d of details || []) {
    const action = (d?.action as string) || 'unknown'
    counts[action] = (counts[action] || 0) + 1
    if (!SUCCESS_ACTIONS.has(action)) {
      const err =
        (d?.error as string) ||
        (Array.isArray(d?.errors) && d.errors[0]?.error) ||
        action
      failures.push({
        name: (d?.name as string) || (d?.label as string) || (d?.transcript_id as string) || '—',
        action,
        error: String(err),
      })
    }
  }
  return { counts, failures }
}

/** A terminal run from a source type the backend knows how to re-launch. */
export function isRetryable(run: ProcurementRun): boolean {
  return run.status !== 'running' && RETRYABLE_SOURCE_TYPES.has(run.source_type)
}

/** True if a run has anything worth expanding (an error or non-success details). */
export function hasDetail(run: ProcurementRun): boolean {
  if (run.error_message) return true
  return (run.details || []).some((d) => d?.action && !SUCCESS_ACTIONS.has(d.action))
}

/**
 * Gemini Flash pricing (USD per token). Update when Google changes rates.
 * https://ai.google.dev/pricing
 */
const GEMINI_PRICING: Record<string, { in: number; out: number }> = {
  'gemini-3-flash-preview': { in: 0.075 / 1_000_000, out: 0.30 / 1_000_000 },
}

export function estimateCostUsd(
  promptTokens: number,
  completionTokens: number,
  model: keyof typeof GEMINI_PRICING = 'gemini-3-flash-preview',
): number {
  const rates = GEMINI_PRICING[model]
  if (!rates) return 0
  return promptTokens * rates.in + completionTokens * rates.out
}

export function formatCostUsd(value: number): string {
  if (value === 0) return '$0'
  if (value < 0.01) return `$${value.toFixed(4)}`
  if (value < 1) return `$${value.toFixed(3)}`
  return `$${value.toFixed(2)}`
}

/**
 * ETA helper — seconds remaining, or null if we can't estimate yet.
 */
export function estimateEtaSeconds(run: ProcurementRun): number | null {
  if (run.status !== 'running' || !run.started_at) return null
  const done = run.items_new + run.items_skipped
  if (done <= 0) return null
  const remaining = Math.max(0, run.items_found - done)
  if (remaining === 0) return 0
  const elapsedMs = Date.now() - new Date(run.started_at).getTime()
  if (elapsedMs <= 0) return null
  const avgMsPerItem = elapsedMs / done
  return Math.round((remaining * avgMsPerItem) / 1000)
}

export function formatDurationSeconds(s: number | null): string {
  if (s === null) return '—'
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  if (m < 60) return `${m}m ${rem}s`
  const h = Math.floor(m / 60)
  return `${h}h ${m % 60}m`
}

export function useProcurementRuns() {
  const { authFetch } = useAuthFetch()
  const runs = useState<ProcurementRun[]>('procurement-runs', () => [])
  const loading = useState<boolean>('procurement-runs-loading', () => false)
  const error = useState<string | null>('procurement-runs-error', () => null)
  const lastOpts = useState<ListRunsOptions>('procurement-runs-opts', () => ({}))

  let pollTimer: ReturnType<typeof setInterval> | null = null

  async function listRuns(opts: ListRunsOptions = {}): Promise<ProcurementRun[]> {
    lastOpts.value = opts
    loading.value = true
    error.value = null
    try {
      const query: Record<string, string> = {}
      if (opts.source_type) query.source_type = opts.source_type
      if (opts.persona_id) query.persona_id = opts.persona_id
      if (opts.status) query.status = opts.status
      query.limit = String(opts.limit ?? 50)
      const result = await authFetch<ProcurementRun[]>(
        '/api/analytical/procurement-runs',
        { query },
      )
      runs.value = Array.isArray(result) ? result : []
      return runs.value
    } catch (e: any) {
      error.value = e?.message || 'Failed to load procurement runs'
      console.error('listRuns failed:', e)
      return []
    } finally {
      loading.value = false
    }
  }

  function hasActiveRun(): boolean {
    return runs.value.some((r) => r.status === 'running')
  }

  function startPolling(opts?: ListRunsOptions): void {
    if (pollTimer) return
    if (opts) lastOpts.value = opts
    // Immediate refresh, then schedule
    void listRuns(lastOpts.value)
    pollTimer = setInterval(() => {
      // Skip the network call if nothing's active AND we've already loaded once.
      // We always refresh while at least one run is running, otherwise every
      // 3 ticks to catch newly-started runs.
      void listRuns(lastOpts.value)
    }, POLL_INTERVAL_MS)
  }

  function stopPolling(): void {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  async function cancelRun(runId: string): Promise<void> {
    await authFetch(`/api/analytical/procurement-runs/${runId}/cancel`, {
      method: 'POST',
    })
    void listRuns(lastOpts.value)
  }

  async function deleteRun(runId: string): Promise<void> {
    await authFetch(`/api/analytical/procurement-runs/${runId}`, {
      method: 'DELETE',
    })
    void listRuns(lastOpts.value)
  }

  async function retryRun(
    runId: string,
  ): Promise<{ message: string; run_id?: string; source_type: string }> {
    const result = await authFetch<{ message: string; run_id?: string; source_type: string }>(
      `/api/analytical/procurement-runs/${runId}/retry`,
      { method: 'POST' },
    )
    void listRuns(lastOpts.value)
    return result
  }

  async function resetStaleRuns(): Promise<{ reset: number; run_ids?: string[] }> {
    const result = await authFetch<{ reset: number; run_ids?: string[] }>(
      '/api/analytical/procurement-runs/reset-stale',
      { method: 'POST' },
    )
    void listRuns(lastOpts.value)
    return result
  }

  return {
    runs,
    loading,
    error,
    listRuns,
    startPolling,
    stopPolling,
    hasActiveRun,
    cancelRun,
    deleteRun,
    retryRun,
    resetStaleRuns,
    estimateCostUsd,
    formatCostUsd,
    estimateEtaSeconds,
    formatDurationSeconds,
    summarizeDetails,
    isRetryable,
    hasDetail,
    POLL_INTERVAL_MS,
  }
}
