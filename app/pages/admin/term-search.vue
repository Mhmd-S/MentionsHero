<script lang="ts">
definePageMeta({ layout: 'admin' })
</script>

<script setup lang="ts">
import { useAnalysis, type AnalysisFolder } from '~/composables/useAnalysis'
import { usePersonas, type Persona } from '~/composables/usePersonas'

const { getAllTerms, fetchFolders, getSpeakers, folders, selectedFolderId, selectedSpeakers } = useAnalysis()
const { personas, fetchPersonas, getAliasesForPersona } = usePersonas()

const selectedPersonaId = ref<string | null>(null)

const topTerms = ref<Array<{ term: string; count: number; percentage: number }>>([])

const FOLDER_ALL = '__all__' as const

const folderOptions = computed(() => [
  { label: 'All Transcripts', value: FOLDER_ALL },
  ...folders.value.map((f: AnalysisFolder) => ({ label: f.name, value: f.id }))
])

const PERSONA_NONE = '__none__' as const

const personaOptions = computed(() => [
  { label: 'No persona filter', value: PERSONA_NONE },
  ...personas.value.map((p: Persona) => ({
    label: `${p.name} (${p.aliases.length} aliases)`,
    value: p.id
  }))
])

function onPersonaChange(value: unknown) {
  const raw = value != null ? String(value) : ''
  const id = raw === PERSONA_NONE || raw === '' ? null : raw
  selectedPersonaId.value = id

  if (id) {
    // Auto-fill speakers with persona aliases
    const aliases = getAliasesForPersona(id)
    selectedSpeakers.value = aliases.length > 0 ? aliases : null
    if (selectedFolderId.value) {
      loadTopTerms()
    }
  } else {
    // Clear speaker selection when persona is deselected
    selectedSpeakers.value = null
  }
}

async function loadTopTerms() {
  const terms = await getAllTerms(10, 20)
  topTerms.value = terms.map(t => ({
    term: t.term,
    count: t.count,
    percentage: t.percentage
  }))
}

function onFolderChange(value: unknown) {
  const raw = value != null ? String(value) : ''
  const id = raw === FOLDER_ALL || raw === '' ? null : raw
  selectedFolderId.value = id
  if (id) {
    getSpeakers(id)
    loadTopTerms()
  } else {
    selectedSpeakers.value = null
    topTerms.value = []
  }
}

function onSpeakerChange(value: string[] | string | null) {
  const normalized = Array.isArray(value) ? value : value ? [value] : []
  selectedSpeakers.value = normalized.length > 0 ? normalized : null
  // Clear persona selection when speakers are manually changed
  selectedPersonaId.value = null
  if (selectedFolderId.value) {
    loadTopTerms()
  }
}

onMounted(async () => {
  await Promise.all([fetchFolders(), fetchPersonas()])
})
</script>

<template>
  <div class="p-6 max-w-7xl mx-auto">
    <!-- Header -->
    <div class="mb-8">
      <div class="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 class="text-3xl font-bold mb-2">Term Search</h1>
          <p class="text-gray-600 dark:text-gray-400">
            Search and analyze terms across press briefing transcripts
          </p>
        </div>
        <div class="flex items-center gap-4 flex-wrap">
          <div class="flex items-center gap-2">
            <label class="text-sm text-gray-500">Analyze folder:</label>
            <USelect
              :model-value="selectedFolderId ?? FOLDER_ALL"
              :items="folderOptions"
              class="w-48"
              value-key="value"
              @update:model-value="onFolderChange"
            />
          </div>
          <div class="flex items-center gap-2">
            <label class="text-sm text-gray-500">Persona:</label>
            <USelect
              :model-value="selectedPersonaId ?? PERSONA_NONE"
              :items="personaOptions"
              class="w-48"
              value-key="value"
              @update:model-value="onPersonaChange"
            />
          </div>
          <SpeakerSelector
            :model-value="selectedSpeakers"
            :folder-id="selectedFolderId"
            placeholder="All speakers"
            @update:model-value="onSpeakerChange"
          />
        </div>
      </div>
    </div>

    <!-- Content -->
    <TermSearch />
  </div>
</template>
