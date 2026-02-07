<script setup lang="ts">
import { usePersonas } from '~/composables/usePersonas'

const route = useRoute()
const personaId = route.params.id as string

const { getPersona } = usePersonas()

// Persona state
const persona = ref<Awaited<ReturnType<typeof getPersona>>>(null)
const loadingPersona = ref(true)

// Polymarket state
interface PersonaEventMarket {
  market: { id: string; question: string | null; outcome_prices: string[] | null; closed?: boolean }
  search_config: { search_terms: string[]; min_count: number } | null
  result_count: number | null
  result_last_updated: string | null
  result_briefings_with_term: number | null
  result_total_briefings: number | null
  result_percentage: number | null
  result_trend: string | null
  result_mentions_by_date: { date: string | null; name: string; count: number }[] | null
}
interface PersonaEvent {
  event: { id: string; slug: string; title: string | null; image: string | null }
  markets: PersonaEventMarket[]
}
const personaEvents = ref<PersonaEvent[]>([])
const loadingPersonaEvents = ref(false)
const showAddEventModal = ref(false)
const newEventSlug = ref('')
const addingEvent = ref(false)
const refreshingEventId = ref<string | null>(null)

function extractSlugFromInput(input: string): string {
  const trimmed = input.trim()
  if (!trimmed) return ''
  try {
    const url = new URL(trimmed)
    const path = url.pathname
    const match = path.match(/\/event\/([^/]+)/) || path.match(/\/market\/([^/]+)/)
    if (match && match[1]) return match[1]
  } catch {
    // not a URL
  }
  return trimmed
}

async function loadPersonaEvents() {
  loadingPersonaEvents.value = true
  try {
    personaEvents.value = await $fetch<PersonaEvent[]>(`/api/polymarket/events/${personaId}`)
  } catch (e) {
    console.error('Failed to load persona events:', e)
    personaEvents.value = []
  } finally {
    loadingPersonaEvents.value = false
  }
}

async function handleAddEvent() {
  const slug = extractSlugFromInput(newEventSlug.value)
  if (!slug) return
  addingEvent.value = true
  try {
    await $fetch('/api/polymarket/events', {
      method: 'POST',
      body: { persona_id: personaId, slug }
    })
    showAddEventModal.value = false
    newEventSlug.value = ''
    await loadPersonaEvents()
  } catch (e: any) {
    console.error('Failed to add event:', e)
    alert(e?.data?.detail || 'Failed to add event')
  } finally {
    addingEvent.value = false
  }
}

async function handleRefreshEvent(eventId: string) {
  refreshingEventId.value = eventId
  try {
    await $fetch(`/api/polymarket/events/${eventId}/refresh`, {
      method: 'POST',
      query: { persona_id: personaId }
    })
    await loadPersonaEvents()
  } catch (e) {
    console.error('Failed to refresh event:', e)
  } finally {
    refreshingEventId.value = null
  }
}

// Load everything on mount
onMounted(async () => {
  loadingPersona.value = true
  try {
    persona.value = await getPersona(personaId)
  } catch (e) {
    console.error('Failed to load persona:', e)
  } finally {
    loadingPersona.value = false
  }

  await loadPersonaEvents()
})
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto">
    <!-- Header with back button -->
    <div class="mb-6">
      <NuxtLink to="/personas"
        class="inline-flex items-center gap-1 text-gray-500 hover:text-gray-900 dark:hover:text-gray-100 transition-colors mb-4">
        <UIcon name="i-heroicons-chevron-left" class="w-5 h-5" />
        <span class="text-base">Personas</span>
      </NuxtLink>

      <div v-if="loadingPersona" class="flex items-center justify-center p-8">
        <UIcon name="i-heroicons-arrow-path" class="w-6 h-6 animate-spin" />
      </div>

      <div v-else-if="!persona" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        Persona not found.
      </div>

      <template v-else>
        <h1 class="text-3xl font-bold mb-1">{{ persona.name }}</h1>
        <p v-if="persona.description" class="text-gray-500 text-base">{{ persona.description }}</p>

        <!-- Aliases -->
        <div v-if="persona.aliases.length > 0" class="flex flex-wrap gap-1.5 mt-3">
          <UBadge v-for="alias in persona.aliases" :key="alias" color="neutral" variant="soft">
            {{ alias }}
          </UBadge>
        </div>
      </template>
    </div>

    <!-- Polymarket Events -->
    <template v-if="persona">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-xl font-semibold">Polymarket Events</h2>
        <UButton size="sm" icon="i-heroicons-plus" @click="showAddEventModal = true">Add Event</UButton>
      </div>

      <div v-if="loadingPersonaEvents" class="flex items-center justify-center p-8">
        <UIcon name="i-heroicons-arrow-path" class="w-6 h-6 animate-spin" />
      </div>

      <div v-else-if="personaEvents.length === 0" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        No events linked. Add by slug or URL.
      </div>

      <div v-else class="space-y-4">
        <div v-for="pe in personaEvents" :key="pe.event.id" class="overflow-hidden flex flex-col gap-4">

          <div class="flex items-center gap-3 px-4 py-3 bg-gray-50 dark:bg-gray-800/50">
            <img v-if="pe.event.image" :src="pe.event.image" :alt="pe.event.title || ''"
              class="w-10 h-10 rounded object-cover" />
            <div class="flex-1 min-w-0">
              <div class="text-base font-medium truncate">{{ pe.event.title || pe.event.slug }}</div>
            </div>
            <UButton size="xs" variant="ghost" icon="i-heroicons-arrow-path"
              :loading="refreshingEventId === pe.event.id" @click="handleRefreshEvent(pe.event.id)" />
          </div>


          <template v-for="m in pe.markets" :key="m.market.id">
            <TermSection
              v-for="term in (m.search_config?.search_terms || []).length ? (m.search_config?.search_terms || []) : ['']"
              :key="`${m.market.id}-${term}`" :market-id="m.market.id" :question="m.market.question" :search-term="term"
              :result-count="m.result_count" :result-last-updated="m.result_last_updated"
              :outcome-price="m.market.outcome_prices?.[0] || null" :persona-id="personaId" />
          </template>

        </div>
      </div>
    </template>

    <!-- Add Polymarket Event Modal -->
    <UModal v-model:open="showAddEventModal">
      <template #content>
        <div class="p-6">
          <h3 class="text-lg font-semibold mb-4">Add Polymarket Event</h3>
          <p class="text-base text-gray-500 mb-4">
            Enter the event slug or full URL (e.g. polymarket.com/event/fed-decision-in-october).
          </p>
          <UFormField label="Event slug or URL">
            <UInput v-model="newEventSlug" placeholder="fed-decision-in-october or https://polymarket.com/event/..."
              class="w-full" @keyup.enter="handleAddEvent()" />
          </UFormField>
          <div class="flex justify-end gap-2 mt-6">
            <UButton variant="ghost" @click="showAddEventModal = false">Cancel</UButton>
            <UButton :loading="addingEvent" :disabled="!extractSlugFromInput(newEventSlug)" @click="handleAddEvent()">
              Add Event
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
