/**
 * Polymarket API Client
 *
 * Fetches prediction markets from Polymarket's public API.
 * Focuses on "mentions markets" related to press briefings.
 *
 * IMPORTANT: Leavitt markets are structured as EVENTS with nested sub-markets,
 * not as top-level markets. We must use the /events API.
 */

const POLYMARKET_CLOB_API = 'https://clob.polymarket.com'
const GAMMA_API_BASE = 'https://gamma-api.polymarket.com'

// Types for the Gamma API response structure
export interface PolymarketTag {
  id: string
  label: string
  slug: string
}

export interface PolymarketMarket {
  id: string
  question: string
  slug: string
  description: string
  outcomes: string[]
  outcomePrices: string[]
  volume: string
  liquidity: string
  endDate: string
  active: boolean
  closed: boolean
  category: string
  image?: string
  conditionId?: string
  tokens?: Array<{
    token_id: string
    outcome: string
  }>
}

export interface PolymarketEvent {
  id: string
  slug: string
  title: string
  description: string
  startDate: string
  endDate: string
  active: boolean
  closed: boolean
  markets: PolymarketMarket[]
  tags?: PolymarketTag[]
  image?: string
}

export interface PolymarketCondition {
  condition_id: string
  question: string
  outcomes: string[]
  tokens: Array<{
    token_id: string
    outcome: string
    price: number
  }>
}

export interface ClobPrice {
  price: string
  side: 'buy' | 'sell'
}

/**
 * Fetch all available tags/categories
 */
export async function getTags(limit = 100): Promise<PolymarketTag[]> {
  try {
    const response = await $fetch<PolymarketTag[]>(
      `${GAMMA_API_BASE}/tags`,
      {
        query: { limit }
      }
    )
    return response || []
  } catch (error) {
    console.error('Failed to fetch tags:', error)
    return []
  }
}

/**
 * Fetch events by tag ID
 */
export async function getEventsByTag(
  tagId: string,
  options: { active?: boolean; closed?: boolean; limit?: number } = {}
): Promise<PolymarketEvent[]> {
  try {
    const response = await $fetch<PolymarketEvent[]>(
      `${GAMMA_API_BASE}/events`,
      {
        query: {
          tag_id: tagId,
          active: options.active ?? true,
          closed: options.closed ?? false,
          limit: options.limit ?? 50
        }
      }
    )
    return response || []
  } catch (error) {
    console.error('Failed to fetch events by tag:', error)
    return []
  }
}

/**
 * Search for events by slug pattern or title
 */
export async function searchEvents(
  searchTerm: string,
  options: { active?: boolean; closed?: boolean; limit?: number } = {}
): Promise<PolymarketEvent[]> {
  try {
    // Try slug-based search first
    const response = await $fetch<PolymarketEvent[]>(
      `${GAMMA_API_BASE}/events`,
      {
        query: {
          slug: searchTerm,
          active: options.active ?? true,
          closed: options.closed ?? false,
          limit: options.limit ?? 50
        }
      }
    )
    return response || []
  } catch (error) {
    console.error('Failed to search events:', error)
    return []
  }
}

/**
 * Fetch a specific event by slug
 */
export async function getEventBySlug(slug: string): Promise<PolymarketEvent | null> {
  try {
    const response = await $fetch<PolymarketEvent>(
      `${GAMMA_API_BASE}/events/${slug}`
    )
    return response
  } catch (error) {
    console.error(`Failed to fetch event ${slug}:`, error)
    return null
  }
}

/**
 * Fetch all active events and filter by keywords
 */
export async function getAllActiveEvents(
  limit = 100
): Promise<PolymarketEvent[]> {
  try {
    const response = await $fetch<PolymarketEvent[]>(
      `${GAMMA_API_BASE}/events`,
      {
        query: {
          active: true,
          closed: false,
          limit
        }
      }
    )
    return response || []
  } catch (error) {
    console.error('Failed to fetch active events:', error)
    return []
  }
}

/**
 * Deduplicate events by ID, preserving first occurrence
 */
function dedupeEvents(events: PolymarketEvent[]): PolymarketEvent[] {
  const seenIds = new Set<string>()
  return events.filter(event => {
    if (seenIds.has(event.id)) return false
    seenIds.add(event.id)
    return true
  })
}

