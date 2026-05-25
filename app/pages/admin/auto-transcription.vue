<script lang="ts">
definePageMeta({ layout: 'admin', ssr: false })
</script>

<script setup lang="ts">
import {
  useAutoTranscription,
  type AutoSource,
  type CreateSourceBody,
  type UpdateSourceBody,
  type RunResult,
  type TimelineEntry,
} from '~/composables/useAutoTranscription'
import { usePersonas } from '~/composables/usePersonas'

const {
  sources, timeline, loading,
  fetchSources, createSource, updateSource, deleteSource,
  runSource, backfillSource, fetchTimeline,
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
const formMaxVideos = ref(5)
const formBackfillLimit = ref<number>(500)
const saving = ref(false)

// Per-source running state + last result
const runningSourceId = ref<string | null>(null)
const backfillingSourceId = ref<string | null>(null)
const lastRun = ref<{ source: AutoSource; result: RunResult; mode: 'run' | 'backfill' } | null>(null)
const lastRunError = ref<string | null>(null)

// Resume-stuck-jobs state
const { authFetch } = useAuthFetch()
const resumingStuck = ref(false)
const lastResumeMessage = ref<string | null>(null)

// Auto-refresh timeline while any entry has an in-flight job
let refreshTimer: ReturnType<typeof setInterval> | null = null

const personaOptions = computed(() =>
  personas.value.map(p => ({ label: p.name, value: p.id }))
)

const folderOptions = computed(() => {
  const buildTree = (parentId: string | null, depth = 0): { label: string; value: string }[] => {
    const children = fileTreeFolders.value.filter(f => f.parent_id === parentId)
    const out: { label: string; value: string }[] = []
    for (const folder of children) {
      const indent = '  '.repeat(depth)
      out.push({ label: `${indent}${folder.name}`, value: folder.id })
      out.push(...buildTree(folder.id, depth + 1))
    }
    return out
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
  formMaxVideos.value = 5
  formBackfillLimit.value = 500
  showSourceModal.value = true
}

function openEditModal(source: AutoSource) {
  editingSource.value = source
  formPersonaId.value = source.persona_id
  formSourceType.value = source.source_type
  formYoutubeUrl.value = source.youtube_url
  formFolderId.value = source.folder_id
  formTitleKeywords.value = source.title_filter || ''
  formMaxVideos.value = source.max_videos_per_check
  formBackfillLimit.value = source.backfill_limit ?? 0
  showSourceModal.value = true
}

async function handleSave() {
  saving.value = true
  try {
    if (editingSource.value) {
      const body: UpdateSourceBody = {
        folder_id: formFolderId.value,
        max_videos_per_check: formMaxVideos.value,
        backfill_limit: formBackfillLimit.value || null,
        title_filter: formTitleKeywords.value || null,
      }
      await updateSource(editingSource.value.id, body)
    } else {
      const body: CreateSourceBody = {
        persona_id: formPersonaId.value,
        source_type: formSourceType.value,
        youtube_url: formYoutubeUrl.value,
        folder_id: formFolderId.value,
        max_videos_per_check: formMaxVideos.value,
        backfill_limit: formBackfillLimit.value || null,
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
  if (!confirm(`Delete source "${source.source_name || source.youtube_url}"?`)) return
  await deleteSource(source.id)
  await fetchTimeline()
}

async function handleRun(source: AutoSource) {
  runningSourceId.value = source.id
  lastRun.value = null
  lastRunError.value = null
  try {
    const result = await runSource(source.id)
    if (result) {
      lastRun.value = { source, result, mode: 'run' }
      await fetchTimeline()
    }
  } catch (e: any) {
    lastRunError.value = e?.message || 'Run failed'
  } finally {
    runningSourceId.value = null
  }
}

async function handleResumeStuck() {
  resumingStuck.value = true
  lastResumeMessage.value = null
  try {
    const result = await authFetch<{ resumed: number }>('/api/jobs/resume-orphaned', { method: 'POST' })
    const n = result?.resumed ?? 0
    lastResumeMessage.value = n === 0
      ? 'No stuck jobs to resume.'
      : `Resumed ${n} stuck job${n === 1 ? '' : 's'}. They will reappear in the timeline as they progress.`
    await fetchTimeline()
  } catch (e: any) {
    lastResumeMessage.value = e?.message || 'Resume failed'
  } finally {
    resumingStuck.value = false
  }
}

async function handleBackfill(source: AutoSource) {
  const cap = source.backfill_limit
  const capDesc = cap && cap > 0 ? `up to ${cap}` : 'every'
  if (!confirm(`Backfill "${source.source_name || source.youtube_url}"?\n\nThis will queue ${capDesc} previously-unseen video from this source. Only run this once per source.`)) return
  backfillingSourceId.value = source.id
  lastRun.value = null
  lastRunError.value = null
  try {
    const result = await backfillSource(source.id)
    if (result) {
      lastRun.value = { source, result, mode: 'backfill' }
      await fetchTimeline()
    }
  } catch (e: any) {
    lastRunError.value = e?.message || 'Backfill failed'
  } finally {
    backfillingSourceId.value = null
  }
}

const isCreateValid = computed(() => {
  if (editingSource.value) return true
  return formPersonaId.value && formYoutubeUrl.value.trim()
})

// ----- Timeline grouping & status -----

function dayKey(iso: string | null): string {
  if (!iso) return 'Unknown'
  const d = new Date(iso)
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(today.getDate() - 1)
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate()
  if (sameDay(d, today)) return 'Today'
  if (sameDay(d, yesterday)) return 'Yesterday'
  return d.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric', year: today.getFullYear() === d.getFullYear() ? undefined : 'numeric' })
}

function timeOf(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
}

const groupedTimeline = computed(() => {
  const groups: { day: string; entries: TimelineEntry[] }[] = []
  for (const entry of timeline.value) {
    const day = dayKey(entry.created_at)
    let group = groups[groups.length - 1]
    if (!group || group.day !== day) {
      group = { day, entries: [] }
      groups.push(group)
    }
    group.entries.push(entry)
  }
  return groups
})

interface EntryStatus {
  label: string
  color: 'success' | 'info' | 'warning' | 'error' | 'neutral' | 'primary'
  icon: string
  spinning?: boolean
}

function statusOf(entry: TimelineEntry): EntryStatus {
  if (entry.action === 'filtered') {
    return { label: 'Filtered out', color: 'neutral', icon: 'i-lucide-filter' }
  }
  if (entry.action === 'skipped') {
    return { label: 'Skipped', color: 'neutral', icon: 'i-lucide-skip-forward' }
  }
  // action === 'transcribed'
  const js = entry.job_status
  if (!js) {
    return { label: 'Transcribed', color: 'success', icon: 'i-lucide-check' }
  }
  if (js === 'completed') {
    return { label: 'Transcribed', color: 'success', icon: 'i-lucide-check' }
  }
  if (js === 'failed') {
    return { label: 'Failed', color: 'error', icon: 'i-lucide-x' }
  }
  if (js === 'cancelled') {
    return { label: 'Cancelled', color: 'neutral', icon: 'i-lucide-ban' }
  }
  if (js === 'pending' || js === 'queued') {
    return { label: 'Queued', color: 'info', icon: 'i-lucide-clock' }
  }
  if (js === 'downloading') {
    return { label: 'Downloading', color: 'info', icon: 'i-lucide-download', spinning: true }
  }
  if (js === 'transcribing') {
    return { label: 'Transcribing', color: 'info', icon: 'i-lucide-loader', spinning: true }
  }
  return { label: js, color: 'info', icon: 'i-lucide-loader', spinning: true }
}

const hasActiveJob = computed(() =>
  timeline.value.some(e => {
    const s = e.job_status
    return s && s !== 'completed' && s !== 'failed' && s !== 'cancelled'
  })
)

function startAutoRefresh() {
  if (refreshTimer) return
  refreshTimer = setInterval(() => {
    if (hasActiveJob.value) {
      fetchTimeline()
    }
  }, 5000)
}

function stopAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}

onMounted(async () => {
  await Promise.all([
    fetchSources(),
    fetchTimeline(),
    fetchPersonas(),
    fetchFileTreeFolders(),
  ])
  startAutoRefresh()
})

onBeforeUnmount(stopAutoRefresh)
</script>

<template>
  <div class="p-4 sm:p-6 max-w-5xl w-full mx-auto space-y-10">
    <!-- Header -->
    <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
      <div>
        <h1 class="text-2xl sm:text-3xl font-bold mb-1">Auto Transcription</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          YouTube channels and playlists you can run on demand to transcribe new videos.
        </p>
      </div>
      <UButton @click="openCreateModal" icon="i-lucide-plus">
        Add Source
      </UButton>
    </div>

    <!-- Last run banner -->
    <div
      v-if="lastRun"
      class="flex items-start gap-3 p-3 rounded-lg border border-green-200 dark:border-green-900/40 bg-green-50/60 dark:bg-green-950/20"
    >
      <UIcon name="i-lucide-check-circle-2" class="w-5 h-5 mt-0.5 text-green-600 dark:text-green-400 shrink-0" />
      <div class="flex-1 text-sm">
        <div class="font-medium">
          {{ lastRun.source.source_name || lastRun.source.youtube_url }}
          <span v-if="lastRun.mode === 'backfill'" class="text-xs font-normal text-gray-500 dark:text-gray-400 ml-1">(backfill)</span>
        </div>
        <div class="text-gray-600 dark:text-gray-400">
          Found {{ lastRun.result.videos_found }}.
          <span v-if="lastRun.result.videos_queued > 0" class="text-green-700 dark:text-green-400 font-medium">
            Queued {{ lastRun.result.videos_queued }} new
          </span>
          <span v-else>No new videos to queue</span>
          <span v-if="lastRun.result.videos_existing > 0">
            · {{ lastRun.result.videos_existing }} already transcribed
          </span>
          <span v-if="lastRun.result.videos_filtered > 0">
            · {{ lastRun.result.videos_filtered }} filtered
          </span>
        </div>
      </div>
      <UButton variant="ghost" size="xs" icon="i-lucide-x" @click="lastRun = null" />
    </div>

    <div
      v-if="lastRunError"
      class="flex items-start gap-3 p-3 rounded-lg border border-red-200 dark:border-red-900/40 bg-red-50/60 dark:bg-red-950/20"
    >
      <UIcon name="i-lucide-alert-circle" class="w-5 h-5 mt-0.5 text-red-600 dark:text-red-400 shrink-0" />
      <div class="flex-1 text-sm text-red-700 dark:text-red-300">{{ lastRunError }}</div>
      <UButton variant="ghost" size="xs" icon="i-lucide-x" @click="lastRunError = null" />
    </div>

    <!-- Sources -->
    <section class="space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">Sources</h2>
        <UBadge v-if="sources.length > 0" color="neutral" variant="subtle">{{ sources.length }}</UBadge>
      </div>

      <div v-if="loading && sources.length === 0" class="flex items-center justify-center p-8">
        <UIcon name="i-lucide-loader" class="w-6 h-6 animate-spin text-gray-400" />
      </div>

      <div v-else-if="sources.length === 0" class="text-sm text-gray-500 p-6 border border-dashed rounded-lg text-center">
        No sources yet. Add a YouTube channel or playlist to get started.
      </div>

      <div v-else class="grid gap-3">
        <div
          v-for="source in sources"
          :key="source.id"
          class="group flex flex-col sm:flex-row sm:items-center gap-3 p-4 border rounded-lg hover:border-gray-300 dark:hover:border-gray-700 transition-colors"
        >
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 mb-1 flex-wrap">
              <span class="font-semibold truncate">{{ source.source_name || source.youtube_url }}</span>
              <UBadge :color="source.source_type === 'channel' ? 'primary' : 'info'" variant="subtle" size="xs">
                {{ source.source_type }}
              </UBadge>
            </div>
            <div class="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
              <span v-if="source.persona_name" class="flex items-center gap-1">
                <UIcon name="i-lucide-user" class="w-3 h-3" />
                {{ source.persona_name }}
              </span>
              <span class="flex items-center gap-1">
                <UIcon name="i-lucide-hash" class="w-3 h-3" />
                up to {{ source.max_videos_per_check }} per run
              </span>
              <span class="flex items-center gap-1">
                <UIcon name="i-lucide-history" class="w-3 h-3" />
                backfill {{ source.backfill_limit && source.backfill_limit > 0 ? source.backfill_limit : '∞' }}
              </span>
              <span v-if="source.title_filter" class="flex items-center gap-1 font-mono">
                <UIcon name="i-lucide-filter" class="w-3 h-3" />
                {{ source.title_filter }}
              </span>
            </div>
          </div>
          <div class="flex items-center gap-1 shrink-0">
            <UButton
              size="sm"
              icon="i-lucide-play"
              :loading="runningSourceId === source.id"
              :disabled="(runningSourceId !== null && runningSourceId !== source.id) || backfillingSourceId !== null"
              @click="handleRun(source)"
            >
              Run
            </UButton>
            <UButton
              size="sm"
              variant="outline"
              icon="i-lucide-history"
              :loading="backfillingSourceId === source.id"
              :disabled="(backfillingSourceId !== null && backfillingSourceId !== source.id) || runningSourceId !== null"
              @click="handleBackfill(source)"
            >
              Backfill
            </UButton>
            <UButton size="sm" variant="ghost" icon="i-lucide-pencil" @click="openEditModal(source)" />
            <UButton size="sm" variant="ghost" color="error" icon="i-lucide-trash-2" @click="handleDelete(source)" />
          </div>
        </div>
      </div>
    </section>

    <!-- Timeline -->
    <section class="space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-lg font-semibold">Timeline</h2>
        <div class="flex items-center gap-2">
          <UButton
            variant="outline"
            size="xs"
            icon="i-lucide-play-circle"
            :loading="resumingStuck"
            @click="handleResumeStuck"
          >
            Resume stuck jobs
          </UButton>
          <UButton variant="ghost" size="xs" icon="i-lucide-refresh-cw" @click="fetchTimeline()">
            Refresh
          </UButton>
        </div>
      </div>

      <div
        v-if="lastResumeMessage"
        class="flex items-start gap-3 p-3 rounded-lg border border-blue-200 dark:border-blue-900/40 bg-blue-50/60 dark:bg-blue-950/20 text-sm"
      >
        <UIcon name="i-lucide-info" class="w-5 h-5 mt-0.5 text-blue-600 dark:text-blue-400 shrink-0" />
        <div class="flex-1 text-gray-700 dark:text-gray-300">{{ lastResumeMessage }}</div>
        <UButton variant="ghost" size="xs" icon="i-lucide-x" @click="lastResumeMessage = null" />
      </div>

      <div v-if="timeline.length === 0" class="text-sm text-gray-500 p-6 border border-dashed rounded-lg text-center">
        Nothing yet. Run a source to start populating the timeline.
      </div>

      <div v-else class="relative space-y-8">
        <div
          v-for="group in groupedTimeline"
          :key="group.day"
          class="space-y-2"
        >
          <div class="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400 px-1">
            {{ group.day }}
          </div>
          <div class="relative">
            <!-- Vertical timeline rail -->
            <div class="absolute left-[15px] top-2 bottom-2 w-px bg-gray-200 dark:bg-gray-800" />
            <ul class="space-y-1.5">
              <li
                v-for="entry in group.entries"
                :key="entry.id"
                class="relative flex items-start gap-3 pl-9 pr-2 py-2 rounded-md hover:bg-gray-50 dark:hover:bg-gray-900/60 transition-colors"
              >
                <!-- Status dot on the rail -->
                <span
                  class="absolute left-2 top-3 w-3.5 h-3.5 rounded-full border-2 border-white dark:border-gray-950 flex items-center justify-center"
                  :class="{
                    'bg-green-500': statusOf(entry).color === 'success',
                    'bg-blue-500': statusOf(entry).color === 'info' || statusOf(entry).color === 'primary',
                    'bg-red-500': statusOf(entry).color === 'error',
                    'bg-gray-400': statusOf(entry).color === 'neutral' || statusOf(entry).color === 'warning',
                  }"
                />
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 flex-wrap">
                    <a
                      :href="entry.youtube_url"
                      target="_blank"
                      rel="noopener"
                      class="text-sm font-medium hover:underline truncate max-w-md"
                    >
                      {{ entry.video_title || entry.youtube_url }}
                    </a>
                    <UBadge
                      :color="statusOf(entry).color"
                      variant="subtle"
                      size="xs"
                      class="shrink-0"
                    >
                      <UIcon
                        :name="statusOf(entry).icon"
                        class="w-3 h-3 mr-1"
                        :class="{ 'animate-spin': statusOf(entry).spinning }"
                      />
                      {{ statusOf(entry).label }}
                    </UBadge>
                  </div>
                  <div class="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                    <span>{{ timeOf(entry.created_at) }}</span>
                    <span v-if="entry.source_name">·</span>
                    <span v-if="entry.source_name" class="truncate max-w-[200px]">{{ entry.source_name }}</span>
                    <span v-if="entry.persona_name">·</span>
                    <span v-if="entry.persona_name">{{ entry.persona_name }}</span>
                    <template v-if="entry.transcript_id">
                      <span>·</span>
                      <NuxtLink
                        :to="`/admin/transcripts/${entry.transcript_id}`"
                        class="text-primary hover:underline"
                      >
                        View transcript
                      </NuxtLink>
                    </template>
                  </div>
                  <div v-if="entry.job_error" class="text-xs text-red-600 dark:text-red-400 mt-1 truncate">
                    {{ entry.job_error }}
                  </div>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </section>

    <!-- Create/Edit modal -->
    <UModal v-model:open="showSourceModal">
      <template #content>
        <div class="p-6 max-h-[85vh] overflow-y-auto">
          <h3 class="text-lg font-semibold mb-4">
            {{ editingSource ? 'Edit Source' : 'Add Source' }}
          </h3>

          <div class="space-y-4">
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

            <UFormField v-if="!editingSource" label="YouTube URL" required>
              <UInput
                v-model="formYoutubeUrl"
                :placeholder="formSourceType === 'channel' ? 'https://www.youtube.com/@ChannelName' : 'https://www.youtube.com/playlist?list=...'"
                class="w-full"
              />
            </UFormField>

            <UFormField label="Target Folder" description="Where transcripts produced by this source will be saved">
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

            <UFormField label="Title Keywords" description="Only transcribe videos whose title contains any of these (comma-separated, case-insensitive). Leave blank to allow all.">
              <UInput v-model="formTitleKeywords" class="w-full" placeholder="e.g., PMQ, prime minister, press briefing" />
            </UFormField>

            <UFormField label="Max videos per run" description="Safety cap on how many new videos a single run can queue">
              <UInput v-model.number="formMaxVideos" type="number" :min="1" :max="50" class="w-full" />
            </UFormField>

            <UFormField label="Backfill limit" description="One-shot backfill cap — pulls a source's full history. 0 = unlimited (everything yt-dlp can list).">
              <UInput v-model.number="formBackfillLimit" type="number" :min="0" class="w-full" />
            </UFormField>
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
