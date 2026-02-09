/**
 * Composable for Polymarket series/event API interactions
 */

export interface TermResult {
  search_term: string
  total_mentions: number
  briefings_with_term: number
  total_briefings: number
  percentage: number
  trend: string
  mentions_by_date: { date: string | null; name: string; count: number }[]
  context_matches: { transcript_id: string; transcript_name: string; date: string | null; context: string; position: number }[]
  context_total_matches: number
  context_transcripts_with_matches: number
  last_updated?: string | null
}

export interface PersonaEventMarket {
  market: {
    id: string
    question: string | null
    outcome_prices: string[] | null
    closed?: boolean
    resolved_outcome?: string | null
    closed_time?: string | null
  }
  search_config: { search_terms: string[]; min_count: number } | null
  term_results: TermResult[]
}

export interface PolymarketSeries {
  id: string
  polymarket_id: string
  slug: string
  title: string | null
  description: string | null
  image: string | null
  icon: string | null
  series_type: string | null
  recurrence: string | null
  active: boolean
  closed: boolean
  event_count?: number
  persona_ids?: string[]
  created_at: string | null
  updated_at: string | null
}

export interface PolymarketEvent {
  id: string
  slug: string
  title: string | null
  image: string | null
  start_date: string | null
  end_date: string | null
  series_id: string | null
  polymarket_id: string | null
}

export interface SeriesDetail {
  series: PolymarketSeries
  events: PolymarketEvent[]
  persona_ids: string[]
}

export interface GammaSeriesResult {
  id: string
  slug: string
  title: string | null
  description: string | null
  image: string | null
  recurrence: string | null
  active: boolean
  closed: boolean
}

export function usePolymarket() {
  async function fetchAllSeries(): Promise<PolymarketSeries[]> {
    try {
      return await $fetch<PolymarketSeries[]>('/api/polymarket/series')
    } catch (e) {
      console.error('Failed to fetch series:', e)
      return []
    }
  }

  async function addSeriesBySlug(slug: string): Promise<SeriesDetail | null> {
    try {
      return await $fetch<SeriesDetail>('/api/polymarket/series', {
        method: 'POST',
        body: { slug },
      })
    } catch (e) {
      console.error('Failed to add series:', e)
      return null
    }
  }

  async function getSeriesDetail(id: string): Promise<SeriesDetail | null> {
    try {
      return await $fetch<SeriesDetail>(`/api/polymarket/series/${id}`)
    } catch (e) {
      console.error('Failed to get series detail:', e)
      return null
    }
  }

  async function refreshSeries(id: string): Promise<SeriesDetail | null> {
    try {
      return await $fetch<SeriesDetail>(`/api/polymarket/series/${id}/refresh`, {
        method: 'POST',
      })
    } catch (e) {
      console.error('Failed to refresh series:', e)
      return null
    }
  }

  async function deleteSeries(id: string): Promise<boolean> {
    try {
      await $fetch(`/api/polymarket/series/${id}`, { method: 'DELETE' })
      return true
    } catch (e) {
      console.error('Failed to delete series:', e)
      return false
    }
  }

  async function searchSeries(query: string): Promise<GammaSeriesResult[]> {
    try {
      return await $fetch<GammaSeriesResult[]>('/api/polymarket/series/search', {
        query: { q: query },
      })
    } catch (e) {
      console.error('Failed to search series:', e)
      return []
    }
  }

  async function linkPersonaToSeries(seriesId: string, personaId: string): Promise<boolean> {
    try {
      await $fetch(`/api/polymarket/series/${seriesId}/personas`, {
        method: 'POST',
        body: { persona_id: personaId },
      })
      return true
    } catch (e) {
      console.error('Failed to link persona to series:', e)
      return false
    }
  }

  async function unlinkPersonaFromSeries(seriesId: string, personaId: string): Promise<boolean> {
    try {
      await $fetch(`/api/polymarket/series/${seriesId}/personas/${personaId}`, {
        method: 'DELETE',
      })
      return true
    } catch (e) {
      console.error('Failed to unlink persona from series:', e)
      return false
    }
  }

  async function getEventWithAnalysis(
    seriesId: string,
    eventId: string,
    personaId?: string,
  ): Promise<{ event: PolymarketEvent; markets: PersonaEventMarket[] | any[] } | null> {
    try {
      return await $fetch(`/api/polymarket/series/${seriesId}/events/${eventId}`, {
        query: personaId ? { persona_id: personaId } : undefined,
      })
    } catch (e) {
      console.error('Failed to get event with analysis:', e)
      return null
    }
  }

  async function refreshEvent(seriesId: string, eventId: string): Promise<any> {
    try {
      return await $fetch(`/api/polymarket/series/${seriesId}/events/${eventId}/refresh`, {
        method: 'POST',
      })
    } catch (e) {
      console.error('Failed to refresh event:', e)
      return null
    }
  }

  async function getSeriesForPersona(personaId: string): Promise<PolymarketSeries[]> {
    try {
      // Use the persona events endpoint to find linked series
      const events = await $fetch<any[]>(`/api/polymarket/events/${personaId}`)
      // This returns persona events; for series we'll fetch separately
      return []
    } catch {
      return []
    }
  }

  function extractSlugFromInput(input: string): string {
    const trimmed = input.trim()
    if (!trimmed) return ''
    try {
      const url = new URL(trimmed)
      const path = url.pathname
      // Match /event/slug, /market/slug, or /series/slug patterns
      const match = path.match(/\/(?:event|market|series)\/([^/]+)/)
      if (match && match[1]) return match[1]
    } catch {
      // not a URL
    }
    return trimmed
  }

  return {
    fetchAllSeries,
    addSeriesBySlug,
    getSeriesDetail,
    refreshSeries,
    deleteSeries,
    searchSeries,
    linkPersonaToSeries,
    unlinkPersonaFromSeries,
    getEventWithAnalysis,
    refreshEvent,
    getSeriesForPersona,
    extractSlugFromInput,
  }
}
