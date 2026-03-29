<script lang="ts">
definePageMeta({ layout: 'admin', ssr: false })
</script>

<script setup lang="ts">
import { useAutoTranscription, type AutoSource, type AutoRun, type CreateSourceBody, type UpdateSourceBody } from '~/composables/useAutoTranscription'
import { usePersonas, type Persona } from '~/composables/usePersonas'

const {
  sources, runs, loading, error,
  fetchSources, createSource, updateSource, deleteSource,
  triggerCheck, fetchRuns,
} = useAutoTranscription()

const { personas, fetchPersonas } = usePersonas()
const { folders: fileTreeFolders, fetchFolders: fetchFileTreeFolders } = useFileTree()

// Modal state
const showSourceModal = ref(false)
const editingSource = ref<AutoSource | null>(null)

// Form fields
const formPersonaId = ref('')
const formSourceType = ref<'channel' | 'playlist'>('channel')
const formYoutubeUrl = ref('')
const formFolderId = ref<string | null>(null)
const formTitleKeywords = ref('')
const formCheckInterval = ref(360)
const formMaxVideos = ref(5)
const formIsEnabled = ref(true)
const saving = ref(false)

// Check trigger state
const checkingSourceId = ref<string | null>(null)

// Expanded run details
const expandedRunId = ref<string | null>(null)

const intervalOptions = [
  { label: 'Every 1 hour', value: 60 },
  { label: 'Every 3 hours', value: 180 },
  { label: 'Every 6 hours', value: 360 },
  { label: 'Every 12 hours', value: 720 },
  { label: 'Every 24 hours', value: 1440 },
]

const personaOptions = computed(() =>
  personas.value.map(p => ({ label: p.name, value: p.id }))
)

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

function openCreateModal() {
  editingSource.value = null
  formPersonaId.value = ''
  formSourceType.value = 'channel'
  formYoutubeUrl.value = ''
  formFolderId.value = null
  formTitleKeywords.value = ''
  formCheckInterval.value = 360
  formMaxVideos.value = 5
  formIsEnabled.value = true
  showSourceModal.value = true
}

function openEditModal(source: AutoSource) {
  editingSource.value = source
  formPersonaId.value = source.persona_id
  formSourceType.value = source.source_type
  formYoutubeUrl.value = source.youtube_url
  formFolderId.value = source.folder_id
  formTitleKeywords.value = source.title_filter || ''
  formCheckInterval.value = source.check_interval_minutes
  formMaxVideos.value = source.max_videos_per_check
  formIsEnabled.value = source.is_enabled
  showSourceModal.value = true
}

async function handleSave() {
  saving.value = true
  try {
    if (editingSource.value) {
      const body: UpdateSourceBody = {
        folder_id: formFolderId.value,
        check_interval_minutes: formCheckInterval.value,
        max_videos_per_check: formMaxVideos.value,
        title_filter: formTitleKeywords.value || null,
        is_enabled: formIsEnabled.value,
      }
      await updateSource(editingSource.value.id, body)
    } else {
      const body: CreateSourceBody = {
        persona_id: formPersonaId.value,
        source_type: formSourceType.value,
        youtube_url: formYoutubeUrl.value,
        folder_id: formFolderId.value,
        check_interval_minutes: formCheckInterval.value,
        max_videos_per_check: formMaxVideos.value,
        title_filter: formTitleKeywords.value || null,
      }
      await createSource(body)
    }
    showSourceModal.value = false
  } finally {
    saving.value = false
  }
}

async function handleDelete(source: AutoSource) {
  if (!confirm(`Delete auto-source "${source.source_name || source.youtube_url}"?`)) return
  await deleteSource(source.id)
}

async function handleCheck(source: AutoSource) {
  checkingSourceId.value = source.id
  await triggerCheck(source.id)
  // Refresh runs after a short delay to show the new run
  setTimeout(() => {
    fetchRuns()
    checkingSourceId.value = null
  }, 2000)
}

async function handleToggleEnabled(source: AutoSource) {
  await updateSource(source.id, { is_enabled: !source.is_enabled })
}

