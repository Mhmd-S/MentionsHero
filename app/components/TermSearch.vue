<script setup lang="ts">
import { useAnalysis, type TermFrequency } from '~/composables/useAnalysis'

const { getTermFrequency, searchTerm, loading } = useAnalysis()

const searchQuery = ref('')
const caseSensitive = ref(false)
const result = ref<TermFrequency | null>(null)
const searchResults = ref<{ query: string; total_matches: number; matches: any[] } | null>(null)
const activeTab = ref<'frequency' | 'context'>('frequency')

async function handleSearch() {
  if (!searchQuery.value.trim()) return

  if (activeTab.value === 'frequency') {
    result.value = await getTermFrequency(searchQuery.value, caseSensitive.value)
    searchResults.value = null
  } else {
    searchResults.value = await searchTerm(searchQuery.value)
    result.value = null
  }
}

function getTrendIcon(trend: string) {
  switch (trend) {
    case 'increasing': return 'i-heroicons-arrow-trending-up'
    case 'decreasing': return 'i-heroicons-arrow-trending-down'
    default: return 'i-heroicons-minus'
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
  const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi')
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
      <UTabs
        v-model="activeTab"
        :items="[
          { label: 'Frequency', value: 'frequency' },
          { label: 'Context', value: 'context' }
        ]"
        class="w-auto"
      />
      <UCheckbox
        v-if="activeTab === 'frequency'"
        v-model="caseSensitive"
        label="Case sensitive"
      />
    </div>

    <!-- Frequency Results -->
    <div v-if="result && activeTab === 'frequency'" class="space-y-4">
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
              <span class="text-gray-600 dark:text-gray-400">{{ mention.name || mention.date }}</span>
              <span class="font-medium">{{ mention.count }} mentions</span>
            </div>
          </div>
        </template>
      </UCard>
    </div>

    <!-- Context Search Results -->
    <div v-if="searchResults && activeTab === 'context'" class="space-y-4">
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
      <UIcon name="i-heroicons-magnifying-glass" class="w-12 h-12 mx-auto mb-4 opacity-50" />
      <p>Enter a term to analyze its frequency in press briefings</p>
    </div>
  </div>
</template>
