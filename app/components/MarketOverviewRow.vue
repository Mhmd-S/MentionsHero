<script setup lang="ts">
import type { TermResult } from '~/components/TermSection.vue'
import { useHighlight } from '~/composables/useHighlight'

interface Props {
  marketId: string
  question: string | null
  searchTerm: string
  termResult: TermResult | null
  personaId: string
  result?: string | null
  closeTime?: string | null
}

const props = defineProps<Props>()

const { highlightTerm } = useHighlight()

const expanded = ref(false)

// --- Metrics ---
const totalMentions = computed(() => props.termResult?.total_mentions ?? 0)
const percentage = computed(() => props.termResult?.percentage ?? 0)
// Average and median mentions per transcript (from mentions_by_date counts)
const mentionCounts = computed(() => {
  const entries = props.termResult?.mentions_by_date ?? []
  return entries.filter(e => e.count > 0).map(e => e.count)
})

const avgMentions = computed(() => {
  const counts = mentionCounts.value
  if (!counts.length) return 0
  return counts.reduce((sum, c) => sum + c, 0) / counts.length
})

const medianMentions = computed(() => {
  const counts = [...mentionCounts.value].sort((a, b) => a - b)
  if (!counts.length) return 0
  const mid = Math.floor(counts.length / 2)
  return counts.length % 2 === 0 ? (counts[mid - 1] + counts[mid]) / 2 : counts[mid]
})

// Trend: compare first half vs second half averages (mirrors backend logic)
const trendData = computed(() => {
  const entries = props.termResult?.mentions_by_date ?? []
  if (entries.length < 4) return { pctChange: null, absChange: null, direction: 'stable' as const }

  const mid = Math.floor(entries.length / 2)
  const firstHalfAvg = entries.slice(0, mid).reduce((s, e) => s + e.count, 0) / mid
  const secondHalfAvg = entries.slice(mid).reduce((s, e) => s + e.count, 0) / (entries.length - mid)

  const absChange = secondHalfAvg - firstHalfAvg
  const pctChange = firstHalfAvg > 0 ? ((secondHalfAvg - firstHalfAvg) / firstHalfAvg) * 100 : (secondHalfAvg > 0 ? 100 : 0)

  let direction: 'increasing' | 'decreasing' | 'stable' = 'stable'
  if (secondHalfAvg > firstHalfAvg * 1.2) direction = 'increasing'
  else if (secondHalfAvg < firstHalfAvg * 0.8) direction = 'decreasing'

  return { pctChange, absChange, direction }
})

function trendIcon(d: string) {
  if (d === 'increasing') return 'i-lucide-trending-up'
  if (d === 'decreasing') return 'i-lucide-trending-down'
  return 'i-lucide-minus'
}

function trendColor(d: string) {
  if (d === 'increasing') return 'text-green-500'
  if (d === 'decreasing') return 'text-red-500'
  return 'text-gray-400'
}

// --- Transcript context (same logic as TermSection) ---
const displayCap = 3
const showAll = ref(false)
const expandedTranscripts = ref(new Set<string>())

const groupedByTranscript = computed(() => {
  const matches = props.termResult?.context_matches
  if (!matches?.length) return []

  const countByName = new Map<string, number>()
  for (const entry of props.termResult?.mentions_by_date ?? []) {
    if (entry.name) countByName.set(entry.name, entry.count)
  }

  const groups = new Map<string, {
    transcript_id: string
    transcript_name: string
    date: string | null
    snippets: string[]
    mentionCount: number
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
        snippets: [match.context],
        mentionCount: countByName.get(match.transcript_name) ?? match.mention_count ?? 1,
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
</script>

<template>
  <div class="border-b border-gray-100 dark:border-gray-800">
    <!-- Collapsed row -->
    <div
      class="grid grid-cols-[1fr_80px_180px_70px_60px_60px_60px] gap-2 items-center px-3 py-2.5 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/40 transition-colors"
      @click="expanded = !expanded"
    >
      <!-- Term -->
      <div class="flex items-center gap-2 min-w-0">
        <UIcon
          :name="expanded ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
          class="w-4 h-4 shrink-0 text-gray-400"
        />
        <span class="font-medium text-sm truncate">{{ searchTerm || '—' }}</span>
      </div>

      <!-- % Briefings (likelihood) -->
      <div class="text-right text-sm font-semibold tabular-nums">
        {{ percentage.toFixed(0) }}%
      </div>

      <!-- Trend -->
      <div class="flex items-center gap-1.5" :class="trendColor(trendData.direction)">
        <UIcon :name="trendIcon(trendData.direction)" class="w-4 h-4 shrink-0" />
        <div v-if="trendData.pctChange != null" class="text-xs leading-tight">
          <span class="font-medium">{{ trendData.pctChange >= 0 ? '+' : '' }}{{ trendData.pctChange.toFixed(0) }}%</span>
          <span class="text-gray-400 ml-1">({{ trendData.absChange != null && trendData.absChange >= 0 ? '+' : '' }}{{ trendData.absChange?.toFixed(1) }}/br)</span>
        </div>
        <span v-else class="text-xs">—</span>
      </div>

      <!-- Mentions -->
      <div class="text-right text-sm tabular-nums">
        {{ totalMentions }}
      </div>

      <!-- Avg -->
      <div class="text-right text-sm tabular-nums text-gray-500">
        {{ avgMentions > 0 ? avgMentions.toFixed(1) : '—' }}
      </div>

      <!-- Median -->
      <div class="text-right text-sm tabular-nums text-gray-500">
        {{ medianMentions > 0 ? medianMentions.toFixed(1) : '—' }}
      </div>

      <!-- Result -->
      <div class="text-right">
        <UBadge v-if="result" :color="result === 'yes' ? 'success' : 'error'" variant="subtle" size="xs">
          {{ result.toUpperCase() }}
        </UBadge>
      </div>
    </div>

    <!-- Expanded panel -->
    <div v-if="expanded" class="px-3 pb-3 pr-16 pt-0 dark:border-gray-700">
      <!-- Transcript list -->
      <div v-if="groupedByTranscript.length" class="space-y-0.5">
        <div
          v-for="group in displayedTranscripts"
          :key="group.transcript_id"
          class="text-xs"
        >
          <div
            class="flex items-center justify-between py-1 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-800/50 rounded px-1 -mx-1"
            @click.stop="expandedTranscripts.has(group.transcript_id) ? expandedTranscripts.delete(group.transcript_id) : expandedTranscripts.add(group.transcript_id)"
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
              <span class="font-medium">{{ group.mentionCount }}x</span>
            </div>
          </div>
          <!-- Context snippets -->
          <div v-if="expandedTranscripts.has(group.transcript_id)" class="space-y-1 pl-4 pb-2 border-l-2 border-gray-200 dark:border-gray-700 ml-1.5 mt-0.5">
            <p
              v-for="(snippet, idx) in group.snippets"
              :key="idx"
              class="text-gray-600 dark:text-gray-400 leading-relaxed"
              v-html="highlightTerm(snippet, searchTerm)"
            />
          </div>
        </div>

        <div v-if="hasMore" class="pt-1">
          <UButton size="xs" variant="ghost" @click.stop="showAll = !showAll">
            {{ showAll ? 'Show less' : `Show all ${groupedByTranscript.length} transcripts` }}
          </UButton>
        </div>
      </div>

      <!-- No data -->
      <div v-else-if="!searchTerm" class="text-xs text-gray-500 py-1">
        No search term found in question.
      </div>
      <div v-else-if="totalMentions === 0" class="text-xs text-gray-500 py-1">
        No mentions found.
      </div>
    </div>
  </div>
</template>
