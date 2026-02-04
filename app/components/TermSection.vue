<script setup lang="ts">
interface Props {
  marketId: string
  question: string | null
  searchTerms: string[]
  resultCount: number | null
  resultLastUpdated: string | null
  outcomePrice: string | null
  personaId: string
  // Cached analysis data (optional - will fetch if missing)
  briefingsWithTerm?: number | null
  totalBriefings?: number | null
  percentage?: number | null
  trend?: string | null
  mentionsByDate?: { date: string | null; name: string; count: number }[] | null
}

const props = defineProps<Props>()

const primaryTerm = computed(() => props.searchTerms?.[0] || '')

const yesPrice = computed(() => {
  if (!props.outcomePrice) return null
  return (parseFloat(props.outcomePrice) * 100).toFixed(0)
})

// Local state for fetched data (when cached data is missing)
const loading = ref(false)
const fetchedData = ref<{
  total_mentions: number
  briefings_with_term: number
  total_briefings: number
  percentage: number
  trend: string
  mentions_by_date: { date: string | null; name: string; count: number }[]
} | null>(null)

// Context viewing state
const showContext = ref(false)
const loadingContext = ref(false)
const contextData = ref<{
  query: string
  total_matches: number
  transcripts_with_matches: number
  matches: { transcript_id: string; transcript_name: string; date: string | null; context: string; position: number }[]
} | null>(null)

// Use cached data if available, otherwise use fetched data
const totalMentions = computed(() => props.resultCount ?? fetchedData.value?.total_mentions ?? null)
const briefings = computed(() => props.briefingsWithTerm ?? fetchedData.value?.briefings_with_term ?? null)
const totalBriefings = computed(() => props.totalBriefings ?? fetchedData.value?.total_briefings ?? null)
const pct = computed(() => props.percentage ?? fetchedData.value?.percentage ?? null)
const trendValue = computed(() => props.trend ?? fetchedData.value?.trend ?? null)
const mentions = computed(() => props.mentionsByDate ?? fetchedData.value?.mentions_by_date ?? null)

const hasData = computed(() => totalMentions.value !== null)
const needsFetch = computed(() =>
  primaryTerm.value &&
  props.briefingsWithTerm === null &&
  props.briefingsWithTerm === undefined &&
  !fetchedData.value
)

async function fetchTermData() {
  if (!primaryTerm.value || fetchedData.value) return

  loading.value = true
  try {
    const data = await $fetch(`/api/analysis/term/${encodeURIComponent(primaryTerm.value)}`, {
      params: { persona_id: props.personaId }
    })
    fetchedData.value = data as typeof fetchedData.value
  } catch (e) {
    console.error('Failed to fetch term data:', e)
  } finally {
    loading.value = false
  }
}

async function fetchContext() {
  if (!primaryTerm.value || contextData.value) return

  loadingContext.value = true
  try {
    const data = await $fetch('/api/analysis/search', {
      method: 'POST',
      body: {
        query: primaryTerm.value,
        context_chars: 300,
        speakers: null // Could filter by persona aliases if needed
      }
    })
    contextData.value = data as typeof contextData.value
  } catch (e) {
    console.error('Failed to fetch context:', e)
  } finally {
    loadingContext.value = false
  }
}

function toggleContext() {
  showContext.value = !showContext.value
  if (showContext.value && !contextData.value) {
    fetchContext()
  }
}

