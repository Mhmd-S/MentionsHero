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

function onSpeakerChange(value: string[] | string | null) {
  const normalized = Array.isArray(value) ? value : value ? [value] : []
  selectedSpeakers.value = normalized.length > 0 ? normalized : null
  if (selectedFolderId.value) {
    loadTopTerms()
  }
}

onMounted(async () => {
  await fetchFolders()
})

const tabs = [
  { label: 'Term Search', value: 'search', icon: 'i-heroicons-magnifying-glass' },
  { label: 'Markets', value: 'markets', icon: 'i-heroicons-chart-bar' }
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
      <MarketAnalysis v-else-if="activeTab === 'markets'" />
    </div>
  </div>
</template>
