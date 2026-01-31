<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAnalysis, type PolymarketMarket, type MarketAnalysis as MarketAnalysisType } from '~/composables/useAnalysis'

const { getPolymarkets, getTermFrequency, loading } = useAnalysis()

const markets = ref<PolymarketMarket[]>([])
const marketAnalyses = ref<Map<string, { analysis: MarketAnalysisType | null; termPercentage: number }>>(new Map())
const loadingMarkets = ref(false)

async function loadMarkets() {
  loadingMarkets.value = true
  markets.value = await getPolymarkets('all')
  loadingMarkets.value = false
}

async function analyzeMarket(market: PolymarketMarket) {
  // Extract term from question (simplified extraction)
  const question = market.question.toLowerCase()
  let term;

  // Try to extract the term being bet on
  const mentionMatch = question.match(/mention[s]?\s+"([^"]+)"/i) ||
                       question.match(/say\s+"([^"]+)"/i) ||
                       question.match(/"([^"]+)"\s+(?:be\s+)?(?:said|mentioned)/i)

  if (mentionMatch) {
    term = mentionMatch[1]
  } else {
    // Try to find quoted text
    const quotedMatch = question.match(/"([^"]+)"/)
    if (quotedMatch) {
      term = quotedMatch[1]
    }
  }

  if (!term) {
    marketAnalyses.value.set(market.id, {
      analysis: null,
      termPercentage: 0
    })
    return
  }

  const frequency = await getTermFrequency(term)
  if (frequency) {
    const yesPrice = parseFloat(market.outcomePrices?.[0] || '0.5')
    const estimatedProbability = frequency.percentage / 100

    // Calculate expected value
    const yesEV = estimatedProbability * (1 / yesPrice) - 1
    const noEV = (1 - estimatedProbability) * (1 / (1 - yesPrice)) - 1

    let recommendation: 'yes' | 'no' | 'skip' = 'skip'
    let confidence: 'high' | 'medium' | 'low' = 'low'
    let reason = ''
    let expectedValue = 0

    if (yesEV > 0.15) {
      recommendation = 'yes'
      expectedValue = yesEV
      if (yesEV > 0.3 && estimatedProbability > 0.8) confidence = 'high'
      else if (yesEV > 0.2) confidence = 'medium'
      reason = `Historical ${frequency.percentage.toFixed(0)}% vs market ${(yesPrice * 100).toFixed(0)}%`
    } else if (noEV > 0.15) {
      recommendation = 'no'
      expectedValue = noEV
      if (noEV > 0.3 && estimatedProbability < 0.2) confidence = 'high'
      else if (noEV > 0.2) confidence = 'medium'
      reason = `Historical ${frequency.percentage.toFixed(0)}% vs market ${(yesPrice * 100).toFixed(0)}%`
    } else {
      reason = `Market fairly priced (${frequency.percentage.toFixed(0)}% ≈ ${(yesPrice * 100).toFixed(0)}%)`
    }

    marketAnalyses.value.set(market.id, {
      analysis: {
        market_id: market.id,
        market_question: market.question,
        term,
        historical_percentage: frequency.percentage,
        market_yes_price: yesPrice,
        recommendation,
        confidence,
        reason,
        expected_value: Math.round(expectedValue * 100) / 100
      },
      termPercentage: frequency.percentage
    })
  }
}

function getRecommendationColor(rec: string) {
  switch (rec) {
    case 'yes': return 'text-green-600 dark:text-green-400'
    case 'no': return 'text-red-600 dark:text-red-400'
    default: return 'text-gray-500'
  }
}

function getConfidenceBadge(conf: string) {
  switch (conf) {
    case 'high': return 'success'
    case 'medium': return 'warning'
    default: return 'neutral'
  }
}

onMounted(() => {
  loadMarkets()
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-semibold">Polymarket Mentions Markets</h2>
      <UButton
        variant="outline"
        :loading="loadingMarkets"
        @click="loadMarkets"
      >
        Refresh Markets
      </UButton>
    </div>

    <div v-if="loadingMarkets" class="text-center py-8">
      <UIcon name="i-heroicons-arrow-path" class="w-8 h-8 animate-spin mx-auto text-gray-400" />
      <p class="mt-2 text-gray-500">Loading markets...</p>
    </div>

    <div v-else-if="markets.length === 0" class="text-center py-8 text-gray-500">
      <UIcon name="i-heroicons-chart-bar" class="w-12 h-12 mx-auto mb-4 opacity-50" />
      <p>No active markets found</p>
    </div>

    <div v-else class="space-y-3">
      <UCard
        v-for="market in markets"
        :key="market.id"
        class="hover:shadow-md transition-shadow"
      >
        <div class="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div class="flex-1">
            <h3 class="font-medium">{{ market.question }}</h3>
            <div class="flex items-center gap-4 mt-2 text-sm text-gray-500">
              <span>
                YES: <span class="font-semibold text-green-600">{{ (parseFloat(market.outcomePrices?.[0] || '0') * 100).toFixed(0) }}%</span>
              </span>
              <span>
                NO: <span class="font-semibold text-red-600">{{ (parseFloat(market.outcomePrices?.[1] || '0') * 100).toFixed(0) }}%</span>
              </span>
              <span>Volume: ${{ parseInt(market.volume || '0').toLocaleString() }}</span>
            </div>
          </div>

          <div class="flex items-center gap-2">
            <UButton
              v-if="!marketAnalyses.has(market.id)"
              size="sm"
              variant="soft"
              :loading="loading"
              @click="analyzeMarket(market)"
            >
              Analyze
            </UButton>

            <div v-else-if="marketAnalyses.get(market.id)?.analysis" class="text-right">
              <div class="flex items-center gap-2">
                <UBadge
                  :color="getConfidenceBadge(marketAnalyses.get(market.id)!.analysis!.confidence)"
                  size="xs"
                >
                  {{ marketAnalyses.get(market.id)!.analysis!.confidence }}
                </UBadge>
                <span
                  :class="['font-bold uppercase', getRecommendationColor(marketAnalyses.get(market.id)!.analysis!.recommendation)]"
                >
                  {{ marketAnalyses.get(market.id)!.analysis!.recommendation }}
                </span>
              </div>
              <p class="text-xs text-gray-500 mt-1">
                {{ marketAnalyses.get(market.id)!.analysis!.reason }}
              </p>
              <p class="text-xs mt-1">
                Historical: <span class="font-semibold">{{ marketAnalyses.get(market.id)!.termPercentage.toFixed(1) }}%</span>
                | EV: <span class="font-semibold">{{ (marketAnalyses.get(market.id)!.analysis!.expected_value * 100).toFixed(0) }}%</span>
              </p>
            </div>

            <div v-else class="text-sm text-gray-500">
              Could not extract term
            </div>
          </div>
        </div>
      </UCard>
    </div>
  </div>
</template>
