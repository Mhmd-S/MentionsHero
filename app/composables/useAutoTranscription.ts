/**
 * Composable for auto-transcription source management (manual-trigger only).
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
  max_videos_per_check: number
  backfill_limit: number | null
  title_filter: string | null
  created_at: string | null
  updated_at: string | null
}

export interface CreateSourceBody {
  persona_id: string
  source_type: 'channel' | 'playlist'
  youtube_url: string
  folder_id?: string | null
  max_videos_per_check?: number
  backfill_limit?: number | null
  title_filter?: string | null
}

export interface UpdateSourceBody {
  folder_id?: string | null
  max_videos_per_check?: number
  backfill_limit?: number | null
  title_filter?: string | null
}

export type RunDetailAction = 'queued' | 'filtered' | 'exists' | 'error'

export interface RunDetail {
  url: string
  title: string
  action: RunDetailAction
  error?: string
}

export interface RunResult {
  videos_found: number
  videos_filtered: number
  videos_existing: number
  videos_queued: number
  details: RunDetail[]
}

export interface TimelineEntry {
  id: string
  auto_source_id: string
  source_name: string | null
  persona_id: string | null
  persona_name: string | null
  youtube_url: string
  video_title: string | null
  action: 'transcribed' | 'filtered' | 'skipped'
  job_id: string | null
  job_status: string | null
  job_error: string | null
  transcript_id: string | null
  created_at: string | null
}

export function useAutoTranscription() {
  const { authFetch } = useAuthFetch()
  const sources = useState<AutoSource[]>('auto-sources-list', () => [])
  const timeline = useState<TimelineEntry[]>('auto-timeline-list', () => [])
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

  async function runSource(id: string): Promise<RunResult | null> {
    try {
      return await authFetch<RunResult>(`/api/auto-transcription/sources/${id}/run`, {
        method: 'POST',
      })
    } catch (e: any) {
      console.error('Failed to run source:', e)
      throw e
    }
  }

  async function backfillSource(id: string): Promise<RunResult | null> {
    try {
      return await authFetch<RunResult>(`/api/auto-transcription/sources/${id}/backfill`, {
        method: 'POST',
      })
    } catch (e: any) {
      console.error('Failed to backfill source:', e)
      throw e
    }
  }

  async function fetchTimeline(limit: number = 200): Promise<TimelineEntry[]> {
    try {
      const result = await authFetch<TimelineEntry[]>('/api/auto-transcription/timeline', {
        query: { limit },
      })
      timeline.value = Array.isArray(result) ? result : []
      return timeline.value
    } catch (e: any) {
      console.error('Failed to fetch timeline:', e)
      return []
    }
  }

  return {
    sources: readonly(sources),
    timeline: readonly(timeline),
    loading: readonly(loading),
    error: readonly(error),
    fetchSources,
    createSource,
    updateSource,
    deleteSource,
    runSource,
    backfillSource,
    fetchTimeline,
  }
}
