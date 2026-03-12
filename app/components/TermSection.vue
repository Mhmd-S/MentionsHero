<script setup lang="ts">
export interface TermResult {
  search_term: string
  total_mentions: number
  briefings_with_term: number
  total_briefings: number
  percentage: number
  trend: string
  mentions_by_date: { date: string | null; name: string; count: number }[]
  context_matches: { transcript_id: string; transcript_name: string; date: string | null; context: string; position: number }[]
  context_total_matches: number
  context_transcripts_with_matches: number
  last_updated?: string | null
}

interface Props {
  marketId: string
  question: string | null
  searchTerm: string
  termResult: TermResult | null
  lastPrice: number | null
  personaId: string
  result?: string | null
  closeTime?: string | null
}

const props = defineProps<Props>()

const yesPrice = computed(() => {
  if (props.lastPrice == null) return null
  return (props.lastPrice).toFixed(0)
})
const totalMentions = computed(() => props.termResult?.total_mentions ?? null)
const briefings = computed(() => props.termResult?.briefings_with_term ?? null)
const hasData = computed(() => totalMentions.value !== null || (props.termResult?.context_matches?.length ?? 0) > 0)

const displayCap = 8
const showAll = ref(false)
const expandedTranscripts = ref(new Set<string>())

const groupedByTranscript = computed(() => {
  const matches = props.termResult?.context_matches
  if (!matches?.length) return []
  const groups = new Map<string, {
    transcript_id: string
    transcript_name: string
    date: string | null
    snippets: string[]
  }>()
  const seen = new Set<string>()
  for (const match of matches) {
    const key = `${match.transcript_id}::${match.context}`
    if (seen.has(key)) continue
    seen.add(key)
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
  return Array.from(groups.values()).sort((a, b) => {
    if (!a.date && !b.date) return 0
    if (!a.date) return 1
    if (!b.date) return -1
    return b.date.localeCompare(a.date)
  })
})

const displayedTranscripts = computed(() => {
  if (showAll.value) return groupedByTranscript.value
  return groupedByTranscript.value.slice(0, displayCap)
})

const hasMore = computed(() => groupedByTranscript.value.length > displayCap)

const summaryLine = computed(() => {
  const total = props.termResult?.context_total_matches ?? props.termResult?.total_mentions ?? 0
  const transcriptCount = props.termResult?.context_transcripts_with_matches ?? props.termResult?.briefings_with_term ?? 0
  return `${total} mention${total !== 1 ? 's' : ''} across ${transcriptCount} transcript${transcriptCount !== 1 ? 's' : ''}`
})

function buildPluralPattern(term: string): string {
  const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  // Words ending in consonant + y: match "ies" plural (e.g., policy → policies)
  if (/[^aeiou]y$/i.test(term)) {
    const base = escaped.slice(0, -1)
    return `\\b(${escaped}(?:'s)?|${base}ies(?:'s)?)\\b`
  }
  // Default: match optional plural 's'/'es' and possessive "'s"
  return `\\b(${escaped}(?:'?e?s)?)\\b`
}

function highlightTerm(text: string): string {
  if (!props.searchTerm) return text
  const regex = new RegExp(buildPluralPattern(props.searchTerm), 'gi')
  return text.replace(regex, '<mark class="bg-yellow-200 dark:bg-yellow-800 px-0.5 rounded">$1</mark>')
}
</script>

<template>
  <div class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-800/50">
      <span class="text-sm font-medium truncate flex-1">{{ question || '—' }}</span>
      <div class="flex items-center gap-2 shrink-0">
        <UBadge v-if="result" :color="result === 'yes' ? 'success' : 'error'" variant="subtle" size="xs">
          {{ result.toUpperCase() }}
        </UBadge>
        <UBadge v-if="searchTerm" color="primary" variant="subtle" size="xs">
          "{{ searchTerm }}"
        </UBadge>
        <span v-if="yesPrice && !result" class="text-sm font-semibold text-primary">
          {{ yesPrice }}%
        </span>
      </div>
    </div>

    <!-- Details -->
    <div class="px-3 py-2">
      <!-- Has Data -->
      <div v-if="hasData || groupedByTranscript.length" class="space-y-2">
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
                  :name="expandedTranscripts.has(group.transcript_id) ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
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
