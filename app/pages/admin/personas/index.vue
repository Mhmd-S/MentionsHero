<script lang="ts">
definePageMeta({ layout: 'admin' })
</script>

<script setup lang="ts">
import { usePersonas, type Persona } from '~/composables/usePersonas'

const NuxtLink = resolveComponent('NuxtLink')
const { personas, loading, fetchPersonas, createPersona, updatePersona, deletePersona, addAliases, removeAliases } = usePersonas()
const { fetchFolders, getSpeakers } = useAnalysis()
const { folders: fileTreeFolders, fetchFolders: fetchFileTreeFolders } = useFileTree()

// Type for readonly persona from the composable
type ReadonlyPersona = {
  readonly id: string
  readonly name: string
  readonly slug: string | null
  readonly description: string | null
  readonly meta_title: string | null
  readonly meta_description: string | null
  readonly aliases: readonly string[]
  readonly created_at: string | null
  readonly updated_at: string | null
}

// Selection / mass edit state
const selectMode = ref(false)
const selectedIds = ref<Set<string>>(new Set())
const bulkDeleting = ref(false)

const allSelected = computed(() =>
  personas.value.length > 0 && selectedIds.value.size === personas.value.length
)

function toggleSelect(id: string) {
  const next = new Set(selectedIds.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selectedIds.value = next
}

function toggleSelectAll() {
  if (allSelected.value) {
    selectedIds.value = new Set()
  } else {
    selectedIds.value = new Set(personas.value.map(p => p.id))
  }
}

function exitSelectMode() {
  selectMode.value = false
  selectedIds.value = new Set()
}

async function bulkDelete() {
  const count = selectedIds.value.size
  if (!count) return
  if (!confirm(`Delete ${count} persona${count !== 1 ? 's' : ''} and all their aliases?`)) return

  bulkDeleting.value = true
  try {
    for (const id of selectedIds.value) {
      await deletePersona(id)
    }
    selectedIds.value = new Set()
    selectMode.value = false
  } finally {
    bulkDeleting.value = false
  }
}

function bulkAddAliases() {
  // Open add alias modal targeting all selected personas
  editingPersona.value = null
  bulkTargetIds.value = [...selectedIds.value]
  aliasToAdd.value = ''
  selectedSpeakersToAdd.value = []
  showAddAliasModal.value = true
}

// Modal state
const showCreateModal = ref(false)
const showEditModal = ref(false)
const showAddAliasModal = ref(false)
const bulkTargetIds = ref<string[]>([])
const newPersonaName = ref('')
const newPersonaDescription = ref('')
const newPersonaAliases = ref('')
const newSlug = ref('')
const newMetaTitle = ref('')
const newMetaDescription = ref('')
const editingPersona = ref<ReadonlyPersona | null>(null)
const aliasToAdd = ref('')

// Speaker search state
const availableSpeakers = ref<import('~/composables/useAnalysis').SpeakerInfo[]>([])
const loadingAvailableSpeakers = ref(false)
const selectedSpeakersToAdd = ref<string[]>([])
const selectedFolderForSpeakers = ref<string | null>(null)

// Build hierarchical folder options for select menu
const folderOptions = computed(() => {
  const buildTree = (parentId: string | null, depth = 0): { label: string; value: string }[] => {
    const children = fileTreeFolders.value.filter(f => f.parent_id === parentId)
    const result: { label: string; value: string }[] = []
    for (const folder of children) {
      const indent = '\u00A0\u00A0'.repeat(depth)
      result.push({ label: `${indent}${folder.name}`, value: folder.id })
      result.push(...buildTree(folder.id, depth + 1))
    }
    return result
  }
  return buildTree(null)
})

// Load speakers for selected folder (recursive)
async function loadSpeakersForFolder(folderId: string) {
  loadingAvailableSpeakers.value = true
  availableSpeakers.value = []
  try {
    const speakers = await getSpeakers(folderId)
    availableSpeakers.value = speakers.sort((a, b) => b.briefings - a.briefings)
  } catch (e) {
    console.error('Failed to load speakers:', e)
  } finally {
    loadingAvailableSpeakers.value = false
  }
}

// Watch for folder selection to load speakers
watch(selectedFolderForSpeakers, (folderId) => {
  if (folderId) {
    loadSpeakersForFolder(folderId)
    selectedSpeakersToAdd.value = []
  } else {
    availableSpeakers.value = []
    selectedSpeakersToAdd.value = []
  }
})

// Watch for add alias modal to reset state
watch(showAddAliasModal, (isOpen) => {
  if (isOpen) {
    selectedFolderForSpeakers.value = null
    availableSpeakers.value = []
    selectedSpeakersToAdd.value = []
    aliasToAdd.value = ''
  }
})

// Speaker options for select menu
const speakerOptions = computed(() => {
  // Collect aliases from all targeted personas (single or bulk)
  const existingAliases = new Set<string>()
  if (bulkTargetIds.value.length > 0) {
    for (const id of bulkTargetIds.value) {
      const p = personas.value.find(p => p.id === id)
      p?.aliases.forEach(a => existingAliases.add(a))
    }
  } else if (editingPersona.value) {
    editingPersona.value.aliases.forEach(a => existingAliases.add(a))
  }
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
    aliases,
    newMetaTitle.value.trim() || undefined,
    newMetaDescription.value.trim() || undefined,
  )

  showCreateModal.value = false
  newPersonaName.value = ''
  newPersonaDescription.value = ''
  newPersonaAliases.value = ''
  newMetaTitle.value = ''
  newMetaDescription.value = ''
}

// Update persona
async function handleUpdatePersona() {
  if (!editingPersona.value || !newPersonaName.value.trim()) return

  await updatePersona(
    editingPersona.value.id,
    newPersonaName.value.trim(),
    newPersonaDescription.value.trim() || undefined,
    newMetaTitle.value.trim() || undefined,
    newMetaDescription.value.trim() || undefined,
    newSlug.value.trim() || undefined,
  )

  showEditModal.value = false
  editingPersona.value = null
  newPersonaName.value = ''
  newPersonaDescription.value = ''
  newSlug.value = ''
  newMetaTitle.value = ''
  newMetaDescription.value = ''
}

// Delete persona
async function handleDeletePersona(persona: ReadonlyPersona) {
  if (!confirm(`Delete persona "${persona.name}" and all its aliases?`)) return
  await deletePersona(persona.id)
}

// Open edit modal
function openEditModal(persona: ReadonlyPersona) {
  editingPersona.value = persona
  newPersonaName.value = persona.name
  newPersonaDescription.value = persona.description || ''
  newSlug.value = persona.slug || ''
  newMetaTitle.value = persona.meta_title || ''
  newMetaDescription.value = persona.meta_description || ''
  showEditModal.value = true
}

// Open add alias modal
function openAddAliasModal(persona: ReadonlyPersona) {
  editingPersona.value = persona
  bulkTargetIds.value = []
  aliasToAdd.value = ''
  selectedSpeakersToAdd.value = []
  showAddAliasModal.value = true
}

// Add alias to persona(s) — supports single and bulk
async function handleAddAlias() {
  const aliasesToAdd = new Set<string>()

  // Add selected speakers
  selectedSpeakersToAdd.value.forEach(s => aliasesToAdd.add(s))

  // Add custom alias if present
  if (aliasToAdd.value.trim()) {
    aliasesToAdd.add(aliasToAdd.value.trim())
  }

  if (aliasesToAdd.size === 0) return

  const aliasList = Array.from(aliasesToAdd)

  // Bulk mode: add aliases to all selected personas
  if (bulkTargetIds.value.length > 0) {
    for (const id of bulkTargetIds.value) {
      await addAliases(id, aliasList)
    }
  } else if (editingPersona.value) {
    await addAliases(editingPersona.value.id, aliasList)
  }

  showAddAliasModal.value = false
  aliasToAdd.value = ''
  selectedSpeakersToAdd.value = []
  editingPersona.value = null
  bulkTargetIds.value = []
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
  <div class="p-4 sm:p-6 max-w-7xl w-full mx-auto">
    <!-- Header -->
    <div class="mb-6">
      <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 class="text-2xl sm:text-3xl font-bold mb-2">Personas</h1>
          <p class="text-gray-600 dark:text-gray-400">
            Group speaker name variations into unified personas
          </p>
        </div>
        <div class="flex items-center gap-2">
          <UButton
            v-if="personas.length > 0"
            :variant="selectMode ? 'solid' : 'outline'"
            :color="selectMode ? 'neutral' : undefined"
            size="sm"
            icon="i-lucide-check-circle"
            @click="selectMode ? exitSelectMode() : (selectMode = true)"
          >
            {{ selectMode ? 'Cancel' : 'Select' }}
          </UButton>
          <UButton @click="showCreateModal = true" icon="i-lucide-plus">
            New Persona
          </UButton>
        </div>
      </div>
    </div>

    <!-- Bulk action bar -->
    <div
      v-if="selectMode && selectedIds.size > 0"
      class="mb-4 flex flex-wrap items-center gap-3 p-3 bg-primary-50 dark:bg-primary-950/30 border border-primary-200 dark:border-primary-800 rounded-lg"
    >
      <span class="text-sm font-medium">{{ selectedIds.size }} selected</span>
      <UButton size="xs" variant="outline" @click="toggleSelectAll">
        {{ allSelected ? 'Deselect all' : 'Select all' }}
      </UButton>
      <div class="ml-auto flex items-center gap-2">
        <UButton size="xs" variant="outline" icon="i-lucide-plus" @click="bulkAddAliases">
          Add Aliases
        </UButton>
        <UButton size="xs" variant="outline" color="error" icon="i-lucide-trash-2" :loading="bulkDeleting" @click="bulkDelete">
          Delete
        </UButton>
      </div>
    </div>

    <!-- Main Content -->
    <div class="space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-xl font-semibold">Personas</h2>
        <UBadge v-if="personas.length > 0" color="neutral" variant="subtle">
          {{ personas.length }}
        </UBadge>
      </div>

      <div v-if="loading" class="flex items-center justify-center p-8">
        <UIcon name="i-lucide-loader" class="w-6 h-6 animate-spin" />
      </div>

      <div v-else-if="personas.length === 0" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        No personas created yet. Click "New Persona" to create one.
      </div>

      <div v-else class="space-y-3">
        <component
          :is="selectMode ? 'div' : NuxtLink"
          v-for="persona in personas"
          :key="persona.id"
          :to="selectMode ? undefined : `/admin/personas/${persona.id}`"
          class="block p-4 border rounded-lg transition-colors cursor-pointer"
          :class="[
            selectMode && selectedIds.has(persona.id)
              ? 'border-primary-500 bg-primary-50/50 dark:bg-primary-950/20'
              : 'hover:border-primary-500'
          ]"
          @click="selectMode ? toggleSelect(persona.id) : undefined"
        >
          <div class="flex items-start justify-between mb-2">
            <div class="flex items-start gap-3">
              <UCheckbox
                v-if="selectMode"
                :model-value="selectedIds.has(persona.id)"
                @click.stop
                @update:model-value="toggleSelect(persona.id)"
                class="mt-0.5"
              />
              <div>
                <div class="font-semibold">{{ persona.name }}</div>
                <div v-if="persona.description" class="text-base text-gray-500 mt-1">
                  {{ persona.description }}
                </div>
              </div>
            </div>
            <div v-if="!selectMode" class="flex items-center gap-1">
              <UButton size="xs" variant="ghost" icon="i-lucide-plus" @click.prevent="openAddAliasModal(persona)" />
              <UButton size="xs" variant="ghost" icon="i-lucide-pencil" @click.prevent="openEditModal(persona)" />
              <UButton size="xs" variant="ghost" color="error" icon="i-lucide-trash-2" @click.prevent="handleDeletePersona(persona)" />
            </div>
          </div>

          <!-- Aliases -->
          <div v-if="persona.aliases.length > 0" class="flex flex-wrap gap-1" :class="selectMode ? 'ml-8' : ''">
            <UBadge
              v-for="alias in persona.aliases"
              :key="alias"
              color="neutral"
              variant="soft"
              size="sm"
              :class="selectMode ? '' : 'cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-800'"
              @click.prevent="selectMode ? undefined : handleRemoveAlias(persona, alias)"
            >
              {{ alias }}
              <UIcon v-if="!selectMode" name="i-lucide-x" class="w-3 h-3 ml-1" />
            </UBadge>
          </div>
          <div v-else class="text-sm text-gray-400" :class="selectMode ? 'ml-8' : ''">
            No aliases - click + to add
          </div>
        </component>
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

            <details class="border border-gray-200 dark:border-gray-700 rounded-lg">
              <summary class="px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 cursor-pointer">SEO Settings</summary>
              <div class="px-3 pb-3 space-y-3">
                <UFormField label="Meta Title" description="Custom page title for search engines">
                  <UInput v-model="newMetaTitle" placeholder="Defaults to persona name" class="w-full" />
                </UFormField>
                <UFormField label="Meta Description" description="Page description for search results">
                  <UTextarea v-model="newMetaDescription" placeholder="Defaults to persona description" :rows="2" class="w-full" />
                </UFormField>
              </div>
            </details>
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

            <UFormField label="Slug" description="URL-friendly identifier (e.g., john-smith)">
              <UInput v-model="newSlug" placeholder="e.g., john-smith" class="w-full" />
            </UFormField>

            <UFormField label="Description">
              <UTextarea v-model="newPersonaDescription" placeholder="Optional description..." :rows="2" class="w-full" />
            </UFormField>

            <details class="border border-gray-200 dark:border-gray-700 rounded-lg">
              <summary class="px-3 py-2 text-sm font-medium text-gray-600 dark:text-gray-400 cursor-pointer">SEO Settings</summary>
              <div class="px-3 pb-3 space-y-3">
                <UFormField label="Meta Title" description="Custom page title for search engines">
                  <UInput v-model="newMetaTitle" placeholder="Defaults to persona name" class="w-full" />
                </UFormField>
                <UFormField label="Meta Description" description="Page description for search results">
                  <UTextarea v-model="newMetaDescription" placeholder="Defaults to persona description" :rows="2" class="w-full" />
                </UFormField>
              </div>
            </details>
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
          <h3 class="text-lg font-semibold mb-4">
            {{ bulkTargetIds.length > 0
              ? `Add Aliases to ${bulkTargetIds.length} Persona${bulkTargetIds.length !== 1 ? 's' : ''}`
              : `Add Aliases to ${editingPersona?.name}` }}
          </h3>

          <div class="space-y-4">
            <!-- Folder Selection -->
            <UFormField label="Select Folder" description="Choose a folder to load speakers from">
              <USelectMenu
                v-model="selectedFolderForSpeakers"
                :items="folderOptions"
                placeholder="Select a folder..."
                searchable
                class="w-full"
                value-key="value"
                label-key="label"
              />
            </UFormField>

            <!-- Speaker Search (only shown after folder is selected) -->
            <template v-if="selectedFolderForSpeakers">
              <UFormField label="Search Speakers" description="Select speakers from the selected folder">
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
                  <UIcon name="i-lucide-x" class="w-3 h-3 ml-1" />
                </UBadge>
              </div>

              <!-- No speakers message -->
              <div v-else-if="!loadingAvailableSpeakers && availableSpeakers.length === 0" class="text-base text-gray-500 p-2 border border-dashed rounded">
                No speakers found in this folder.
              </div>
            </template>

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
