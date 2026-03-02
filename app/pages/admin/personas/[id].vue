<script lang="ts">
definePageMeta({ layout: 'admin' })
</script>

<script setup lang="ts">
import { usePersonas } from '~/composables/usePersonas'
import { useKalshi, type KalshiSeries } from '~/composables/useKalshi'
import { useFileTree } from '~/composables/useFileTree'

const route = useRoute()
const personaId = route.params.id as string

const { getPersona } = usePersonas()
const { fetchAllSeries, linkPersonaToSeries, unlinkPersonaFromSeries } = useKalshi()
const { folders, fetchFolders } = useFileTree()
const { authFetch } = useAuthFetch()

const persona = ref<Awaited<ReturnType<typeof getPersona>>>(null)
const loadingPersona = ref(true)

// Series linking
const linkedSeries = ref<KalshiSeries[]>([])
const allSeries = ref<KalshiSeries[]>([])
const loadingSeries = ref(false)
const showLinkSeriesModal = ref(false)
const linking = ref(false)
const selectedSeriesId = ref<string | null>(null)
const selectedFolderId = ref<string | undefined>(undefined)

const folderOptions = computed(() =>
  folders.value.filter(f => !f.parent_id).map(f => ({ label: f.name, value: f.id }))
)

async function loadLinkedSeries() {
  loadingSeries.value = true
  try {
    const all = await fetchAllSeries()
    allSeries.value = all
    linkedSeries.value = all.filter(s => s.persona_ids?.includes(personaId))
  } finally {
    loadingSeries.value = false
  }
}

const availableSeries = computed(() => {
  const linkedIds = new Set(linkedSeries.value.map(s => s.id))
  return allSeries.value.filter(s => !linkedIds.has(s.id))
})

async function handleLinkSeries() {
  if (!selectedSeriesId.value) return
  linking.value = true
  try {
    await linkPersonaToSeries(selectedSeriesId.value, personaId, selectedFolderId.value)
    showLinkSeriesModal.value = false
    selectedSeriesId.value = null
    selectedFolderId.value = undefined
    await loadLinkedSeries()
  } finally {
    linking.value = false
  }
}

async function handleUnlinkSeries(seriesId: string) {
  await unlinkPersonaFromSeries(seriesId, personaId)
  await loadLinkedSeries()
}

// Persona transcripts
interface PersonaTranscript {
  id: string
  name: string | null
  youtube_url: string
  created_at: string
  is_public?: boolean
  is_premium?: boolean
}

const personaTranscripts = ref<PersonaTranscript[]>([])
const loadingTranscripts = ref(false)

async function loadPersonaTranscripts() {
  loadingTranscripts.value = true
  try {
    personaTranscripts.value = await authFetch<PersonaTranscript[]>(`/api/personas/${personaId}/transcripts`)
  } catch (e) {
    console.error('Failed to load persona transcripts:', e)
  } finally {
    loadingTranscripts.value = false
  }
}

async function toggleTranscriptVisibility(item: PersonaTranscript, field: 'is_public' | 'is_premium', value: boolean) {
  if (field === 'is_premium' && value && !item.is_public) {
    // Turning on premium auto-enables public
    item.is_public = true
    item.is_premium = true
    await authFetch(`/api/transcripts/${item.id}`, {
      method: 'PATCH',
      body: { is_public: true, is_premium: true },
    }).catch(() => {})
  } else if (field === 'is_public' && !value) {
    // Turning off public also turns off premium
    item.is_public = false
    item.is_premium = false
    await authFetch(`/api/transcripts/${item.id}`, {
      method: 'PATCH',
      body: { is_public: false, is_premium: false },
    }).catch(() => {})
  } else {
    item[field] = value
    await authFetch(`/api/transcripts/${item.id}`, {
      method: 'PATCH',
      body: { [field]: value },
    }).catch(() => {})
  }
}

onMounted(async () => {
  loadingPersona.value = true
  try {
    persona.value = await getPersona(personaId)
  } finally {
    loadingPersona.value = false
  }
  await Promise.all([loadLinkedSeries(), fetchFolders(), loadPersonaTranscripts()])
})
</script>

