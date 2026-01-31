<script setup lang="ts">
import { useAnalysis, type NgramData } from '~/composables/useAnalysis'

const { getHighConfidencePhrases, loading } = useAnalysis()

const phrases = ref<NgramData[]>([])
const minPercentage = ref(90)

async function loadPhrases() {
  phrases.value = await getHighConfidencePhrases(minPercentage.value)
}

onMounted(() => {
  loadPhrases()
})

watch(minPercentage, () => {
  loadPhrases()
})
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <div>
        <h2 class="text-xl font-semibold">High-Confidence Phrases</h2>
        <p class="text-sm text-gray-500">Phrases mentioned in {{ minPercentage }}%+ of briefings</p>
      </div>
      <div class="flex items-center gap-4">
        <div class="flex items-center gap-2">
          <label class="text-sm text-gray-500">Min %:</label>
          <UInput
            v-model.number="minPercentage"
            type="number"
            :min="50"
            :max="100"
            class="w-20"
            size="sm"
          />
        </div>
        <UButton
          variant="outline"
          size="sm"
          :loading="loading"
          @click="loadPhrases"
        >
          Refresh
        </UButton>
      </div>
    </div>

    <div v-if="loading" class="text-center py-8">
      <UIcon name="i-heroicons-arrow-path" class="w-8 h-8 animate-spin mx-auto text-gray-400" />
    </div>

    <div v-else-if="phrases.length === 0" class="text-center py-8 text-gray-500">
      <UIcon name="i-heroicons-document-magnifying-glass" class="w-12 h-12 mx-auto mb-4 opacity-50" />
      <p>No phrases found above {{ minPercentage }}% threshold</p>
      <p class="text-sm mt-2">Try lowering the minimum percentage</p>
    </div>

    <div v-else class="space-y-2">
      <UAlert
        color="success"
        icon="i-heroicons-light-bulb"
        title="Low-Risk Bet Candidates"
        description="These phrases appear so frequently that betting YES on their mention is statistically favorable."
        class="mb-4"
      />

      <div class="grid gap-2">
        <UCard
          v-for="phrase in phrases"
          :key="phrase.phrase"
          class="hover:shadow-md transition-shadow"
        >
          <div class="flex items-center justify-between">
            <div>
              <span class="font-medium text-lg">"{{ phrase.phrase }}"</span>
              <div class="text-sm text-gray-500 mt-1">
                Appeared {{ phrase.count }} times across {{ phrase.briefings_with_phrase }} of {{ phrase.total_briefings }} briefings
              </div>
            </div>
            <div class="text-right">
              <div class="text-2xl font-bold text-green-600">
                {{ phrase.percentage.toFixed(1) }}%
              </div>
              <div class="text-xs text-gray-500">mention rate</div>
            </div>
          </div>
        </UCard>
      </div>
    </div>
  </div>
</template>
