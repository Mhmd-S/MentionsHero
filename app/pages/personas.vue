<script setup lang="ts">
import { usePersonas, type Persona, type PersonaTranscript } from '~/composables/usePersonas'
import { useAnalysis, type SpeakerInfo } from '~/composables/useAnalysis'

const { personas, loading, fetchPersonas, createPersona, updatePersona, deletePersona, addAliases, removeAliases, getPersonaTranscripts } = usePersonas()
const { fetchFolders, getSpeakers } = useAnalysis()
const { folders: fileTreeFolders, fetchFolders: fetchFileTreeFolders } = useFileTree()

// Type for readonly persona from the composable
type ReadonlyPersona = {
  readonly id: string
  readonly name: string
  readonly description: string | null
  readonly aliases: readonly string[]
  readonly created_at: string | null
  readonly updated_at: string | null
}

// State
const selectedPersona = ref<ReadonlyPersona | null>(null)
const personaTranscripts = ref<PersonaTranscript[]>([])
const loadingTranscripts = ref(false)

// Modal state
const showCreateModal = ref(false)
const showEditModal = ref(false)
const showAddAliasModal = ref(false)
const newPersonaName = ref('')
const newPersonaDescription = ref('')
const newPersonaAliases = ref('')
const editingPersona = ref<ReadonlyPersona | null>(null)
const aliasToAdd = ref('')

// Speaker search state
const availableSpeakers = ref<SpeakerInfo[]>([])
const loadingAvailableSpeakers = ref(false)
const selectedSpeakersToAdd = ref<string[]>([])

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

// Load all speakers from database (single request)
async function loadAllSpeakers() {
  if (availableSpeakers.value.length > 0) return

  loadingAvailableSpeakers.value = true
  try {
    const speakers = await getSpeakers()
    availableSpeakers.value = speakers.sort((a, b) => b.briefings - a.briefings)
  } catch (e) {
    console.error('Failed to load speakers:', e)
  } finally {
    loadingAvailableSpeakers.value = false
  }
}

// Watch for add alias modal to load speakers
watch(showAddAliasModal, (isOpen) => {
  if (isOpen) {
    loadAllSpeakers()
    selectedSpeakersToAdd.value = []
    aliasToAdd.value = ''
  }
})

// Speaker options for select menu
const speakerOptions = computed(() => {
  const existingAliases = new Set(editingPersona.value?.aliases || [])
  return availableSpeakers.value.map(s => {
    const isAssigned = existingAliases.has(s.name)
    return {
      label: s.name,
      value: s.name,
      description: isAssigned ? 'Already assigned' : `${s.briefings} briefings`,
      disabled: isAssigned
    }
  })
})

// Load transcripts for selected persona
async function loadPersonaTranscripts(persona: ReadonlyPersona) {
  selectedPersona.value = persona
  loadingTranscripts.value = true
  try {
    personaTranscripts.value = await getPersonaTranscripts(persona.id)
  } catch (e) {
    console.error('Failed to load persona transcripts:', e)
    personaTranscripts.value = []
  } finally {
    loadingTranscripts.value = false
  }
}

// Create persona
async function handleCreatePersona() {
  if (!newPersonaName.value.trim()) return

  const aliases = newPersonaAliases.value
    .split(',')
    .map(a => a.trim())
    .filter(Boolean)

  await createPersona(
    newPersonaName.value.trim(),
    newPersonaDescription.value.trim() || undefined,
    aliases
  )

  showCreateModal.value = false
  newPersonaName.value = ''
  newPersonaDescription.value = ''
  newPersonaAliases.value = ''
}

// Update persona
async function handleUpdatePersona() {
  if (!editingPersona.value || !newPersonaName.value.trim()) return

  await updatePersona(
    editingPersona.value.id,
    newPersonaName.value.trim(),
    newPersonaDescription.value.trim() || undefined
  )

  showEditModal.value = false
  editingPersona.value = null
  newPersonaName.value = ''
  newPersonaDescription.value = ''
}

// Delete persona
async function handleDeletePersona(persona: ReadonlyPersona) {
  if (!confirm(`Delete persona "${persona.name}" and all its aliases?`)) return
  await deletePersona(persona.id)
  if (selectedPersona.value?.id === persona.id) {
    selectedPersona.value = null
    personaTranscripts.value = []
  }
}

// Open edit modal
function openEditModal(persona: ReadonlyPersona) {
  editingPersona.value = persona
  newPersonaName.value = persona.name
  newPersonaDescription.value = persona.description || ''
  showEditModal.value = true
}

// Open add alias modal
function openAddAliasModal(persona: ReadonlyPersona) {
  editingPersona.value = persona
  aliasToAdd.value = ''
  selectedSpeakersToAdd.value = []
  showAddAliasModal.value = true
}

