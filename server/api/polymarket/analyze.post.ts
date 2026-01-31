import { analyzeMarketOpportunity, type PolymarketMarket } from '../../utils/polymarket'

interface AnalyzeRequest {
  market: PolymarketMarket
  term: string
}

interface AnalyzeResponse {
  market_id: string
  market_question: string
  term: string
  historical_percentage: number
  market_yes_price: number
  recommendation: 'yes' | 'no' | 'skip'
  confidence: 'high' | 'medium' | 'low'
  reason: string
  expected_value: number
}

export default defineEventHandler(async (event): Promise<AnalyzeResponse> => {
  const body = await readBody<AnalyzeRequest>(event)

  if (!body.market || !body.term) {
    throw createError({
      statusCode: 400,
      message: 'market and term are required'
    })
  }

  // Get historical frequency for the term
  const termFrequency = await $fetch<{
    term: string
    percentage: number
  }>(`/api/analysis/term/${encodeURIComponent(body.term)}`)

  const analysis = analyzeMarketOpportunity(
    body.market,
    termFrequency.percentage
  )

  const yesPrice = parseFloat(body.market.outcomePrices?.[0] || '0.5')

  return {
    market_id: body.market.id,
    market_question: body.market.question,
    term: body.term,
    historical_percentage: termFrequency.percentage,
    market_yes_price: yesPrice,
    recommendation: analysis.recommendation,
    confidence: analysis.confidence,
    reason: analysis.reason,
    expected_value: analysis.expectedValue
  }
})
