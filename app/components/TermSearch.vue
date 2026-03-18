<script setup lang="ts">
import { useAnalysis, type TermFrequency, type SearchResult } from '~/composables/useAnalysis'

const { getTermFrequency, searchTerm, loading } = useAnalysis()

const searchQuery = ref('')
const caseSensitive = ref(false)
const result = ref<TermFrequency | null>(null)
const searchResults = ref<SearchResult | null>(null)

let searchTimer: ReturnType<typeof setTimeout> | null = null

watch(searchQuery, (val) => {
  if (searchTimer) clearTimeout(searchTimer)
  if (!val.trim()) {
    result.value = null
    searchResults.value = null
    return
  }
  searchTimer = setTimeout(() => handleSearch(), 500)
})

async function handleSearch() {
  if (!searchQuery.value.trim()) return

  const [freq, context] = await Promise.all([
    getTermFrequency(searchQuery.value, caseSensitive.value),
    searchTerm(searchQuery.value),
  ])
  result.value = freq
  searchResults.value = context
}

function getTrendIcon(trend: string) {
  switch (trend) {
    case 'increasing': return 'i-lucide-trending-up'
    case 'decreasing': return 'i-lucide-trending-down'
    default: return 'i-lucide-minus'
  }
}

function getTrendColor(trend: string) {
  switch (trend) {
    case 'increasing': return 'text-green-500'
    case 'decreasing': return 'text-red-500'
    default: return 'text-gray-500'
  }
}

function highlightMatch(text: string, query: string): string {
  const escaped = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  let pattern: string
  if (/[^aeiou]y$/i.test(query)) {
    const base = escaped.slice(0, -1)
    pattern = `(${escaped}(?:'s)?|${base}ies(?:'s)?)`
  } else {
    pattern = `(${escaped}(?:'?e?s)?)`
  }
  const regex = new RegExp(pattern, 'gi')
  return text.replace(regex, '<mark class="bg-yellow-200 dark:bg-yellow-800 px-0.5 rounded">$1</mark>')
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex gap-2">
      <UInput
        v-model="searchQuery"
        placeholder="Search for a term or phrase..."
        class="flex-1"
        size="lg"
        @keyup.enter="handleSearch"
      />
      <UButton
        :loading="loading"
        size="lg"
        @click="handleSearch"
      >
        Search
      </UButton>
    </div>

    <div class="flex items-center gap-4">
      <UCheckbox
        v-model="caseSensitive"
        label="Case sensitive"
      />
    </div>

    <!-- Frequency Results -->
    <div v-if="result" class="space-y-4">
      <UCard>
        <template #header>
          <div class="flex items-center justify-between">
            <h3 class="text-lg font-semibold">"{{ result.term }}"</h3>
            <div :class="['flex items-center gap-1', getTrendColor(result.trend)]">
              <UIcon :name="getTrendIcon(result.trend)" class="w-5 h-5" />
              <span class="text-sm capitalize">{{ result.trend }}</span>
            </div>
          </div>
        </template>

        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div class="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <div class="text-3xl font-bold text-primary">{{ result.total_mentions }}</div>
            <div class="text-sm text-gray-500">Total Mentions</div>
          </div>
          <div class="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <div class="text-3xl font-bold text-primary">{{ result.briefings_with_term }}</div>
            <div class="text-sm text-gray-500">Briefings With Term</div>
          </div>
          <div class="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <div class="text-3xl font-bold text-primary">{{ result.total_briefings }}</div>
            <div class="text-sm text-gray-500">Total Briefings</div>
          </div>
          <div class="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
            <div class="text-3xl font-bold" :class="result.percentage >= 90 ? 'text-green-500' : result.percentage >= 50 ? 'text-yellow-500' : 'text-red-500'">
              {{ result.percentage }}%
            </div>
            <div class="text-sm text-gray-500">Mention Rate</div>
          </div>
        </div>

        <template v-if="result.mentions_by_date.length > 0" #footer>
          <h4 class="font-medium mb-2">Recent Mentions</h4>
          <div class="max-h-48 overflow-y-auto space-y-1">
            <div
              v-for="mention in result.mentions_by_date.slice(0, 10)"
              :key="mention.date + mention.name"
              class="flex justify-between text-sm py-1 border-b border-gray-100 dark:border-gray-700"
            >
              <div class="flex items-center gap-2 min-w-0">
                <span class="text-gray-600 dark:text-gray-400 truncate">{{ mention.name }}</span>
                <span class="text-gray-400 dark:text-gray-500 text-xs shrink-0">{{ mention.date }}</span>
              </div>
              <span class="font-medium shrink-0 ml-2">{{ mention.count }} mentions</span>
            </div>
          </div>
        </template>
      </UCard>
    </div>

    <!-- Context Search Results -->
    <div v-if="searchResults" class="space-y-4">
      <div class="flex items-center justify-between">
        <h3 class="text-lg font-semibold">
          Found {{ searchResults.total_matches }} matches for "{{ searchResults.query }}"
        </h3>
      </div>

      <div class="space-y-2 max-h-[500px] overflow-y-auto">
        <UCard
          v-for="(match, index) in searchResults.matches"
          :key="index"
          class="text-sm"
        >
          <div class="flex items-center justify-between mb-2">
            <span class="font-medium text-primary">{{ match.transcript_name || 'Transcript' }}</span>
            <span class="text-gray-500 text-xs">{{ match.date }}</span>
          </div>
          <p
            class="text-gray-600 dark:text-gray-400"
            v-html="highlightMatch(match.context, searchResults.query)"
          />
        </UCard>
      </div>
    </div>

    <!-- Empty State -->
    <div
      v-if="!result && !searchResults && !loading"
      class="text-center py-12 text-gray-500"
    >
      <UIcon name="i-lucide-search" class="w-12 h-12 mx-auto mb-4 opacity-50" />
      <p>Enter a term to analyze its frequency in press briefings</p>
    </div>
  </div>
</template>
