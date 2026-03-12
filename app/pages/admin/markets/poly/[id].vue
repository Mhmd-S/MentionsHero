<script lang="ts">
definePageMeta({ layout: 'admin' })
</script>

<script setup lang="ts">
import { usePolymarket, type PolyEventDetail } from '~/composables/usePolymarket'
import { usePersonas } from '~/composables/usePersonas'

const route = useRoute()
const eventId = route.params.id as string

const { getEventDetail, refreshEvent } = usePolymarket()
const { personas, fetchPersonas } = usePersonas()

const detail = ref<PolyEventDetail | null>(null)
const loading = ref(true)
const refreshing = ref(false)

// Persona selection
const selectedPersonaId = ref<string | undefined>(undefined)

const personaOptions = computed(() =>
  personas.value.map(p => ({ label: p.name, value: p.id }))
)

async function loadDetail() {
  loading.value = true
  try {
    detail.value = await getEventDetail(eventId, selectedPersonaId.value || undefined)
  } finally {
    loading.value = false
  }
}

async function reloadWithPersona() {
  loading.value = true
  try {
    detail.value = await getEventDetail(eventId, selectedPersonaId.value || undefined)
  } finally {
    loading.value = false
  }
}

async function handleRefresh() {
  refreshing.value = true
  try {
    await refreshEvent(eventId)
    await reloadWithPersona()
  } finally {
    refreshing.value = false
  }
}

watch(selectedPersonaId, () => {
  if (detail.value) reloadWithPersona()
})

onMounted(async () => {
  await fetchPersonas()
  await loadDetail()
})
</script>

<template>
  <div class="max-w-7xl">
    <!-- Back button -->
    <NuxtLink to="/admin/markets?tab=polymarket"
      class="inline-flex items-center gap-1 text-gray-500 hover:text-gray-900 dark:hover:text-gray-100 transition-colors mb-4">
      <UIcon name="i-lucide-chevron-left" class="w-5 h-5" />
      <span class="text-base">Markets</span>
    </NuxtLink>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center p-8">
      <UIcon name="i-lucide-loader" class="w-6 h-6 animate-spin" />
    </div>

    <div v-else-if="!detail" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
      Event not found.
    </div>

    <template v-else>
      <!-- Event header -->
      <div class="flex items-start gap-4 mb-6">
        <img
          v-if="detail.event.image"
          :src="detail.event.image"
          class="w-12 h-12 rounded object-cover shrink-0"
          alt=""
        />
        <div class="flex-1 min-w-0">
          <h1 class="text-2xl sm:text-3xl font-bold truncate mb-1">{{ detail.event.title || detail.event.slug }}</h1>
          <div class="flex items-center gap-3 text-sm text-gray-500">
            <UBadge color="info" variant="soft" size="xs">Polymarket</UBadge>
            <span v-if="detail.event.end_date">Ends {{ new Date(detail.event.end_date).toLocaleDateString() }}</span>
          </div>
        </div>
        <UButton
          size="xs"
          variant="ghost"
          icon="i-lucide-refresh-cw"
          :loading="refreshing"
          @click="handleRefresh"
        />
      </div>

      <!-- Persona selector -->
      <div class="flex flex-wrap items-center gap-3 mb-4">
        <span class="text-sm font-medium text-gray-600 dark:text-gray-400">Persona:</span>
        <USelectMenu
          v-model="selectedPersonaId"
          :items="personaOptions"
          value-key="value"
          placeholder="Select persona for analysis"
          class="w-64"
        />
        <UButton
          v-if="selectedPersonaId"
          size="xs"
          variant="ghost"
          icon="i-lucide-x"
          @click="selectedPersonaId = undefined"
        />
      </div>

      <!-- Markets -->
      <div v-if="!detail.markets?.length" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        No markets for this event.
      </div>

      <div v-else class="space-y-3">
        <template v-for="m in detail.markets" :key="m.market?.id || m.id">
          <!-- With persona analysis -->
          <template v-if="m.term_results">
            <TermSection
              v-for="term in (m.search_config?.search_terms || []).length ? (m.search_config?.search_terms || []) : ['']"
              :key="`${m.market.id}-${term}`"
              :market-id="m.market.id"
              :question="m.market.question"
              :search-term="term"
              :term-result="m.term_results?.find((tr: any) => tr.search_term === term) || null"
              :last-price="m.market.last_trade_price != null ? m.market.last_trade_price * 100 : null"
              :persona-id="selectedPersonaId || ''"
              :result="m.market.result"
              :close-time="m.market.closed_time"
            />
          </template>
          <!-- Without persona analysis -->
          <div v-else class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <div class="flex items-center justify-between gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-800/50">
              <span class="text-sm font-medium truncate flex-1">{{ m.question || '—' }}</span>
              <div class="flex items-center gap-2 shrink-0">
                <UBadge v-if="m.result" :color="m.result === 'yes' ? 'success' : 'error'" variant="subtle" size="xs">
                  {{ m.result.toUpperCase() }}
                </UBadge>
                <span v-if="m.last_trade_price != null && !m.result" class="text-sm font-semibold text-primary">
                  {{ (m.last_trade_price * 100).toFixed(0) }}%
                </span>
              </div>
            </div>
            <div class="px-3 py-2 text-xs text-gray-500">
              Select a persona to see analysis.
            </div>
          </div>
        </template>
      </div>
    </template>
  </div>
</template>
