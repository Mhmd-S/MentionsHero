/**
 * Composable for triggering analytical scrapes and reading the results.
 *
 * Wraps:
 *   - POST /api/analytical/scrape        — start a date-ranged scrape (returns run_id)
 *   - GET  /api/analytical/truth-social  — browse stored Truth Social posts
 *   - GET  /api/analytical/news          — browse stored news items (outlet filter)
 *
 * Run status/progress is handled separately by useProcurementRuns().
 */

import type { SourceType } from '~/composables/useProcurementRuns'

export type ScrapeSourceType = Extract<SourceType, 'truth_social' | 'news_fox'>

export interface ScrapeOptions {
  personaId: string
  sourceType: ScrapeSourceType
  startDate: string // ISO 8601
  endDate?: string | null // ISO 8601; defaults to now server-side
}

export interface ScrapeResult {
  message: string
  run_id: string
  items_found: number
  items_new: number
  items_skipped: number
}

export interface TruthSocialPost {
  id: string
  persona_id: string
  external_id: string | null
  content: string
  post_url: string | null
  posted_at: string
  source: string
  media_urls: string[]
  engagement: Record<string, number | null> | null
  is_retruth: boolean
  created_at: string | null
}

export interface NewsItem {
  id: string
  persona_id: string
  title: string
  body: string | null
  url: string
  source_name: string | null
  source_domain: string | null
  published_at: string
  procurement_source: string
  topics: string[]
  created_at: string | null
}

export interface ListItemsOptions {
  personaId: string
  start?: string | null
  end?: string | null
  limit?: number
  source?: string | null // news only — outlet filter
}

export function useAnalyticalProcurement() {
  const { authFetch } = useAuthFetch()

  /** Start a scrape in the background. Returns the real run_id for tracking. */
  async function scrape(opts: ScrapeOptions): Promise<ScrapeResult> {
    return await authFetch<ScrapeResult>('/api/analytical/scrape', {
      method: 'POST',
      body: {
        persona_id: opts.personaId,
        source_type: opts.sourceType,
        start_date: opts.startDate,
        end_date: opts.endDate ?? null,
      },
    })
  }

  async function listTruthSocial(opts: ListItemsOptions): Promise<TruthSocialPost[]> {
    const query: Record<string, string> = { persona_id: opts.personaId }
    if (opts.start) query.start = opts.start
    if (opts.end) query.end = opts.end
    query.limit = String(opts.limit ?? 100)
    const result = await authFetch<TruthSocialPost[]>('/api/analytical/truth-social', { query })
    return Array.isArray(result) ? result : []
  }

  async function listNews(opts: ListItemsOptions): Promise<NewsItem[]> {
    const query: Record<string, string> = { persona_id: opts.personaId }
    if (opts.start) query.start = opts.start
    if (opts.end) query.end = opts.end
    if (opts.source) query.source = opts.source
    query.limit = String(opts.limit ?? 100)
    const result = await authFetch<NewsItem[]>('/api/analytical/news', { query })
    return Array.isArray(result) ? result : []
  }

  return { scrape, listTruthSocial, listNews }
}
