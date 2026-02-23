<script setup lang="ts">
import { useKalshi, type EventDetail, type PersonaEventMarket } from '~/composables/useKalshi'
import { usePersonas } from '~/composables/usePersonas'
import { useFileTree } from '~/composables/useFileTree'

const route = useRoute()
const eventTicker = route.params.id as string

const {
  getEventDetailByTicker, refreshEvent,
  linkPersonaToSeries, unlinkPersonaFromSeries,
} = useKalshi()
const { personas, fetchPersonas } = usePersonas()
const { folders, fetchFolders } = useFileTree()

const detail = ref<EventDetail | null>(null)
const loading = ref(true)
const refreshing = ref(false)

// DB IDs derived from loaded detail
const seriesId = computed(() => detail.value?.series?.id || '')
const eventId = computed(() => detail.value?.event?.id || '')

// Persona selection
const selectedPersonaId = ref<string | null>(null)

// Link persona modal
const showLinkModal = ref(false)
const linkPersonaId = ref<string | null>(null)
const linkFolderId = ref<string | undefined>(undefined)
const linking = ref(false)

const folderOptions = computed(() =>
  folders.value.filter(f => !f.parent_id).map(f => ({ label: f.name, value: f.id }))
)

async function loadDetail() {
  loading.value = true
  try {
    detail.value = await getEventDetailByTicker(eventTicker, selectedPersonaId.value || undefined)
    if (detail.value?.persona_ids?.length && !selectedPersonaId.value) {
      selectedPersonaId.value = detail.value.persona_ids[0] ?? null
    }
  } finally {
    loading.value = false
  }
}

async function reloadWithPersona() {
  loading.value = true
  try {
    detail.value = await getEventDetailByTicker(eventTicker, selectedPersonaId.value || undefined)
  } finally {
    loading.value = false
  }
}

async function handleRefresh() {
  if (!eventId.value || !seriesId.value) return
  refreshing.value = true
  try {
    await refreshEvent(seriesId.value, eventId.value)
    await reloadWithPersona()
  } finally {
    refreshing.value = false
  }
}

async function handleLinkPersona() {
  if (!linkPersonaId.value || !seriesId.value) return
  linking.value = true
  try {
    await linkPersonaToSeries(seriesId.value, linkPersonaId.value, linkFolderId.value)
    showLinkModal.value = false
    linkPersonaId.value = null
    linkFolderId.value = undefined
    await reloadWithPersona()
  } finally {
    linking.value = false
  }
}

async function handleUnlinkPersona(personaId: string) {
  if (!seriesId.value) return
  await unlinkPersonaFromSeries(seriesId.value, personaId)
  if (selectedPersonaId.value === personaId) {
    selectedPersonaId.value = null
  }
  await reloadWithPersona()
}

function getPersonaName(id: string): string {
  const p = personas.value.find(p => p.id === id)
  return p?.name || id.slice(0, 8)
}

const availablePersonas = computed(() => {
  const linkedIds = new Set(detail.value?.persona_ids || [])
  return personas.value.filter(p => !linkedIds.has(p.id))
})

watch(selectedPersonaId, () => {
  if (detail.value) reloadWithPersona()
})

onMounted(async () => {
  await Promise.all([fetchPersonas(), fetchFolders()])
  await loadDetail()
})
</script>

