/**
 * Composable for per-transcript metadata bundle (event_tag + context_window).
 *
 * Reads:  GET /api/analytical/event-tags/{transcript_id}
 *         GET /api/analytical/context-windows/{transcript_id}
 * Writes: PATCH /api/analytical/event-tags/{transcript_id}
 */

export type EventTypeValue =
  | 'rally'
  | 'press_conference'
  | 'press_briefing'
  | 'interview'
  | 'prepared_remarks'
  | 'signing_ceremony'
  | 'bilateral_meeting'
  | 'cabinet_meeting'
  | 'reception'
  | 'ceremony'
  | 'summit'
  | 'roundtable'
  | 'announcement'
  | 'greeting'
  | 'troop_address'
  | 'other'

export const EVENT_TYPE_VALUES: EventTypeValue[] = [
  'rally',
  'press_conference',
  'press_briefing',
  'interview',
  'prepared_remarks',
  'signing_ceremony',
  'bilateral_meeting',
  'cabinet_meeting',
  'reception',
  'ceremony',
  'summit',
  'roundtable',
  'announcement',
  'greeting',
  'troop_address',
  'other',
]

export interface EventTag {
  id: string
  transcript_id: string
  event_type: EventTypeValue
  city: string | null
  state: string | null
  country: string | null
  venue: string | null
  event_time: string | null
  classification_source: 'manual' | 'auto_ddgs' | 'auto_llm'
  created_at: string | null
  updated_at: string | null
}

export interface EventTagPatch {
  event_type?: EventTypeValue
  city?: string | null
  state?: string | null
  country?: string | null
  venue?: string | null
  event_time?: string | null
}

export interface BulkBackfillMetadataResult {
  message: string
  run_id: string
  candidates: number
  succeeded: number
  failed: number
}

export interface BulkBackfillOptions {
  force?: boolean
  limit?: number
}

export interface ContextWindow {
  id: string
  transcript_id: string
  persona_id: string
  window_start: string
  window_end: string
  truth_social_post_count: number
  news_item_count: number
  news_sentiment_avg: number | null
  top_news_topics: string[]
  truth_social_topics: string[]
  market_snapshot: Record<string, unknown> | null
  computed_at: string | null
}

export function useTranscriptMetadata() {
  const { authFetch } = useAuthFetch()

  async function getEventTag(transcriptId: string): Promise<EventTag | null> {
    try {
      const result = await authFetch<EventTag>(
        `/api/analytical/event-tags/${transcriptId}`,
      )
      return result || null
    } catch (e: any) {
      if (e?.statusCode === 404 || e?.response?.status === 404) return null
      console.error('Failed to load event tag:', e)
      return null
    }
  }

  async function updateEventTag(
    transcriptId: string,
    patch: EventTagPatch,
  ): Promise<EventTag | null> {
    try {
      const result = await authFetch<EventTag>(
        `/api/analytical/event-tags/${transcriptId}`,
        { method: 'PATCH', body: patch },
      )
      return result
    } catch (e: any) {
      console.error('Failed to update event tag:', e)
      throw e
    }
  }

  async function getContextWindow(
    transcriptId: string,
    personaId: string,
  ): Promise<ContextWindow | null> {
    try {
      const result = await authFetch<ContextWindow>(
        `/api/analytical/context-windows/${transcriptId}`,
        { query: { persona_id: personaId } },
      )
      return result || null
    } catch (e: any) {
      if (e?.statusCode === 404 || e?.response?.status === 404) return null
      console.error('Failed to load context window:', e)
      return null
    }
  }

  async function bulkBackfillMetadata(
    personaId: string,
    opts: BulkBackfillOptions = {},
  ): Promise<BulkBackfillMetadataResult> {
    const query: Record<string, string> = {}
    if (opts.force) query.force = 'true'
    if (opts.limit !== undefined) query.limit = String(opts.limit)
    return await authFetch<BulkBackfillMetadataResult>(
      `/api/analytical/metadata/backfill/${personaId}`,
      { method: 'POST', query },
    )
  }

  return {
    getEventTag,
    updateEventTag,
    getContextWindow,
    bulkBackfillMetadata,
    EVENT_TYPE_VALUES,
  }
}