// Add alias to persona
async function handleAddAlias() {
  if (!editingPersona.value) return

  const aliasesToAdd = new Set<string>()
  
  // Add selected speakers
  selectedSpeakersToAdd.value.forEach(s => aliasesToAdd.add(s))
  
  // Add custom alias if present
  if (aliasToAdd.value.trim()) {
    aliasesToAdd.add(aliasToAdd.value.trim())
  }

  if (aliasesToAdd.size === 0) return
  
  await addAliases(editingPersona.value.id, Array.from(aliasesToAdd))
  
  showAddAliasModal.value = false
  aliasToAdd.value = ''
  selectedSpeakersToAdd.value = []
  editingPersona.value = null
}

// Remove alias from persona
async function handleRemoveAlias(persona: ReadonlyPersona, alias: string) {
  await removeAliases(persona.id, [alias])
}

// Polymarket: load events for selected persona
async function loadPersonaEvents() {
  if (!selectedPersona.value) return
  loadingPersonaEvents.value = true
  try {
    personaEvents.value = await $fetch<PersonaEvent[]>(`/api/polymarket/events/${selectedPersona.value.id}`)
  } catch (e) {
    console.error('Failed to load persona events:', e)
    personaEvents.value = []
  } finally {
    loadingPersonaEvents.value = false
  }
}

watch(selectedPersona, (p) => {
  if (p) loadPersonaEvents()
  else personaEvents.value = []
})

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

