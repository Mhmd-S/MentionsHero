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

    <!-- Transcripts Panel -->
    <div v-if="selectedPersona" class="mt-8">
      <div class="flex items-center justify-between mb-4">
        <h2 class="text-lg font-semibold">
          Transcripts containing "{{ selectedPersona.name }}"
        </h2>
        <UButton size="xs" variant="ghost" @click="selectedPersona = null; personaTranscripts = []">
          Close
        </UButton>
      </div>

      <div v-if="loadingTranscripts" class="flex items-center justify-center p-8">
        <UIcon name="i-heroicons-arrow-path" class="w-6 h-6 animate-spin" />
      </div>

      <div v-else-if="personaTranscripts.length === 0" class="text-gray-500 text-sm p-4 border border-dashed rounded-lg">
        No transcripts found containing this persona's aliases
      </div>

      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        <NuxtLink
          v-for="transcript in personaTranscripts"
          :key="transcript.id"
          :to="`/transcripts/${transcript.id}`"
          class="p-3 border rounded-lg hover:border-primary-500 transition-colors"
        >
          <div class="font-medium truncate">{{ transcript.name || 'Untitled' }}</div>
          <div class="text-xs text-gray-500 mt-1">
            {{ new Date(transcript.created_at).toLocaleDateString() }}
          </div>
        </NuxtLink>
      </div>
    </div>

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
