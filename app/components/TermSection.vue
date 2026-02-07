<script setup lang="ts">
interface Props {
  marketId: string
  question: string | null
  searchTerm: string
  resultCount: number | null
  resultLastUpdated: string | null
  outcomePrice: string | null
  personaId: string
}

const props = defineProps<Props>()

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

// Context state
const loadingContext = ref(false)
const contextData = ref<{
  query: string
  total_matches: number
  transcripts_with_matches: number
  matches: { transcript_id: string; transcript_name: string; date: string | null; context: string; position: number }[]
} | null>(null)

// Use cached data if available, otherwise use fetched data
const totalMentions = computed(() => props.resultCount ?? fetchedData.value?.total_mentions ?? null)
const briefings = computed(() => fetchedData.value?.briefings_with_term ?? null)

const hasData = computed(() => totalMentions.value !== null)
const needsFetch = computed(() =>
  props.searchTerm && !fetchedData.value
)

// Display cap
const displayCap = 8
const showAll = ref(false)
const expandedTranscripts = ref(new Set<string>())

// Group context matches by transcript
const groupedByTranscript = computed(() => {
  if (!contextData.value?.matches?.length) return []
  const groups = new Map<string, {
    transcript_id: string
    transcript_name: string
    date: string | null
    snippets: string[]
  }>()
  for (const match of contextData.value.matches) {
    const existing = groups.get(match.transcript_id)
    if (existing) {
      existing.snippets.push(match.context)
    } else {
      groups.set(match.transcript_id, {
        transcript_id: match.transcript_id,
        transcript_name: match.transcript_name,
        date: match.date,
        snippets: [match.context]
      })
    }
  }
  return Array.from(groups.values())
})

const displayedTranscripts = computed(() => {
  if (showAll.value) return groupedByTranscript.value
  return groupedByTranscript.value.slice(0, displayCap)
})

const hasMore = computed(() => groupedByTranscript.value.length > displayCap)

// Summary line
const summaryLine = computed(() => {
  const total = contextData.value?.total_matches ?? totalMentions.value ?? 0
  const transcriptCount = contextData.value?.transcripts_with_matches ?? briefings.value ?? 0
  return `${total} mention${total !== 1 ? 's' : ''} across ${transcriptCount} transcript${transcriptCount !== 1 ? 's' : ''}`
})

async function fetchTermData() {
  if (!props.searchTerm || fetchedData.value) return

  loading.value = true
  try {
    const data = await $fetch(`/api/analysis/term/${encodeURIComponent(props.searchTerm)}`, {
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
  if (!props.searchTerm || contextData.value) return

  loadingContext.value = true
  try {
    const data = await $fetch('/api/analysis/search', {
      method: 'POST',
      body: {
        query: props.searchTerm,
        context_chars: 300,
        speakers: null
      }
    })
    contextData.value = data as typeof contextData.value
  } catch (e) {
    console.error('Failed to fetch context:', e)
  } finally {
    loadingContext.value = false
  }
}

function highlightTerm(text: string): string {
  if (!props.searchTerm) return text
  const regex = new RegExp(`\\b(${props.searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})\\b`, 'gi')
  return text.replace(regex, '<mark class="bg-yellow-200 dark:bg-yellow-800 px-0.5 rounded">$1</mark>')
}

// Fetch data and context on mount
onMounted(() => {
  if (needsFetch.value) {
    fetchTermData()
  }
  fetchContext()
})
</script>

<template>
  <div class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-800/50">
      <span class="text-sm font-medium truncate flex-1">{{ question || '—' }}</span>
      <div class="flex items-center gap-2 shrink-0">
        <UBadge v-if="searchTerm" color="primary" variant="subtle" size="xs">
          "{{ searchTerm }}"
        </UBadge>
        <span v-if="yesPrice" class="text-sm font-semibold text-primary">
          {{ yesPrice }}%
        </span>
      </div>
    </div>

    <!-- Details -->
    <div class="px-3 py-2">
      <!-- Loading -->
      <div v-if="loading || loadingContext" class="flex items-center justify-center py-3">
        <UIcon name="i-heroicons-arrow-path" class="w-4 h-4 animate-spin" />
      </div>

      <!-- Has Data -->
      <div v-else-if="hasData || contextData" class="space-y-2">
        <!-- Summary Line -->
        <div class="text-xs text-gray-500">
          {{ summaryLine }}
        </div>

        <!-- Transcript List -->
        <div v-if="groupedByTranscript.length" class="space-y-0.5">
          <div
            v-for="group in displayedTranscripts"
            :key="group.transcript_id"
            class="text-xs"
          >
            <!-- Transcript row (clickable to expand) -->
            <div
              class="flex items-center justify-between py-1 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded px-1 -mx-1"
              @click="expandedTranscripts.has(group.transcript_id) ? expandedTranscripts.delete(group.transcript_id) : expandedTranscripts.add(group.transcript_id)"
            >
              <div class="flex items-center gap-1 truncate">
                <UIcon
                  :name="expandedTranscripts.has(group.transcript_id) ? 'i-heroicons-chevron-down' : 'i-heroicons-chevron-right'"
                  class="w-3 h-3 shrink-0 text-gray-400"
                />
                <span class="font-medium truncate">{{ group.transcript_name }}</span>
              </div>
              <div class="flex items-center gap-2 shrink-0 text-gray-400">
                <span v-if="group.date">{{ group.date }}</span>
                <span class="font-medium">{{ group.snippets.length }}x</span>
              </div>
            </div>
            <!-- Expanded context snippets -->
            <div v-if="expandedTranscripts.has(group.transcript_id)" class="space-y-1 pl-4 pb-2 border-l-2 border-gray-200 dark:border-gray-700 ml-1.5 mt-0.5">
              <p
                v-for="(snippet, idx) in group.snippets"
                :key="idx"
                class="text-gray-600 dark:text-gray-400 leading-relaxed"
                v-html="highlightTerm(snippet)"
              />
            </div>
          </div>

          <!-- Show All / Show Less -->
          <div v-if="hasMore" class="pt-1">
            <UButton size="xs" variant="ghost" @click="showAll = !showAll">
              {{ showAll ? 'Show less' : `Show all ${groupedByTranscript.length} transcripts` }}
            </UButton>
          </div>
        </div>
      </div>

      <!-- No search term -->
      <div v-else-if="!searchTerm" class="text-xs text-gray-500 py-1">
        No search term found in question.
      </div>

      <!-- No data yet -->
      <div v-else class="text-xs text-gray-500 py-1">
        Click refresh to analyze.
      </div>
    </div>
  </div>
</template>