async function handleAddEvent() {
  if (!selectedPersona.value) return
  const slug = extractSlugFromInput(newEventSlug.value)
  if (!slug) return
  addingEvent.value = true
  try {
    await $fetch('/api/polymarket/events', {
      method: 'POST',
      body: { persona_id: selectedPersona.value.id, slug }
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
  if (!selectedPersona.value) return
  refreshingEventId.value = eventId
  try {
    await $fetch(`/api/polymarket/events/${eventId}/refresh`, {
      method: 'POST',
      query: { persona_id: selectedPersona.value.id }
    })
    await loadPersonaEvents()
  } catch (e) {
    console.error('Failed to refresh event:', e)
  } finally {
    refreshingEventId.value = null
  }
}

// Initialize
onMounted(async () => {
  await Promise.all([
    fetchPersonas(),
    fetchFolders(),
    fetchFileTreeFolders()
  ])
})
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="mb-6">
      <div class="flex items-center justify-between">
        <div>
          <h1 class="text-3xl font-bold mb-2">Personas</h1>
          <p class="text-gray-600 dark:text-gray-400">
            Group speaker name variations into unified personas
          </p>
        </div>
        <UButton @click="showCreateModal = true" icon="i-heroicons-plus">
          New Persona
        </UButton>
      </div>
    </div>

    <!-- Main Content -->
    <div class="space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">Personas</h2>
        <UBadge v-if="personas.length > 0" color="neutral" variant="subtle">
          {{ personas.length }}
        </UBadge>
      </div>

      <div v-if="loading" class="flex items-center justify-center p-8">
        <UIcon name="i-heroicons-arrow-path" class="w-6 h-6 animate-spin" />
      </div>

      <div v-else-if="personas.length === 0" class="text-gray-500 text-sm p-4 border border-dashed rounded-lg">
        No personas created yet. Click "New Persona" to create one.
      </div>

      <div v-else class="space-y-3 max-h-96 overflow-y-auto">
        <div
          v-for="persona in personas"
          :key="persona.id"
          class="p-4 border rounded-lg hover:border-primary-500 transition-colors cursor-pointer"
          :class="{ 'border-primary-500 bg-primary-50 dark:bg-primary-900/20': selectedPersona?.id === persona.id }"
          @click="loadPersonaTranscripts(persona)"
        >
          <div class="flex items-start justify-between mb-2">
            <div>
              <div class="font-semibold">{{ persona.name }}</div>
              <div v-if="persona.description" class="text-sm text-gray-500 mt-1">
                {{ persona.description }}
              </div>
            </div>
            <div class="flex items-center gap-1">
              <UButton size="xs" variant="ghost" icon="i-heroicons-plus" @click.stop="openAddAliasModal(persona)" />
              <UButton size="xs" variant="ghost" icon="i-heroicons-pencil" @click.stop="openEditModal(persona)" />
              <UButton size="xs" variant="ghost" color="error" icon="i-heroicons-trash" @click.stop="handleDeletePersona(persona)" />
            </div>
          </div>

          <!-- Aliases -->
          <div v-if="persona.aliases.length > 0" class="flex flex-wrap gap-1">
            <UBadge
              v-for="alias in persona.aliases"
              :key="alias"
              color="neutral"
              variant="soft"
              size="sm"
              class="cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800"
              @click.stop="handleRemoveAlias(persona, alias)"
            >
              {{ alias }}
              <UIcon name="i-heroicons-x-mark" class="w-3 h-3 ml-1" />
            </UBadge>
          </div>
          <div v-else class="text-xs text-gray-400">
            No aliases - click + to add
          </div>
        </div>
      </div>
    </div>

    <!-- Tabs Panel -->
    <div v-if="selectedPersona" class="mt-6">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-base font-semibold">{{ selectedPersona.name }}</h2>
        <UButton size="xs" variant="ghost" icon="i-heroicons-x-mark" @click="selectedPersona = null; personaTranscripts = []" />
      </div>

      <UTabs :default-value="'events'" :items="[{ label: 'Polymarket Events', value: 'events' }, { label: 'Transcripts', value: 'transcripts' }]">
        <template #content="{ item }">
          <!-- Polymarket Events Tab -->
          <div v-if="item.value === 'events'" class="pt-3">
            <div class="flex justify-end mb-2">
              <UButton size="xs" icon="i-heroicons-plus" @click="showAddEventModal = true">Add Event</UButton>
            </div>

            <div v-if="loadingPersonaEvents" class="flex items-center justify-center p-6">
              <UIcon name="i-heroicons-arrow-path" class="w-5 h-5 animate-spin" />
            </div>

            <div v-else-if="personaEvents.length === 0" class="text-gray-500 text-sm p-3 border border-dashed rounded-lg">
              No events linked. Add by slug or URL.
            </div>

            <div v-else class="space-y-3">
              <div
                v-for="item in personaEvents"
                :key="item.event.id"
                class="border rounded-lg overflow-hidden"
              >
                <div class="flex items-center gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-800/50">
                  <img v-if="item.event.image" :src="item.event.image" :alt="item.event.title || ''" class="w-8 h-8 rounded object-cover" />
                  <div class="flex-1 min-w-0">
                    <div class="text-sm font-medium truncate">{{ item.event.title || item.event.slug }}</div>
                  </div>
                  <UButton size="xs" variant="ghost" icon="i-heroicons-arrow-path" :loading="refreshingEventId === item.event.id" @click="handleRefreshEvent(item.event.id)" />
                </div>
                <div>
                  <TermSection
                    v-for="m in item.markets"
                    :key="m.market.id"
                    :market-id="m.market.id"
                    :question="m.market.question"
                    :search-terms="m.search_config?.search_terms || []"
                    :result-count="m.result_count"
                    :result-last-updated="m.result_last_updated"
                    :outcome-price="m.market.outcome_prices?.[0] || null"
                    :persona-id="selectedPersona!.id"
                    :briefings-with-term="m.result_briefings_with_term"
                    :total-briefings="m.result_total_briefings"
                    :percentage="m.result_percentage"
                    :trend="m.result_trend"
                    :mentions-by-date="m.result_mentions_by_date"
                  />
                </div>
              </div>
            </div>
          </div>

          <!-- Transcripts Tab -->
          <div v-if="item.value === 'transcripts'" class="pt-3">
            <div v-if="loadingTranscripts" class="flex items-center justify-center p-6">
              <UIcon name="i-heroicons-arrow-path" class="w-5 h-5 animate-spin" />
            </div>

            <div v-else-if="personaTranscripts.length === 0" class="text-gray-500 text-sm p-3 border border-dashed rounded-lg">
              No transcripts found for this persona.
            </div>

            <UTable
              v-else
              :data="personaTranscripts"
              :columns="[
                { key: 'name', header: 'Name' },
                { key: 'created_at', header: 'Date' }
              ]"
              class="text-sm"
            >
              <template #name-cell="{ row }">
                <NuxtLink :to="`/transcripts/${row.original.id}`" class="text-primary-500 hover:underline truncate block max-w-xs">
                  {{ row.original.name || 'Untitled' }}
                </NuxtLink>
              </template>
              <template #created_at-cell="{ row }">
                <span class="text-gray-500 text-xs">{{ new Date(row.original.created_at).toLocaleDateString() }}</span>
              </template>
            </UTable>
          </div>
        </template>
      </UTabs>
    </div>

    <!-- Add Polymarket Event Modal -->
    <UModal v-model:open="showAddEventModal">
      <template #content>
        <div class="p-6">
          <h3 class="text-lg font-semibold mb-4">Add Polymarket Event</h3>
          <p class="text-sm text-gray-500 mb-4">
            Enter the event slug or full URL (e.g. polymarket.com/event/fed-decision-in-october).
          </p>
          <UFormField label="Event slug or URL">
            <UInput
              v-model="newEventSlug"
              placeholder="fed-decision-in-october or https://polymarket.com/event/..."
              class="w-full"
              @keyup.enter="handleAddEvent()"
            />
          </UFormField>
          <div class="flex justify-end gap-2 mt-6">
            <UButton variant="ghost" @click="showAddEventModal = false">Cancel</UButton>
            <UButton
              :loading="addingEvent"
              :disabled="!extractSlugFromInput(newEventSlug)"
              @click="handleAddEvent()"
            >
              Add Event
            </UButton>
          </div>
        </div>
      </template>
    </UModal>

    <!-- Create Persona Modal -->
    <UModal v-model:open="showCreateModal">
      <template #content>
        <div class="p-6">
          <h3 class="text-lg font-semibold mb-4">Create New Persona</h3>

          <div class="space-y-4">
            <UFormField label="Name" required>
              <UInput v-model="newPersonaName" placeholder="e.g., John Smith" class="w-full" />
            </UFormField>

            <UFormField label="Description">
              <UTextarea v-model="newPersonaDescription" placeholder="Optional description..." :rows="2" class="w-full" />
            </UFormField>

            <UFormField label="Aliases" description="Comma-separated list of name variations">
              <UInput v-model="newPersonaAliases" placeholder="e.g., J. Smith, John S., Mr. Smith" class="w-full" />
            </UFormField>
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <UButton variant="ghost" @click="showCreateModal = false">Cancel</UButton>
            <UButton @click="handleCreatePersona" :disabled="!newPersonaName.trim()">Create</UButton>
          </div>
        </div>
      </template>
    </UModal>

    <!-- Edit Persona Modal -->
    <UModal v-model:open="showEditModal">
      <template #content>
        <div class="p-6">
          <h3 class="text-lg font-semibold mb-4">Edit Persona</h3>

          <div class="space-y-4">
            <UFormField label="Name" required>
              <UInput v-model="newPersonaName" placeholder="e.g., John Smith" class="w-full" />
            </UFormField>

            <UFormField label="Description">
              <UTextarea v-model="newPersonaDescription" placeholder="Optional description..." :rows="2" class="w-full" />
            </UFormField>
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <UButton variant="ghost" @click="showEditModal = false">Cancel</UButton>
            <UButton @click="handleUpdatePersona" :disabled="!newPersonaName.trim()">Save</UButton>
          </div>
        </div>
      </template>
    </UModal>

    <!-- Add Alias Modal -->
    <UModal v-model:open="showAddAliasModal">
      <template #content>
        <div class="p-6">
          <h3 class="text-lg font-semibold mb-4">Add Aliases to {{ editingPersona?.name }}</h3>

          <div class="space-y-4">
            <!-- Speaker Search -->
            <UFormField label="Search Speakers" description="Select speakers from your transcripts">
              <USelectMenu
                v-model="selectedSpeakersToAdd"
                :items="speakerOptions"
                :loading="loadingAvailableSpeakers"
                placeholder="Search and select speakers..."
                multiple
                searchable
                class="w-full"
                value-key="value"
                label-key="label"
                :reset-search-term-on-select="false"
              />
            </UFormField>

            <!-- Selected speakers preview -->
            <div v-if="selectedSpeakersToAdd.length > 0" class="flex flex-wrap gap-1">
              <UBadge
                v-for="speaker in selectedSpeakersToAdd"
                :key="speaker"
                color="primary"
                variant="subtle"
                size="sm"
                class="cursor-pointer"
                @click="selectedSpeakersToAdd = selectedSpeakersToAdd.filter(s => s !== speaker)"
              >
                {{ speaker }}
                <UIcon name="i-heroicons-x-mark" class="w-3 h-3 ml-1" />
              </UBadge>
            </div>

            <!-- Custom alias input -->
            <UFormField label="Or type a custom alias">
              <UInput 
                v-model="aliasToAdd" 
                placeholder="Type a custom alias..." 
                class="w-full" 
                @keyup.enter="handleAddAlias()" 
                autocomplete="off"
              />
            </UFormField>
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <UButton variant="ghost" @click="showAddAliasModal = false">Cancel</UButton>
            <UButton 
              @click="handleAddAlias()" 
              :disabled="selectedSpeakersToAdd.length === 0 && !aliasToAdd.trim()"
            >
              Add {{ selectedSpeakersToAdd.length + (aliasToAdd.trim() ? 1 : 0) }} Alias{{ (selectedSpeakersToAdd.length + (aliasToAdd.trim() ? 1 : 0)) !== 1 ? 'es' : '' }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
