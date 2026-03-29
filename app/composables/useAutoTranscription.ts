/**
 * Composable for auto-transcription source management
 */

export interface AutoSource {
  id: string
  persona_id: string
  persona_name: string | null
  source_type: 'channel' | 'playlist'
  youtube_url: string
  source_name: string | null
  folder_id: string | null
  speaker_hint: string | null
  check_interval_minutes: number
  max_videos_per_check: number
  is_enabled: boolean
  title_filter: string | null
  last_run_at: string | null
  last_run_status: string | null
  created_at: string | null
  updated_at: string | null
}

export interface AutoRun {
  id: string
  auto_source_id: string
  source_name: string | null
  persona_name: string | null
  status: 'running' | 'completed' | 'failed'
  videos_found: number
  videos_new: number
  videos_queued: number
  videos_skipped: number
  error_message: string | null
  details: Array<{ url: string; title: string; action: string; error?: string }>
  started_at: string | null
  completed_at: string | null
}

export interface CreateSourceBody {
  persona_id: string
  source_type: 'channel' | 'playlist'
  youtube_url: string
  folder_id?: string | null
  speaker_hint?: string | null
  check_interval_minutes?: number
  max_videos_per_check?: number
  title_filter?: string | null
}

export interface UpdateSourceBody {
  folder_id?: string | null
  speaker_hint?: string | null
  check_interval_minutes?: number
  max_videos_per_check?: number
  title_filter?: string | null
  is_enabled?: boolean
}

export function useAutoTranscription() {
  const { authFetch } = useAuthFetch()
  const sources = useState<AutoSource[]>('auto-sources-list', () => [])
  const runs = useState<AutoRun[]>('auto-runs-list', () => [])
  const loading = useState<boolean>('auto-sources-loading', () => false)
  const error = useState<string | null>('auto-sources-error', () => null)

  async function fetchSources(): Promise<AutoSource[]> {
    loading.value = true
    error.value = null
    try {
      const result = await authFetch<AutoSource[]>('/api/auto-transcription/sources')
      sources.value = Array.isArray(result) ? result : []
      return sources.value
    } catch (e: any) {
      error.value = e.message || 'Failed to fetch sources'
      console.error('Failed to fetch auto-transcription sources:', e)
      return []
    } finally {
      loading.value = false
    }
  }

  async function createSource(body: CreateSourceBody): Promise<AutoSource | null> {
    loading.value = true
    error.value = null
    try {
      const result = await authFetch<AutoSource>('/api/auto-transcription/sources', {
        method: 'POST',
        body,
      })
      await fetchSources()
      return result
    } catch (e: any) {
      error.value = e.message || 'Failed to create source'
      console.error('Failed to create auto-transcription source:', e)
      return null
    } finally {
      loading.value = false
    }
  }

  async function updateSource(id: string, body: UpdateSourceBody): Promise<AutoSource | null> {
    loading.value = true
    error.value = null
    try {
      const result = await authFetch<AutoSource>(`/api/auto-transcription/sources/${id}`, {
        method: 'PATCH',
        body,
      })
      await fetchSources()
      return result
    } catch (e: any) {
      error.value = e.message || 'Failed to update source'
      console.error('Failed to update auto-transcription source:', e)
      return null
    } finally {
      loading.value = false
    }
  }

  async function deleteSource(id: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      await authFetch(`/api/auto-transcription/sources/${id}`, { method: 'DELETE' })
      await fetchSources()
      return true
    } catch (e: any) {
      error.value = e.message || 'Failed to delete source'
      console.error('Failed to delete auto-transcription source:', e)
      return false
    } finally {
      loading.value = false
    }
  }

  async function triggerCheck(id: string): Promise<boolean> {
    try {
      await authFetch(`/api/auto-transcription/sources/${id}/check`, { method: 'POST' })
      return true
    } catch (e: any) {
      console.error('Failed to trigger check:', e)
      return false
    }
  }

  async function fetchRuns(limit: number = 50): Promise<AutoRun[]> {
    try {
      const result = await authFetch<AutoRun[]>('/api/auto-transcription/runs', {
        query: { limit },
      })
      runs.value = Array.isArray(result) ? result : []
      return runs.value
    } catch (e: any) {
      console.error('Failed to fetch runs:', e)
      return []
    }
  }

  async function fetchRunsForSource(sourceId: string, limit: number = 20): Promise<AutoRun[]> {
    try {
      const result = await authFetch<AutoRun[]>(
        `/api/auto-transcription/sources/${sourceId}/runs`,
        { query: { limit } },
      )
      return Array.isArray(result) ? result : []
    } catch (e: any) {
      console.error('Failed to fetch source runs:', e)
      return []
    }
  }

  return {
    sources: readonly(sources),
    runs: readonly(runs),
    loading: readonly(loading),
    error: readonly(error),
    fetchSources,
    createSource,
    updateSource,
    deleteSource,
    triggerCheck,
    fetchRuns,
    fetchRunsForSource,
  }
}