/**
 * Get events related to Leavitt/White House press briefings
 *
 * Strategy:
 * 1. Try tag-based discovery using getTags() + getEventsByTag() for server-side filtering
 * 2. Fall back to keyword search if no relevant tags found
 */
export async function getLeavittEvents(): Promise<PolymarketEvent[]> {
  try {
    // 1. Try tag-based discovery first
    const tags = await getTags(100)
    const relevantTags = tags.filter(tag => {
      const slug = tag.slug?.toLowerCase() || ''
      const label = tag.label?.toLowerCase() || ''
      return ['leavitt', 'karoline', 'briefing', 'press'].some(k =>
        slug.includes(k) || label.includes(k)
      )
    })

    if (relevantTags.length > 0) {
      const eventArrays = await Promise.all(
        relevantTags.map(tag => getEventsByTag(tag.id, { active: true, closed: false, limit: 50 }))
      )
      const events = dedupeEvents(eventArrays.flat())
      if (events.length > 0) {
        return events
      }
    }

    // 2. Fallback to keyword search (fetch all active events, filter client-side)
    const allEvents: PolymarketEvent[] = []
    const seenIds = new Set<string>()
    const searchPatterns = [
      'leavitt',
      'karoline',
      'briefing',
      'press-secretary',
      'white-house-press'
    ]

    const events = await getAllActiveEvents(200)

    for (const event of events) {
      const titleLower = event.title?.toLowerCase() || ''
      const slugLower = event.slug?.toLowerCase() || ''
      const descLower = event.description?.toLowerCase() || ''

      const matches = searchPatterns.some(pattern =>
        titleLower.includes(pattern) ||
        slugLower.includes(pattern) ||
        descLower.includes(pattern)
      )

      if (matches && !seenIds.has(event.id)) {
        seenIds.add(event.id)
        allEvents.push(event)
      }
    }

    return allEvents
  } catch (error) {
    console.error('Failed to fetch Leavitt events:', error)
    return []
  }
}

/**
 * Get "mentions" style markets from events
 * These are typically sub-markets within briefing events asking
 * "Will X be mentioned?" or "Will she say X?"
 */
export async function getMentionsMarkets(): Promise<PolymarketMarket[]> {
  const markets: PolymarketMarket[] = []

  try {
    const events = await getLeavittEvents()

    for (const event of events) {
      if (event.markets && event.markets.length > 0) {
        // Filter to only "mentions" style markets
        const mentionsMarkets = event.markets.filter(market => {
          const q = market.question?.toLowerCase() || ''
          return (
            q.includes('mention') ||
            q.includes('will') && q.includes('say') ||
            q.includes('said') ||
            q.includes('refer to')
          )
        })
        markets.push(...mentionsMarkets)
      }
    }
  } catch (error) {
    console.error('Failed to fetch mentions markets:', error)
  }

  return markets
}

/**
 * Get all markets from Leavitt events (not just mentions-style)
 */
export async function getLeavittMarkets(): Promise<PolymarketMarket[]> {
  const markets: PolymarketMarket[] = []

  try {
    const events = await getLeavittEvents()

    for (const event of events) {
      if (event.markets && event.markets.length > 0) {
        markets.push(...event.markets)
      }
    }
  } catch (error) {
    console.error('Failed to fetch Leavitt markets:', error)
  }

  return markets
}

/**
 * Get current price for a token from CLOB
 */
export async function getTokenPrice(
  tokenId: string,
  side: 'buy' | 'sell' = 'buy'
): Promise<number | null> {
  try {
    const response = await $fetch<{ price: string }>(
      `${POLYMARKET_CLOB_API}/price`,
      {
        query: {
          token_id: tokenId,
          side
        }
      }
    )
    return response?.price ? parseFloat(response.price) : null
  } catch (error) {
    console.error(`Failed to fetch price for token ${tokenId}:`, error)
    return null
  }
}

/**
 * Get market by slug or ID (legacy compatibility)
 */
export async function getMarket(slugOrId: string): Promise<PolymarketMarket | null> {
  try {
    const response = await $fetch<PolymarketMarket>(
      `${GAMMA_API_BASE}/markets/${slugOrId}`
    )
    return response
  } catch (error) {
    console.error(`Failed to fetch market ${slugOrId}:`, error)
    return null
  }
}