<template>
  <div class="max-w-6xl mx-auto">
    <!-- Back button -->
    <NuxtLink to="/markets"
      class="inline-flex items-center gap-1 text-gray-500 hover:text-gray-900 dark:hover:text-gray-100 transition-colors mb-4">
      <UIcon name="i-heroicons-chevron-left" class="w-5 h-5" />
      <span class="text-base">Markets</span>
    </NuxtLink>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center p-8">
      <UIcon name="i-heroicons-arrow-path" class="w-6 h-6 animate-spin" />
    </div>

    <div v-else-if="!detail" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
      Event not found.
    </div>

    <template v-else>
      <!-- Event header -->
      <div class="flex items-start gap-4 mb-6">
        <div class="flex-1 min-w-0">
          <h1 class="text-3xl font-bold truncate mb-1">{{ detail.event.title || eventTicker }}</h1>
          <p v-if="detail.series" class="text-gray-500 text-sm">{{ detail.series.title }}</p>
        </div>
        <UButton
          size="xs"
          variant="ghost"
          icon="i-heroicons-arrow-path"
          :loading="refreshing"
          @click="handleRefresh"
        />
      </div>

      <!-- Persona selector -->
      <div class="flex items-center gap-3 mb-4">
        <span class="text-sm font-medium text-gray-600 dark:text-gray-400">Personas:</span>
        <div class="flex items-center gap-1">
          <UBadge
            v-for="pid in detail.persona_ids"
            :key="pid"
            :color="selectedPersonaId === pid ? 'primary' : 'neutral'"
            :variant="selectedPersonaId === pid ? 'solid' : 'soft'"
            class="cursor-pointer"
            @click="selectedPersonaId = selectedPersonaId === pid ? null : pid"
          >
            {{ getPersonaName(pid) }}
            <UIcon
              name="i-heroicons-x-mark"
              class="w-3 h-3 ml-1"
              @click.stop="handleUnlinkPersona(pid)"
            />
          </UBadge>
        </div>
        <UButton size="xs" variant="ghost" icon="i-heroicons-plus" @click="showLinkModal = true">Link Persona</UButton>
      </div>

      <!-- Markets -->
      <div v-if="!detail.markets?.length" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        No markets for this event.
      </div>

      <div v-else class="space-y-3">
        <template v-for="m in detail.markets" :key="m.market?.id">
          <!-- With persona analysis -->
          <template v-if="m.term_results">
            <TermSection
              v-for="term in (m.search_config?.search_terms || []).length ? (m.search_config?.search_terms || []) : ['']"
              :key="`${m.market.id}-${term}`"
              :market-id="m.market.id"
              :question="m.market.question"
              :search-term="term"
              :term-result="m.term_results?.find((tr: any) => tr.search_term === term) || null"
              :last-price="m.market.last_price"
              :persona-id="selectedPersonaId || ''"
              :result="m.market.result"
              :close-time="m.market.close_time"
            />
          </template>
          <!-- Without persona analysis -->
          <div v-else class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
            <div class="flex items-center justify-between gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-800/50">
              <span class="text-sm font-medium truncate flex-1">{{ m.question || m.market?.question || '-' }}</span>
              <div class="flex items-center gap-2 shrink-0">
                <UBadge v-if="m.result || m.market?.result" :color="(m.result || m.market?.result) === 'yes' ? 'success' : 'error'" variant="subtle" size="xs">
                  {{ (m.result || m.market?.result).toUpperCase() }}
                </UBadge>
                <span v-if="m.last_price != null || m.market?.last_price != null" class="text-sm font-semibold text-primary">
                  {{ ((m.last_price ?? m.market?.last_price)).toFixed(0) }}%
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

    <!-- Link Persona Modal -->
    <UModal v-model:open="showLinkModal">
      <template #content>
        <div class="p-6">
          <h3 class="text-lg font-semibold mb-4">Link Persona to Series</h3>

          <div v-if="availablePersonas.length === 0" class="text-gray-500 text-sm">
            All personas are already linked.
          </div>
          <div v-else class="space-y-4">
            <div class="space-y-2">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Persona</label>
              <div
                v-for="p in availablePersonas"
                :key="p.id"
                class="flex items-center gap-2 p-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer"
                :class="{ 'ring-2 ring-primary': linkPersonaId === p.id }"
                @click="linkPersonaId = p.id"
              >
                <span class="font-medium text-sm">{{ p.name }}</span>
                <span v-if="p.description" class="text-xs text-gray-500 truncate">{{ p.description }}</span>
              </div>
            </div>

            <div class="space-y-1">
              <label class="text-sm font-medium text-gray-700 dark:text-gray-300">Transcript Folder (optional)</label>
              <USelectMenu
                v-model="linkFolderId"
                :items="folderOptions"
                value-key="value"
                placeholder="All transcripts"
                class="w-full"
              />
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <UButton variant="ghost" @click="showLinkModal = false">Cancel</UButton>
            <UButton :loading="linking" :disabled="!linkPersonaId" @click="handleLinkPersona">Link</UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
