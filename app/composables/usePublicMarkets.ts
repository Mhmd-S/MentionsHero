/**
 * Composable for public market API calls.
 */
export function usePublicMarkets() {
  const { publicFetch } = usePublicApi()

  interface TopTerm {
    term: string
    mentions: number
    price: number
  }

  interface MarketEvent {
    source: 'kalshi' | 'polymarket'
    event_id: string
    event_ticker: string | null
    title: string
    strike_date: string | null
    end_date: string | null
    status: string
    image: string | null
    market_count: number
    top_terms: TopTerm[]
  }

  interface PersonaWithEvents {
    persona: {
      id: string
      name: string
      slug: string | null
      image_url: string | null
    }
    events: MarketEvent[]
  }

  interface MarketEntry {
    market_id: string
    question: string | null
    search_term: string
    price: number
    result: string | null
    status: string
    total_mentions?: number
    briefings_with_term?: number
    total_briefings?: number
    percentage?: number
    trend?: string
  }

  interface PersonaMarketsDetail {
    persona: {
      id: string
      name: string
      slug: string | null
      image_url: string | null
      description: string | null
    }
    events: Array<{
      source: 'kalshi' | 'polymarket'
      event_id: string
      event_ticker: string | null
      title: string
      strike_date: string | null
      end_date: string | null
      status: string
      image: string | null
      markets: MarketEntry[]
    }>
    is_limited: boolean
  }

  async function listPublicMarkets(): Promise<PersonaWithEvents[]> {
    return publicFetch<PersonaWithEvents[]>('/api/public/markets')
  }

  async function getPersonaMarkets(slug: string): Promise<PersonaMarketsDetail> {
    return publicFetch<PersonaMarketsDetail>(`/api/public/markets/${slug}`)
  }

  return {
    listPublicMarkets,
    getPersonaMarkets,
  }
}
