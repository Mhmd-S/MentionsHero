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
  details: unknown[]
  started_at: string | null
  completed_at: string | null
  updated_at: string | null
}

export interface ListRunsOptions {
  source_type?: SourceType
  persona_id?: string
  limit?: number
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
    resetStaleRuns,
    estimateCostUsd,
    formatCostUsd,
    estimateEtaSeconds,
    formatDurationSeconds,
    POLL_INTERVAL_MS,
  }
}