<template>
  <div class="max-w-7xl w-full">
    <!-- Header with back button -->
    <div class="mb-6">
      <NuxtLink to="/admin/personas"
        class="inline-flex items-center gap-1 text-gray-500 hover:text-gray-900 dark:hover:text-gray-100 transition-colors mb-4">
        <UIcon name="i-lucide-chevron-left" class="w-5 h-5" />
        <span class="text-base">Personas</span>
      </NuxtLink>

      <div v-if="loadingPersona" class="flex items-center justify-center p-8">
        <UIcon name="i-lucide-loader" class="w-6 h-6 animate-spin" />
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

    <!-- Linked Series -->
    <template v-if="persona">
      <div class="flex flex-wrap items-center justify-between gap-2 mb-3">
        <h2 class="text-xl font-semibold">Linked Series</h2>
        <UButton size="sm" icon="i-lucide-plus" @click="showLinkSeriesModal = true">Link to Series</UButton>
      </div>

      <div v-if="loadingSeries" class="flex items-center justify-center p-4">
        <UIcon name="i-lucide-loader" class="w-5 h-5 animate-spin" />
      </div>

      <div v-else-if="linkedSeries.length === 0" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        No series linked. Click "Link to Series" to associate this persona with a Kalshi series.
      </div>

      <div v-else class="flex flex-wrap gap-2">
        <div
          v-for="s in linkedSeries"
          :key="s.id"
          class="inline-flex items-center gap-2 px-3 py-2 border rounded-lg"
        >
          <span class="text-sm font-medium">{{ s.title || s.ticker }}</span>
          <UBadge v-if="s.frequency" color="primary" variant="subtle" size="xs">{{ s.frequency }}</UBadge>
          <UIcon
            name="i-lucide-x"
            class="w-4 h-4 text-gray-400 hover:text-red-500 cursor-pointer"
            @click.prevent="handleUnlinkSeries(s.id)"
          />
        </div>
      </div>
    </template>

    <!-- Transcripts -->
    <template v-if="persona">
      <div class="flex items-center justify-between mb-3 mt-8">
        <h2 class="text-xl font-semibold">Transcripts</h2>
        <UBadge v-if="personaTranscripts.length > 0" color="neutral" variant="subtle">
          {{ personaTranscripts.length }}
        </UBadge>
      </div>

      <div v-if="loadingTranscripts" class="flex items-center justify-center p-4">
        <UIcon name="i-lucide-loader" class="w-5 h-5 animate-spin" />
      </div>

      <div v-else-if="personaTranscripts.length === 0" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        No transcripts found matching this persona's aliases.
      </div>

      <div v-else class="divide-y divide-gray-100 dark:divide-gray-800">
        <div
          v-for="t in personaTranscripts"
          :key="t.id"
          class="flex flex-wrap items-center gap-3 py-3"
        >
          <NuxtLink
            :to="`/admin/transcripts/${t.id}`"
            class="flex-1 min-w-0 hover:underline"
          >
            <p class="text-sm font-medium truncate">{{ t.name || 'Untitled' }}</p>
            <p class="text-xs text-gray-400 mt-0.5">{{ new Date(t.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) }}</p>
          </NuxtLink>

          <div class="flex items-center gap-2 sm:gap-3 shrink-0">
            <USwitch
              :model-value="t.is_public ?? false"
              size="xs"
              label="Public"
              @update:model-value="toggleTranscriptVisibility(t, 'is_public', $event)"
            />
            <USwitch
              :model-value="t.is_premium ?? false"
              size="xs"
              label="Premium"
              @update:model-value="toggleTranscriptVisibility(t, 'is_premium', $event)"
            />
          </div>
        </div>
      </div>
    </template>

    <!-- Link Series Modal -->
    <UModal v-model:open="showLinkSeriesModal">
      <template #content>
        <div class="p-6">
          <h3 class="text-lg font-semibold mb-4">Link to Series</h3>

          <div v-if="availableSeries.length === 0" class="text-gray-500 text-sm">
            No available series to link.
          </div>
          <div v-else class="space-y-4">
            <div class="space-y-2 max-h-64 overflow-y-auto">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Series</label>
              <div
                v-for="s in availableSeries"
                :key="s.id"
                class="flex items-center gap-2 p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer"
                :class="{ 'ring-2 ring-primary': selectedSeriesId === s.id }"
                @click="selectedSeriesId = s.id"
              >
                <div class="flex-1 min-w-0">
                  <div class="text-sm font-medium truncate">{{ s.title || s.ticker }}</div>
                  <div class="text-xs text-gray-500">{{ s.event_count || 0 }} events</div>
                </div>
              </div>
            </div>

            <div class="space-y-1">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Transcript Folder (optional)</label>
              <USelectMenu
                v-model="selectedFolderId"
                :items="folderOptions"
                value-key="value"
                placeholder="All transcripts"
                class="w-full"
              />
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <UButton variant="ghost" @click="showLinkSeriesModal = false">Cancel</UButton>
            <UButton :loading="linking" :disabled="!selectedSeriesId" @click="handleLinkSeries">Link</UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
