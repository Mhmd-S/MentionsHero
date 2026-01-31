<script setup lang="ts">
import { useAnalysis, type AnalysisFolder } from '~/composables/useAnalysis'

const { getAllTerms, fetchFolders, getSpeakers, folders, selectedFolderId, selectedSpeakers, loading } = useAnalysis()

const activeTab = ref('search')
const topTerms = ref<Array<{ term: string; count: number; percentage: number }>>([])

const FOLDER_ALL = '__all__' as const

const folderOptions = computed(() => [
  { label: 'All Transcripts', value: FOLDER_ALL },
  ...folders.value.map((f: AnalysisFolder) => ({ label: f.name, value: f.id }))
])

async function loadTopTerms() {
  const terms = await getAllTerms(10, 20)
  topTerms.value = terms.map(t => ({
    term: t.term,
    count: t.count,
    percentage: t.percentage
  }))
}

function onFolderChange(value: unknown) {
  const raw = value != null ? String(value) : ''
  const id = raw === FOLDER_ALL || raw === '' ? null : raw
  selectedFolderId.value = id
  if (id) {
    getSpeakers(id)
    loadTopTerms()
  } else {
    selectedSpeakers.value = null
    topTerms.value = []
  }
}

function onSpeakerChange(value: string | null) {
  selectedSpeakers.value = value || null
  if (selectedFolderId.value) {
    loadTopTerms()
  }
}

onMounted(async () => {
  await fetchFolders()
})

const tabs = [
  { label: 'Term Search', value: 'search', icon: 'i-heroicons-magnifying-glass' },
  { label: 'High Confidence', value: 'confidence', icon: 'i-heroicons-check-badge' },
  { label: 'Markets', value: 'markets', icon: 'i-heroicons-chart-bar' },
  { label: 'Trends', value: 'trends', icon: 'i-heroicons-arrow-trending-up' },
  { label: 'Entities', value: 'entities', icon: 'i-heroicons-user-group' }
]
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="mb-8">
      <div class="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 class="text-3xl font-bold mb-2">Polymarket Analysis Dashboard</h1>
          <p class="text-gray-600 dark:text-gray-400">
            Analyze press briefing transcripts to inform betting on Polymarket "mentions markets"
          </p>
        </div>
        <div class="flex items-center gap-4 flex-wrap">
          <div class="flex items-center gap-2">
            <label class="text-sm text-gray-500">Analyze folder:</label>
            <USelect
              :model-value="selectedFolderId ?? FOLDER_ALL"
              :items="folderOptions"
              class="w-48"
              value-key="value"
              @update:model-value="onFolderChange"
            />
          </div>
          <SpeakerSelector
            :model-value="selectedSpeakers"
            :folder-id="selectedFolderId"
            placeholder="All speakers"
            @update:model-value="onSpeakerChange"
          />
        </div>
      </div>
    </div>

    <!-- Quick Stats -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      <UCard class="text-center">
        <div class="text-3xl font-bold text-primary">
          {{ topTerms.length > 0 ? topTerms.reduce((sum, t) => sum + t.count, 0).toLocaleString() : '-' }}
        </div>
        <div class="text-sm text-gray-500">Total Words Analyzed</div>
      </UCard>
      <UCard class="text-center">
        <div class="text-3xl font-bold text-blue-600">Live</div>
        <div class="text-sm text-gray-500">Market Data</div>
      </UCard>
    </div>

    <!-- Top Terms Quick View -->
    <UCard v-if="topTerms.length > 0" class="mb-8">
      <template #header>
        <div class="flex items-center justify-between">
          <h3 class="font-semibold">Most Frequent Terms</h3>
          <UButton variant="ghost" size="xs" :loading="loading" @click="loadTopTerms">
            Refresh
          </UButton>
        </div>
      </template>
      <div class="flex flex-wrap gap-2">
        <UBadge
          v-for="term in topTerms"
          :key="term.term"
          size="lg"
          color="neutral"
        >
          {{ term.term }} ({{ term.percentage.toFixed(0) }}%)
        </UBadge>
      </div>
    </UCard>

    <!-- Tab Navigation -->
    <div class="mb-6">
      <div class="flex gap-2 overflow-x-auto pb-2">
        <UButton
          v-for="tab in tabs"
          :key="tab.value"
          :variant="activeTab === tab.value ? 'solid' : 'ghost'"
          :color="activeTab === tab.value ? 'primary' : 'neutral'"
          @click="activeTab = tab.value"
        >
          <UIcon :name="tab.icon" class="w-4 h-4 mr-2" />
          {{ tab.label }}
        </UButton>
      </div>
    </div>

    <!-- Tab Content -->
    <div class="min-h-[400px]">
      <TermSearch v-if="activeTab === 'search'" />
      <HighConfidenceTerms v-else-if="activeTab === 'confidence'" />
      <MarketAnalysis v-else-if="activeTab === 'markets'" />
      <FrequencyChart v-else-if="activeTab === 'trends'" />
      <EntityList v-else-if="activeTab === 'entities'" />
    </div>

    <!-- Help Section -->
    <UCard class="mt-8">
      <template #header>
        <h3 class="font-semibold flex items-center gap-2">
          <UIcon name="i-heroicons-question-mark-circle" class="w-5 h-5" />
          How to Use This Dashboard
        </h3>
      </template>

      <div class="grid md:grid-cols-2 gap-6 text-sm">
        <div>
          <h4 class="font-medium mb-2">For Betting Strategy:</h4>
          <ol class="list-decimal list-inside space-y-1 text-gray-600 dark:text-gray-400">
            <li>Check <strong>High Confidence</strong> tab for safe bets (90%+ mention rate)</li>
            <li>Use <strong>Term Search</strong> to verify specific market terms</li>
            <li>Compare historical percentage to market prices in <strong>Markets</strong> tab</li>
            <li>Track <strong>Trends</strong> to see if term usage is increasing or decreasing</li>
          </ol>
        </div>
        <div>
          <h4 class="font-medium mb-2">Understanding the Analysis:</h4>
          <ul class="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400">
            <li><strong>Percentage</strong>: % of briefings containing the term</li>
            <li><strong>Trend</strong>: Whether usage is increasing, decreasing, or stable</li>
            <li><strong>Expected Value</strong>: Positive EV means favorable bet</li>
            <li><strong>Confidence</strong>: How certain the recommendation is</li>
          </ul>
        </div>
      </div>
    </UCard>
  </div>
</template>