function formatInterval(minutes: number): string {
  if (minutes < 60) return `${minutes}m`
  if (minutes < 1440) return `${minutes / 60}h`
  return `${minutes / 1440}d`
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '-'
  const d = new Date(dateStr)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function runStatusColor(status: string): string {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'error'
  return 'warning'
}

const isCreateValid = computed(() => {
  if (editingSource.value) return true
  return formPersonaId.value && formYoutubeUrl.value.trim()
})

// Initialize
onMounted(async () => {
  await Promise.all([
    fetchSources(),
    fetchRuns(),
    fetchPersonas(),
    fetchFileTreeFolders(),
  ])
})
</script>

<template>
  <div class="p-4 sm:p-6 max-w-7xl w-full mx-auto space-y-8">
    <!-- Header -->
    <div>
      <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <h1 class="text-2xl sm:text-3xl font-bold mb-2">Auto Transcription</h1>
          <p class="text-gray-600 dark:text-gray-400">
            Automatically transcribe new videos from YouTube channels and playlists
          </p>
        </div>
        <UButton @click="openCreateModal" icon="i-lucide-plus">
          Add Source
        </UButton>
      </div>
    </div>

    <!-- Sources -->
    <div class="space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-xl font-semibold">Sources</h2>
        <UBadge v-if="sources.length > 0" color="neutral" variant="subtle">
          {{ sources.length }}
        </UBadge>
      </div>

      <div v-if="loading" class="flex items-center justify-center p-8">
        <UIcon name="i-lucide-loader" class="w-6 h-6 animate-spin" />
      </div>

      <div v-else-if="sources.length === 0" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        No auto-transcription sources configured. Click "Add Source" to monitor a YouTube channel or playlist.
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="source in sources"
          :key="source.id"
          class="p-4 border rounded-lg"
        >
          <div class="flex items-start justify-between mb-2">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 mb-1">
                <span class="font-semibold truncate">{{ source.source_name || source.youtube_url }}</span>
                <UBadge :color="source.source_type === 'channel' ? 'primary' : 'info'" variant="subtle" size="xs">
                  {{ source.source_type }}
                </UBadge>
                <UBadge v-if="!source.is_enabled" color="neutral" variant="subtle" size="xs">
                  disabled
                </UBadge>
              </div>
              <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-gray-500">
                <span v-if="source.persona_name">{{ source.persona_name }}</span>
                <span>Every {{ formatInterval(source.check_interval_minutes) }}</span>
                <span v-if="source.title_filter" class="font-mono text-xs">filter: {{ source.title_filter }}</span>
                <span v-if="source.last_run_at" class="flex items-center gap-1">
                  Last run:
                  <UBadge :color="runStatusColor(source.last_run_status || '')" variant="subtle" size="xs">
                    {{ source.last_run_status }}
                  </UBadge>
                  {{ formatDate(source.last_run_at) }}
                </span>
              </div>
            </div>
            <div class="flex items-center gap-1 shrink-0 ml-2">
              <UButton
                size="xs"
                variant="ghost"
                icon="i-lucide-play"
                :loading="checkingSourceId === source.id"
                @click="handleCheck(source)"
              />
              <UButton
                size="xs"
                variant="ghost"
                :icon="source.is_enabled ? 'i-lucide-pause' : 'i-lucide-play-circle'"
                @click="handleToggleEnabled(source)"
              />
              <UButton size="xs" variant="ghost" icon="i-lucide-pencil" @click="openEditModal(source)" />
              <UButton size="xs" variant="ghost" color="error" icon="i-lucide-trash-2" @click="handleDelete(source)" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Recent Runs -->
    <div class="space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-xl font-semibold">Recent Runs</h2>
        <UButton variant="ghost" size="xs" icon="i-lucide-refresh-cw" @click="fetchRuns()">
          Refresh
        </UButton>
      </div>

      <div v-if="runs.length === 0" class="text-gray-500 text-base p-4 border border-dashed rounded-lg">
        No runs yet. Add a source and trigger a check to see results here.
      </div>

      <div v-else class="space-y-2">
        <div
          v-for="run in runs"
          :key="run.id"
          class="border rounded-lg overflow-hidden"
        >
          <div
            class="flex items-center gap-3 p-3 cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors"
            @click="expandedRunId = expandedRunId === run.id ? null : run.id"
          >
            <UIcon
              :name="expandedRunId === run.id ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
              class="w-4 h-4 shrink-0 text-gray-400"
            />
            <UBadge :color="runStatusColor(run.status)" variant="subtle" size="xs">
              {{ run.status }}
            </UBadge>
            <span class="text-sm font-medium truncate">
              {{ run.source_name || run.persona_name || run.auto_source_id }}
            </span>
            <div class="flex items-center gap-3 ml-auto text-xs text-gray-500 shrink-0">
              <span v-if="run.videos_found">{{ run.videos_found }} found</span>
              <span v-if="run.videos_queued" class="text-green-600 dark:text-green-400">{{ run.videos_queued }} queued</span>
              <span v-if="run.videos_skipped">{{ run.videos_skipped }} skipped</span>
              <span>{{ formatDate(run.started_at) }}</span>
            </div>
          </div>

          <!-- Expanded details -->
          <div v-if="expandedRunId === run.id" class="border-t px-3 pb-3 pt-2 space-y-2">
            <div v-if="run.error_message" class="text-sm text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-950/20 p-2 rounded">
              {{ run.error_message }}
            </div>
            <div v-if="run.details && run.details.length > 0" class="space-y-1">
              <div
                v-for="(detail, i) in run.details"
                :key="i"
                class="flex items-center gap-2 text-sm"
              >
                <UBadge
                  :color="detail.action === 'queued' ? 'success' : detail.action === 'exists' ? 'neutral' : detail.action === 'filtered' ? 'warning' : 'error'"
                  variant="subtle"
                  size="xs"
                >
                  {{ detail.action }}
                </UBadge>
                <span class="truncate">{{ detail.title }}</span>
              </div>
            </div>
            <div v-else class="text-sm text-gray-400">No video details recorded.</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Create/Edit Source Modal -->
    <UModal v-model:open="showSourceModal">
      <template #content>
        <div class="p-6 max-h-[85vh] overflow-y-auto">
          <h3 class="text-lg font-semibold mb-4">
            {{ editingSource ? 'Edit Source' : 'Add Auto-Transcription Source' }}
          </h3>

          <div class="space-y-4">
            <!-- Persona (only on create) -->
            <UFormField v-if="!editingSource" label="Persona" required>
              <USelectMenu
                v-model="formPersonaId"
                :items="personaOptions"
                placeholder="Select persona..."
                searchable
                class="w-full"
                value-key="value"
                label-key="label"
              />
            </UFormField>

            <!-- Source type (only on create) -->
            <UFormField v-if="!editingSource" label="Source Type">
              <div class="flex gap-2">
                <UButton
                  :variant="formSourceType === 'channel' ? 'solid' : 'outline'"
                  size="sm"
                  @click="formSourceType = 'channel'"
                >
                  Channel
                </UButton>
                <UButton
                  :variant="formSourceType === 'playlist' ? 'solid' : 'outline'"
                  size="sm"
                  @click="formSourceType = 'playlist'"
                >
                  Playlist
                </UButton>
              </div>
            </UFormField>

            <!-- YouTube URL (only on create) -->
            <UFormField v-if="!editingSource" label="YouTube URL" required>
              <UInput
                v-model="formYoutubeUrl"
                :placeholder="formSourceType === 'channel' ? 'https://www.youtube.com/@ChannelName' : 'https://www.youtube.com/playlist?list=...'"
                class="w-full"
              />
            </UFormField>

            <!-- Folder -->
            <UFormField label="Target Folder" description="Where auto-transcribed videos will be saved">
              <USelectMenu
                v-model="formFolderId"
                :items="folderOptions"
                placeholder="Select folder..."
                searchable
                class="w-full"
                value-key="value"
                label-key="label"
              />
            </UFormField>

            <!-- Title keywords filter -->
            <UFormField label="Title Keywords" description="Only transcribe videos whose title contains any of these words (comma-separated)">
              <UInput v-model="formTitleKeywords" class="w-full" placeholder="e.g., PMQ, prime minister, press briefing" />
            </UFormField>

            <!-- Check interval -->
            <UFormField label="Check Interval">
              <USelectMenu
                v-model="formCheckInterval"
                :items="intervalOptions"
                class="w-full"
                value-key="value"
                label-key="label"
              />
            </UFormField>

            <!-- Max videos per check -->
            <UFormField label="Max Videos Per Check" description="Limit how many new videos are transcribed per check">
              <UInput v-model.number="formMaxVideos" type="number" :min="1" :max="20" class="w-full" />
            </UFormField>

            <!-- Enabled toggle (only on edit) -->
            <div v-if="editingSource" class="flex items-center justify-between">
              <span class="text-sm font-medium">Enabled</span>
              <USwitch v-model="formIsEnabled" />
            </div>
          </div>

          <div class="flex justify-end gap-2 mt-6">
            <UButton variant="ghost" @click="showSourceModal = false">Cancel</UButton>
            <UButton @click="handleSave" :loading="saving" :disabled="!isCreateValid">
              {{ editingSource ? 'Save' : 'Create' }}
            </UButton>
          </div>
        </div>
      </template>
    </UModal>
  </div>
</template>