/**
 * Get market prices from CLOB (legacy compatibility)
 */
export async function getMarketPrices(conditionId: string): Promise<PolymarketCondition | null> {
  try {
    const response = await $fetch<PolymarketCondition>(
      `${POLYMARKET_CLOB_API}/markets/${conditionId}`
    )
    return response
  } catch (error) {
    console.error(`Failed to fetch prices for ${conditionId}:`, error)
    return null
  }
}

/**
 * Extract the betting term from a market question
 * e.g., "Will she say 'tariffs'?" -> "tariffs"
 */
export function extractTermFromQuestion(question: string): string | null {
  const questionLower = question.toLowerCase()

  // Pattern 1: "mention 'X'" or "say 'X'"
  const quoteMatch = question.match(/(?:mention|say)\s+['""]([^'""]+)['""]|['""]([^'""]+)['""]/)
  if (quoteMatch) {
    return quoteMatch[1] || quoteMatch[2]
  }

  // Pattern 2: "mention X" without quotes (look for capitalized term)
  const mentionMatch = question.match(/(?:mention|say|refer to)\s+([A-Z][a-zA-Z\s]+?)(?:\s+(?:in|during|at)|\?|$)/i)
  if (mentionMatch) {
    return mentionMatch[1].trim()
  }

  return null
}

/**
 * Analyze market and provide betting insight
 */
export function analyzeMarketOpportunity(
  market: PolymarketMarket,
  historicalPercentage: number
): {
  recommendation: 'yes' | 'no' | 'skip'
  confidence: 'high' | 'medium' | 'low'
  reason: string
  expectedValue: number
} {
  // Parse current market price (probability)
  const yesPriceStr = market.outcomePrices?.[0]
  const yesPrice = yesPriceStr ? parseFloat(yesPriceStr) : 0.5

  // Historical percentage is our estimated true probability
  const estimatedProbability = historicalPercentage / 100

  // Calculate expected value
  // If we bet on YES: EV = (prob * payout) - (1 - prob) * stake
  // For $1 bet at price p: EV = prob * (1/p) - (1-prob)
  const yesEV = estimatedProbability * (1 / yesPrice) - 1
  const noEV = (1 - estimatedProbability) * (1 / (1 - yesPrice)) - 1

  // Determine recommendation
  let recommendation: 'yes' | 'no' | 'skip' = 'skip'
  let confidence: 'high' | 'medium' | 'low' = 'low'
  let reason = ''
  let expectedValue = 0

  if (yesEV > 0.15) {
    recommendation = 'yes'
    expectedValue = yesEV
    if (yesEV > 0.3 && estimatedProbability > 0.8) {
      confidence = 'high'
      reason = `Term appears in ${historicalPercentage.toFixed(0)}% of briefings but market only prices YES at ${(yesPrice * 100).toFixed(0)}%`
    } else if (yesEV > 0.2) {
      confidence = 'medium'
      reason = `Positive expected value: historical ${historicalPercentage.toFixed(0)}% vs market ${(yesPrice * 100).toFixed(0)}%`
    } else {
      confidence = 'low'
      reason = `Slight edge detected: ${historicalPercentage.toFixed(0)}% historical vs ${(yesPrice * 100).toFixed(0)}% market`
    }
  } else if (noEV > 0.15) {
    recommendation = 'no'
    expectedValue = noEV
    if (noEV > 0.3 && estimatedProbability < 0.2) {
      confidence = 'high'
      reason = `Term only appears in ${historicalPercentage.toFixed(0)}% of briefings but market prices YES at ${(yesPrice * 100).toFixed(0)}%`
    } else if (noEV > 0.2) {
      confidence = 'medium'
      reason = `Negative edge: historical ${historicalPercentage.toFixed(0)}% vs market ${(yesPrice * 100).toFixed(0)}%`
    } else {
      confidence = 'low'
      reason = `Slight NO edge: ${historicalPercentage.toFixed(0)}% historical vs ${(yesPrice * 100).toFixed(0)}% market`
    }
  } else {
    reason = `Market fairly priced: historical ${historicalPercentage.toFixed(0)}% ≈ market ${(yesPrice * 100).toFixed(0)}%`
  }

  return {
    recommendation,
    confidence,
    reason,
    expectedValue: Math.round(expectedValue * 100) / 100
  }
}
