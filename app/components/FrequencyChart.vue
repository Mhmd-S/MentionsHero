<script setup lang="ts">
import { useAnalysis } from '~/composables/useAnalysis'

const { getTemporalTrends, loading } = useAnalysis()

const terms = ref<string[]>(['president', 'american'])
const newTerm = ref('')
const trends = ref<Record<string, Array<{ date: string | null; count: number; transcript_name: string }>>>({})

const colors = [
  'bg-blue-500',
  'bg-green-500',
  'bg-purple-500',
  'bg-orange-500',
  'bg-pink-500'
]

async function loadTrends() {
  if (terms.value.length === 0) return
  trends.value = await getTemporalTrends(terms.value)
}

function addTerm() {
  const term = newTerm.value.trim().toLowerCase()
  if (term && !terms.value.includes(term) && terms.value.length < 5) {
    terms.value.push(term)
    newTerm.value = ''
    loadTrends()
  }
}

function removeTerm(term: string) {
  terms.value = terms.value.filter(t => t !== term)
  delete trends.value[term]
}

// Get max count for scaling
const maxCount = computed(() => {
  let max = 0
  for (const term of Object.keys(trends.value)) {
    for (const point of trends.value[term]) {
      if (point.count > max) max = point.count
    }
  }
  return max || 1
})

// Get unique dates across all terms
const dates = computed(() => {
  const allDates = new Set<string>()
  for (const term of Object.keys(trends.value)) {
    for (const point of trends.value[term]) {
      if (point.date) allDates.add(point.date)
    }
  }
  return Array.from(allDates).sort()
})

// Get data point for a term on a specific date
function getDataPoint(term: string, date: string) {
  const points = trends.value[term] || []
  return points.find(p => p.date === date)?.count || 0
}

onMounted(() => {
  loadTrends()
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <h2 class="text-xl font-semibold">Term Trends Over Time</h2>
      <UButton
        variant="outline"
        size="sm"
        :loading="loading"
        @click="loadTrends"
      >
        Refresh
      </UButton>
    </div>

    <!-- Term input -->
    <div class="flex gap-2 flex-wrap">
      <div class="flex gap-2">
        <UInput
          v-model="newTerm"
          placeholder="Add a term to track..."
          size="sm"
          @keyup.enter="addTerm"
        />
        <UButton size="sm" @click="addTerm" :disabled="terms.length >= 5">
          Add
        </UButton>
      </div>

      <div class="flex gap-2 flex-wrap">
        <UBadge
          v-for="(term, index) in terms"
          :key="term"
          :class="colors[index % colors.length]"
          class="cursor-pointer"
          @click="removeTerm(term)"
        >
          {{ term }}
          <UIcon name="i-heroicons-x-mark" class="w-3 h-3 ml-1" />
        </UBadge>
      </div>
    </div>

    <!-- Chart -->
    <div v-if="loading" class="text-center py-8">
      <UIcon name="i-heroicons-arrow-path" class="w-8 h-8 animate-spin mx-auto text-gray-400" />
    </div>

    <div v-else-if="dates.length === 0" class="text-center py-8 text-gray-500">
      <p>No trend data available</p>
    </div>

    <div v-else class="space-y-4">
      <!-- Simple bar chart representation -->
      <div class="overflow-x-auto">
        <div class="min-w-[600px]">
          <!-- Legend -->
          <div class="flex gap-4 mb-4">
            <div
              v-for="(term, index) in terms"
              :key="term"
              class="flex items-center gap-2"
            >
              <div :class="['w-3 h-3 rounded', colors[index % colors.length]]" />
              <span class="text-sm">{{ term }}</span>
            </div>
          </div>

          <!-- Chart area -->
          <div class="relative h-64 border-l border-b border-gray-300 dark:border-gray-600">
            <!-- Y-axis labels -->
            <div class="absolute -left-8 top-0 h-full flex flex-col justify-between text-xs text-gray-500">
              <span>{{ maxCount }}</span>
              <span>{{ Math.round(maxCount / 2) }}</span>
              <span>0</span>
            </div>

            <!-- Bars -->
            <div class="flex h-full items-end gap-1 px-2">
              <div
                v-for="date in dates.slice(-20)"
                :key="date"
                class="flex-1 flex items-end gap-0.5 min-w-[20px]"
              >
                <div
                  v-for="(term, index) in terms"
                  :key="term"
                  :class="['flex-1 rounded-t transition-all', colors[index % colors.length]]"
                  :style="{ height: `${(getDataPoint(term, date) / maxCount) * 100}%`, minHeight: getDataPoint(term, date) > 0 ? '4px' : '0' }"
                  :title="`${term}: ${getDataPoint(term, date)} on ${date}`"
                />
              </div>
            </div>

            <!-- X-axis labels -->
            <div class="flex gap-1 px-2 mt-2">
              <div
                v-for="date in dates.slice(-20)"
                :key="date"
                class="flex-1 text-xs text-gray-500 text-center truncate"
                :title="date"
              >
                {{ date.slice(5) }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Summary stats -->
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
        <UCard v-for="(term, index) in terms" :key="term" class="text-center">
          <div class="flex items-center justify-center gap-2 mb-2">
            <div :class="['w-3 h-3 rounded', colors[index % colors.length]]" />
            <span class="font-medium">{{ term }}</span>
          </div>
          <div class="text-2xl font-bold">
            {{ trends[term]?.reduce((sum, p) => sum + p.count, 0) || 0 }}
          </div>
          <div class="text-sm text-gray-500">total mentions</div>
        </UCard>
      </div>
    </div>
  </div>
</template>