function highlightTerm(text: string): string {
  if (!primaryTerm.value) return text
  const regex = new RegExp(`(${primaryTerm.value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
  return text.replace(regex, '<mark class="bg-yellow-200 dark:bg-yellow-800 px-0.5 rounded">$1</mark>')
}

// Fetch if cached data is missing
onMounted(() => {
  if (needsFetch.value) {
    fetchTermData()
  }
})
</script>

<template>
  <div class="border border-gray-200 dark:border-gray-700 rounded-lg mb-2 overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-800/50">
      <span class="text-sm font-medium truncate flex-1">{{ question || '—' }}</span>
      <div class="flex items-center gap-2 shrink-0">
        <UBadge v-if="searchTerms?.length" color="primary" variant="subtle" size="xs">
          "{{ primaryTerm }}"
        </UBadge>
        <span v-if="yesPrice" class="text-sm font-semibold text-primary">
          {{ yesPrice }}%
        </span>
      </div>
    </div>

    <!-- Details -->
    <div class="px-3 py-2">
      <!-- Loading -->
      <div v-if="loading" class="flex items-center justify-center py-3">
        <UIcon name="i-heroicons-arrow-path" class="w-4 h-4 animate-spin" />
      </div>

      <!-- Has Data -->
      <div v-else-if="hasData" class="space-y-2">
        <!-- Stats Grid -->
        <div class="grid grid-cols-4 gap-2 text-center">
          <div class="p-2 bg-gray-50 dark:bg-gray-800 rounded">
            <div class="text-lg font-bold text-primary">{{ totalMentions ?? 0 }}</div>
            <div class="text-xs text-gray-500">Total</div>
          </div>
          <div class="p-2 bg-gray-50 dark:bg-gray-800 rounded">
            <div class="text-lg font-bold text-primary">{{ briefings ?? 0 }}</div>
            <div class="text-xs text-gray-500">Briefings</div>
          </div>
          <div class="p-2 bg-gray-50 dark:bg-gray-800 rounded">
            <div class="text-lg font-bold" :class="(pct ?? 0) >= 50 ? 'text-green-500' : 'text-orange-500'">
              {{ pct ?? 0 }}%
            </div>
            <div class="text-xs text-gray-500">Rate</div>
          </div>
          <div class="p-2 bg-gray-50 dark:bg-gray-800 rounded">
            <div class="text-lg font-bold capitalize" :class="{
              'text-green-500': trendValue === 'increasing',
              'text-red-500': trendValue === 'decreasing',
              'text-gray-500': !trendValue || trendValue === 'stable'
            }">
              {{ trendValue || 'stable' }}
            </div>
            <div class="text-xs text-gray-500">Trend</div>
          </div>
        </div>

        <!-- Recent Mentions (horizontal scroll) -->
        <div v-if="mentions?.length" class="text-xs">
          <div class="flex items-center justify-between mb-1">
            <span class="font-medium text-gray-600 dark:text-gray-400">Recent:</span>
            <UButton size="xs" variant="ghost" @click="toggleContext">
              {{ showContext ? 'Hide' : 'View' }} Context
            </UButton>
          </div>
          <div class="flex gap-2 overflow-x-auto pb-1">
            <UBadge
              v-for="mention in mentions"
              :key="(mention.date || '') + mention.name"
              color="neutral"
              variant="subtle"
              size="xs"
              class="shrink-0"
            >
              {{ mention.name }} ({{ mention.count }}x)
            </UBadge>
          </div>
        </div>

        <!-- Context Detail View -->
        <div v-if="showContext" class="mt-2 border-t pt-2">
          <div v-if="loadingContext" class="flex items-center justify-center py-3">
            <UIcon name="i-heroicons-arrow-path" class="w-4 h-4 animate-spin" />
          </div>
          <div v-else-if="contextData?.matches?.length" class="space-y-2 max-h-64 overflow-y-auto">
            <div
              v-for="(match, idx) in contextData.matches.slice(0, 10)"
              :key="idx"
              class="p-2 bg-gray-50 dark:bg-gray-800 rounded text-xs"
            >
              <div class="flex items-center justify-between mb-1">
                <span class="font-medium text-primary">{{ match.transcript_name }}</span>
                <span v-if="match.date" class="text-gray-400">{{ match.date }}</span>
              </div>
              <p class="text-gray-600 dark:text-gray-400 leading-relaxed" v-html="highlightTerm(match.context)" />
            </div>
          </div>
          <div v-else class="text-xs text-gray-500 py-2">
            No context matches found.
          </div>
        </div>
      </div>

      <!-- No search term -->
      <div v-else-if="!primaryTerm" class="text-xs text-gray-500 py-1">
        No search term found in question.
      </div>

      <!-- No data yet -->
      <div v-else class="text-xs text-gray-500 py-1">
        Click refresh to analyze.
      </div>
    </div>
  </div>
</template>
