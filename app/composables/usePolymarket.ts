/**
 * Composable for Polymarket event API interactions
 */

import type { TermResult } from '~/components/TermSection.vue'

export interface PolyEvent {
  id: string
  poly_id: string
  slug: string
  title: string | null
  description: string | null
  start_date: string | null
  end_date: string | null
  active: boolean
  closed: boolean
  volume: number | null
  liquidity: number | null
  image: string | null
  neg_risk: boolean
  created_at: string | null
  updated_at: string | null
  market_count?: number
}

export interface PolyMarket {
  id: string
  poly_id: string
  event_id: string
  slug: string | null
  question: string | null
  group_item_title: string | null
  outcome_prices: number[] | null
  outcomes: string[] | null
  last_trade_price: number | null
  one_day_price_change: number | null
  volume: number | null
  active: boolean
  closed: boolean
  closed_time: string | null
  neg_risk: boolean
  result: string | null
}

export interface PolyPersonaMarket {
  market: PolyMarket
  search_config: { search_terms: string[]; min_count: number } | null
  term_results: TermResult[]
}

export interface PolyEventDetail {
  event: PolyEvent
  markets: PolyPersonaMarket[] | PolyMarket[]
}

export interface PolySearchResult {
  poly_id: string
  slug: string
  title: string | null
  image: string | null
  market_count: number
  volume: number | null
  end_date: string | null
}

export function usePolymarket() {
  const { authFetch } = useAuthFetch()

  async function searchEvents(q: string, limit: number = 20, mentionsOnly: boolean = true): Promise<PolySearchResult[]> {
    try {
      return await authFetch<PolySearchResult[]>('/api/polymarket/events/search', {
        query: { q, limit, mentions_only: mentionsOnly },
      })
    } catch (e) {
      console.error('Failed to search Polymarket events:', e)
      return []
    }
  }

  async function listStoredEvents(): Promise<PolyEvent[]> {
    try {
      return await authFetch<PolyEvent[]>('/api/polymarket/events')
    } catch (e) {
      console.error('Failed to list stored Polymarket events:', e)
      return []
    }
  }

  async function addEvent(slug: string): Promise<PolyEventDetail | null> {
    try {
      return await authFetch<PolyEventDetail>('/api/polymarket/events', {
        method: 'POST',
        body: { slug },
      })
    } catch (e) {
      console.error('Failed to add Polymarket event:', e)
      return null
    }
  }

  async function getEventDetail(eventId: string, personaId?: string): Promise<PolyEventDetail | null> {
    try {
      return await authFetch<PolyEventDetail>(`/api/polymarket/events/${eventId}`, {
        query: personaId ? { persona_id: personaId } : undefined,
      })
    } catch (e) {
      console.error('Failed to get Polymarket event detail:', e)
      return null
    }
  }

  async function refreshEvent(eventId: string): Promise<any> {
    try {
      return await authFetch(`/api/polymarket/events/${eventId}/refresh`, {
        method: 'POST',
      })
    } catch (e) {
      console.error('Failed to refresh Polymarket event:', e)
      return null
    }
  }

  async function reanalyzeEvent(eventId: string, personaId: string): Promise<any> {
    try {
      return await authFetch(`/api/polymarket/events/${eventId}/reanalyze?persona_id=${personaId}`, {
        method: 'POST',
      })
    } catch (e) {
      console.error('Failed to reanalyze Polymarket event:', e)
      return null
    }
  }

  async function deleteEvent(eventId: string): Promise<boolean> {
    try {
      await authFetch(`/api/polymarket/events/${eventId}`, { method: 'DELETE' })
      return true
    } catch (e) {
      console.error('Failed to delete Polymarket event:', e)
      return false
    }
  }

  function extractSlugFromInput(input: string): string {
    const trimmed = input.trim()
    if (!trimmed) return ''
    try {
      const url = new URL(trimmed)
      const match = url.pathname.match(/\/event\/([^/?#]+)/)
      if (match && match[1]) return match[1]
    } catch {
      // not a URL
    }
    return trimmed
  }

  return {
    searchEvents,
    listStoredEvents,
    addEvent,
    getEventDetail,
    refreshEvent,
    reanalyzeEvent,
    deleteEvent,
    extractSlugFromInput,
  }
}
