import {
  getLeavittMarkets,
  getMentionsMarkets,
  type PolymarketMarket
} from '../../utils/polymarket'

interface MarketsResponse {
  markets: PolymarketMarket[]
  count: number
  source: 'live' | 'mock'
}

export default defineEventHandler(async (event): Promise<MarketsResponse> => {
  const query = getQuery(event)
  const type = query.type as string || 'all'

  let markets: PolymarketMarket[] = []

  try {
    if (type === 'mentions') {
      markets = await getMentionsMarkets()
    } else if (type === 'leavitt') {
      markets = await getLeavittMarkets()
    } else {
      // Fetch both and deduplicate
      const [leavitt, mentions] = await Promise.all([
        getLeavittMarkets(),
        getMentionsMarkets()
      ])

      const seen = new Set<string>()
      for (const market of [...leavitt, ...mentions]) {
        if (!seen.has(market.id)) {
          seen.add(market.id)
          markets.push(market)
        }
      }
    }

    return {
      markets,
      count: markets.length,
      source: 'live'
    }
  } catch (error) {
    console.error('Failed to fetch Polymarket markets:', error)

    // Return mock data for development/testing
    return {
      markets: getMockMarkets(),
      count: getMockMarkets().length,
      source: 'mock'
    }
  }
})

function getMockMarkets(): PolymarketMarket[] {
  return [
    {
      id: 'mock-1',
      question: 'Will Karoline Leavitt mention "tariffs" in her next briefing?',
      slug: 'leavitt-tariffs-mention',
      description: 'Resolves YES if "tariffs" is said during the next White House press briefing.',
      outcomes: ['Yes', 'No'],
      outcomePrices: ['0.72', '0.28'],
      volume: '15420',
      liquidity: '8500',
      endDate: new Date(Date.now() + 86400000).toISOString(),
      active: true,
      closed: false,
      category: 'Politics'
    },
    {
      id: 'mock-2',
      question: 'Will "fake news" be mentioned in the next press briefing?',
      slug: 'fake-news-mention',
      description: 'Resolves YES if the phrase "fake news" is spoken during the briefing.',
      outcomes: ['Yes', 'No'],
      outcomePrices: ['0.45', '0.55'],
      volume: '8230',
      liquidity: '4200',
      endDate: new Date(Date.now() + 86400000).toISOString(),
      active: true,
      closed: false,
      category: 'Politics'
    },
    {
      id: 'mock-3',
      question: 'Will Elon Musk be mentioned in White House briefing?',
      slug: 'elon-musk-mention',
      description: 'Resolves YES if Elon Musk is mentioned by name.',
      outcomes: ['Yes', 'No'],
      outcomePrices: ['0.35', '0.65'],
      volume: '22100',
      liquidity: '12000',
      endDate: new Date(Date.now() + 86400000).toISOString(),
      active: true,
      closed: false,
      category: 'Politics'
    },
    {
      id: 'mock-4',
      question: 'Will "the American people" be said in next briefing?',
      slug: 'american-people-mention',
      description: 'Resolves YES if the phrase "the American people" is spoken.',
      outcomes: ['Yes', 'No'],
      outcomePrices: ['0.88', '0.12'],
      volume: '5600',
      liquidity: '2800',
      endDate: new Date(Date.now() + 86400000).toISOString(),
      active: true,
      closed: false,
      category: 'Politics'
    }
  ]
}
