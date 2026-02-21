<script setup lang="ts">
import { usePersonas } from '~/composables/usePersonas'
import { useKalshi, type KalshiSeries } from '~/composables/useKalshi'
import { useFileTree } from '~/composables/useFileTree'

const route = useRoute()
const personaId = route.params.id as string

const { getPersona } = usePersonas()
const { fetchAllSeries, linkPersonaToSeries, unlinkPersonaFromSeries } = useKalshi()
const { folders, fetchFolders } = useFileTree()

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

onMounted(async () => {
  loadingPersona.value = true
  try {
    persona.value = await getPersona(personaId)
  } finally {
    loadingPersona.value = false
  }
  await Promise.all([loadLinkedSeries(), fetchFolders()])
})
</script>

<template>
  <div class="max-w-7xl mx-auto">
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

    <!-- Linked Series -->
    <template v-if="persona">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-xl font-semibold">Linked Series</h2>
        <UButton size="sm" icon="i-heroicons-plus" @click="showLinkSeriesModal = true">Link to Series</UButton>
      </div>

      <div v-if="loadingSeries" class="flex items-center justify-center p-4">
        <UIcon name="i-heroicons-arrow-path" class="w-5 h-5 animate-spin" />
      </div>

      <div v-else-if="linkedSeries.length === 0" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        No series linked. Click "Link to Series" to associate this persona with a Kalshi series.
      </div>

      <div v-else class="flex flex-wrap gap-2">
        <NuxtLink
          v-for="s in linkedSeries"
          :key="s.id"
          :to="`/markets/${s.id}`"
          class="inline-flex items-center gap-2 px-3 py-2 border rounded-lg hover:border-primary-500 transition-colors"
        >
          <span class="text-sm font-medium">{{ s.title || s.ticker }}</span>
          <UBadge v-if="s.frequency" color="primary" variant="subtle" size="xs">{{ s.frequency }}</UBadge>
          <UIcon
            name="i-heroicons-x-mark"
            class="w-4 h-4 text-gray-400 hover:text-red-500 cursor-pointer"
            @click.prevent="handleUnlinkSeries(s.id)"
          />
        </NuxtLink>
      </div>
    </template>

    <!-- Link Series Modal -->
    <UModal v-model:open="showLinkSeriesModal">
      <template #content>
        <div class="p-6">
          <h3 class="text-lg font-semibold mb-4">Link to Series</h3>

          <div v-if="availableSeries.length === 0" class="text-gray-500 text-sm">
            No available series to link. Add series from the Markets page first.
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
