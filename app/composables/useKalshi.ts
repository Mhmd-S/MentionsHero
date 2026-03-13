/**
 * Composable for Kalshi series/event API interactions
 */

export interface TermResult {
  search_term: string
  total_mentions: number
  briefings_with_term: number
  total_briefings: number
  percentage: number
  trend: string
  mentions_by_date: { date: string | null; name: string; count: number }[]
  context_matches: { transcript_id: string; transcript_name: string; date: string | null; context: string; position: number; mention_count?: number }[]
  context_total_matches: number
  context_transcripts_with_matches: number
  last_updated?: string | null
}

export interface PersonaEventMarket {
  market: {
    id: string
    ticker: string
    question: string | null
    last_price: number | null
    yes_bid: number | null
    yes_ask: number | null
    status: string
    result: string | null
    close_time: string | null
  }
  search_config: { search_terms: string[]; min_count: number } | null
  term_results: TermResult[]
}

export interface KalshiSeries {
  id: string
  ticker: string
  title: string | null
  frequency: string | null
  category: string | null
  tags: string[]
  status: string
  event_count?: number
  created_at: string | null
  updated_at: string | null
}

export interface KalshiEvent {
  id: string
  event_ticker: string
  series_ticker: string | null
  series_id: string | null
  title: string | null
  sub_title: string | null
  status: string
  strike_date: string | null
  strike_period: string | null
}

export interface SeriesDetail {
  series: KalshiSeries
  events: KalshiEvent[]
}

export interface DiscoveredSeries {
  ticker: string
  title: string | null
  category: string | null
  tags: string[]
  frequency: string | null
  status: string
}

export interface BrowsedMarket {
  ticker: string
  word: string
  yes_bid: number | null
  yes_ask: number | null
  last_price: number | null
  result: string
  volume: number | null
  close_ts: string | null
}

export interface BrowsedEvent {
  series_ticker: string
  event_ticker: string
  event_title: string
  event_subtitle: string
  series_title: string
  total_market_count: number
  active_market_count: number
  markets: BrowsedMarket[]
  tag: string
  strike_date: string | null
}

export interface EventDetail {
  event: KalshiEvent
  markets: PersonaEventMarket[] | any[]
  series: KalshiSeries | null
}

export interface LoadPastEventsResult {
  added: number
  total_matching: number
  detail: SeriesDetail | null
}

export function useKalshi() {
  const { authFetch } = useAuthFetch();

  async function fetchAllSeries(): Promise<KalshiSeries[]> {
    try {
      return await authFetch<KalshiSeries[]>('/api/kalshi/series')
    } catch (e) {
      console.error('Failed to fetch series:', e)
      return []
    }
  }

  async function browseEvents(): Promise<Record<string, BrowsedEvent[]>> {
    try {
      return await authFetch<Record<string, BrowsedEvent[]>>('/api/kalshi/series/browse')
    } catch (e) {
      console.error('Failed to browse events:', e)
      return {}
    }
  }

  async function getSeriesDetailByTicker(ticker: string): Promise<SeriesDetail | null> {
    try {
      return await authFetch<SeriesDetail>(`/api/kalshi/series/by-ticker/${ticker}`)
    } catch (e) {
      console.error('Failed to get series by ticker:', e)
      return null
    }
  }

  async function getEventDetailByTicker(eventTicker: string, personaId?: string): Promise<EventDetail | null> {
    try {
      return await authFetch<EventDetail>(`/api/kalshi/events/by-ticker/${eventTicker}`, {
        query: personaId ? { persona_id: personaId } : undefined,
      })
    } catch (e) {
      console.error('Failed to get event by ticker:', e)
      return null
    }
  }

  async function addSeriesByTicker(ticker: string): Promise<SeriesDetail | null> {
    try {
      return await authFetch<SeriesDetail>('/api/kalshi/series', {
        method: 'POST',
        body: { ticker },
      })
    } catch (e) {
      console.error('Failed to add series:', e)
      return null
    }
  }

  async function getSeriesDetail(id: string): Promise<SeriesDetail | null> {
    try {
      return await authFetch<SeriesDetail>(`/api/kalshi/series/${id}`)
    } catch (e) {
      console.error('Failed to get series detail:', e)
      return null
    }
  }

  async function refreshSeries(id: string): Promise<SeriesDetail | null> {
    try {
      return await authFetch<SeriesDetail>(`/api/kalshi/series/${id}/refresh`, {
        method: 'POST',
      })
    } catch (e) {
      console.error('Failed to refresh series:', e)
      return null
    }
  }

  async function deleteSeries(id: string): Promise<boolean> {
    try {
      await authFetch(`/api/kalshi/series/${id}`, { method: 'DELETE' })
      return true
    } catch (e) {
      console.error('Failed to delete series:', e)
      return false
    }
  }

  async function discoverSeries(tags?: string[]): Promise<DiscoveredSeries[]> {
    try {
      const query: Record<string, string> = {}
      if (tags?.length) query.tags = tags.join(',')
      return await authFetch<DiscoveredSeries[]>('/api/kalshi/series/discover', { query })
    } catch (e) {
      console.error('Failed to discover series:', e)
      return []
    }
  }

  async function getEventWithAnalysis(
    seriesId: string,
    eventId: string,
    personaId?: string,
  ): Promise<{ event: KalshiEvent; markets: PersonaEventMarket[] | any[] } | null> {
    try {
      return await authFetch(`/api/kalshi/series/${seriesId}/events/${eventId}`, {
        query: personaId ? { persona_id: personaId } : undefined,
      })
    } catch (e) {
      console.error('Failed to get event with analysis:', e)
      return null
    }
  }

  async function refreshEvent(seriesId: string, eventId: string): Promise<any> {
    try {
      return await authFetch(`/api/kalshi/series/${seriesId}/events/${eventId}/refresh`, {
        method: 'POST',
      })
    } catch (e) {
      console.error('Failed to refresh event:', e)
      return null
    }
  }

  async function loadPastEvents(seriesId: string): Promise<LoadPastEventsResult | null> {
    try {
      return await authFetch<LoadPastEventsResult>(`/api/kalshi/series/${seriesId}/load-past-events`, {
        method: 'POST',
      })
    } catch (e) {
      console.error('Failed to load past events:', e)
      return null
    }
  }

  function extractTickerFromInput(input: string): string {
    const trimmed = input.trim()
    if (!trimmed) return ''
    try {
      const url = new URL(trimmed)
      const path = url.pathname
      // Match /markets/TICKER or /event/TICKER patterns from Kalshi URLs
      const match = path.match(/\/(?:markets|event|series)\/([^/]+)/)
      if (match && match[1]) return match[1]
    } catch {
      // not a URL
    }
    return trimmed
  }

  return {
    fetchAllSeries,
    browseEvents,
    addSeriesByTicker,
    getSeriesDetail,
    getSeriesDetailByTicker,
    getEventDetailByTicker,
    refreshSeries,
    deleteSeries,
    discoverSeries,
    getEventWithAnalysis,
    refreshEvent,
    extractTickerFromInput,
    loadPastEvents,
  }
}
