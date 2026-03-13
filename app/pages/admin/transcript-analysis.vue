<script setup lang="ts">
definePageMeta({ layout: 'admin' })

const { authFetch } = useAuthFetch()
const { folders, fetchFolders } = useFileTree()

interface Report {
  id: string
  folder_id: string | null
  transcript_count: number
  report?: string
  created_at: string
}

const folderId = ref<string | null>(null)
const jobId = ref<string | null>(null)
const analyzing = ref(false)
const result = ref<string | null>(null)
const launchError = ref<string | null>(null)
const reports = ref<Report[]>([])
const selectedReportId = ref<string | null>(null)
const loadingReports = ref(false)

const { progress, error: sseError, isActive, statusLabel } = useJobProgress(jobId)

// Fetch past reports + folders on mount
onMounted(async () => {
  await Promise.all([loadReports(), fetchFolders()])
})

async function loadReports() {
  loadingReports.value = true
  try {
    reports.value = await authFetch<Report[]>('/api/analysis/transcript-analysis/reports')
  } catch { /* ignore */ } finally {
    loadingReports.value = false
  }
}

function folderName(fId: string | null): string {
  if (!fId) return 'Unknown'
  return folders.value.find(f => f.id === fId)?.name || fId.slice(0, 8)
}

// Watch for completion — extract result from stage_progress and refresh list
watch(progress, async (p) => {
  if (p?.status === 'completed' && p.stage_progress) {
    const sp = p.stage_progress as Record<string, any>
    if (sp.result) {
      result.value = sp.result
      await loadReports()
    }
  }
})

const progressDetail = computed(() => {
  if (!progress.value?.stage_progress) return null
  const sp = progress.value.stage_progress as Record<string, any>
  const detail = sp.substep_detail || ''
  const current = sp.current_chunk
  const total = sp.total_chunks
  if (current && total) {
    return `${detail} (${current}/${total})`
  }
  return detail
})

async function startAnalysis() {
  if (!folderId.value) return

  analyzing.value = true
  launchError.value = null
  result.value = null
  selectedReportId.value = null

  try {
    const data = await authFetch<{ jobId: string }>('/api/analysis/transcript-analysis', {
      method: 'POST',
      body: { folderId: folderId.value }
    })
    jobId.value = data.jobId
  } catch (e: any) {
    launchError.value = e?.data?.detail || e?.message || 'Failed to start analysis'
  } finally {
    analyzing.value = false
  }
}

async function viewReport(reportId: string) {
  selectedReportId.value = reportId
  result.value = null
  try {
    const report = await authFetch<Report>(`/api/analysis/transcript-analysis/reports/${reportId}`)
    result.value = report.report || null
  } catch {
    result.value = null
  }
}

async function deleteReport(reportId: string) {
  try {
    await authFetch(`/api/analysis/transcript-analysis/reports/${reportId}`, { method: 'DELETE' })
    reports.value = reports.value.filter(r => r.id !== reportId)
    if (selectedReportId.value === reportId) {
      selectedReportId.value = null
      result.value = null
    }
  } catch { /* ignore */ }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric', year: 'numeric', hour: '2-digit', minute: '2-digit'
  })
}
</script>

<template>
  <div class="max-w-4xl mx-auto p-6 space-y-6">
    <h1 class="text-2xl font-bold">Transcript Analysis</h1>
    <p class="text-sm text-gray-500">
      Select a folder of transcripts to analyze with AI. Extracts trading style, strategies, tips, and common mistakes.
    </p>

    <!-- Folder picker + launch -->
    <div class="flex items-end gap-4">
      <div class="w-80">
        <FolderPicker v-model="folderId" />
      </div>
      <UButton
        label="Analyze"
        icon="i-lucide-brain"
        :loading="analyzing"
        :disabled="!folderId || !!isActive"
        @click="startAnalysis"
      />
    </div>

    <!-- Errors -->
    <div v-if="launchError" class="text-red-500 text-sm">{{ launchError }}</div>
    <div v-if="sseError" class="text-red-500 text-sm">{{ sseError }}</div>

    <!-- Progress -->
    <div v-if="isActive" class="space-y-2 p-4 rounded-lg bg-gray-50 dark:bg-gray-800">
      <div class="flex items-center gap-2">
        <UIcon name="i-lucide-loader-circle" class="size-4 animate-spin text-primary" />
        <span class="font-medium">{{ statusLabel }}</span>
      </div>
      <p v-if="progressDetail" class="text-sm text-gray-600 dark:text-gray-400">
        {{ progressDetail }}
      </p>
      <div
        v-if="progress?.stage_progress?.current_chunk && progress?.stage_progress?.total_chunks"
        class="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2"
      >
        <div
          class="bg-primary rounded-full h-2 transition-all duration-300"
          :style="{ width: `${(progress.stage_progress.current_chunk / progress.stage_progress.total_chunks) * 100}%` }"
        />
      </div>
    </div>

    <!-- Failed -->
    <div v-if="progress?.status === 'failed'" class="p-4 rounded-lg bg-red-50 dark:bg-red-900/20">
      <p class="text-red-600 dark:text-red-400 font-medium">Analysis failed</p>
      <p v-if="progress.error_message" class="text-sm text-red-500 mt-1">{{ progress.error_message }}</p>
    </div>

    <!-- Past reports -->
    <div v-if="reports.length > 0" class="space-y-3">
      <h2 class="text-lg font-semibold">Past Reports</h2>
      <div class="space-y-2">
        <div
          v-for="r in reports"
          :key="r.id"
          class="flex items-center justify-between p-3 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
          :class="{ 'ring-2 ring-primary': selectedReportId === r.id }"
        >
          <button class="flex-1 text-left" @click="viewReport(r.id)">
            <span class="font-medium text-sm">{{ folderName(r.folder_id) }}</span>
            <span class="text-xs text-gray-500 ml-2">{{ r.transcript_count }} transcripts</span>
            <span class="text-xs text-gray-400 ml-2">{{ formatDate(r.created_at) }}</span>
          </button>
          <UButton
            icon="i-lucide-trash-2"
            variant="ghost"
            color="red"
            size="xs"
            @click.stop="deleteReport(r.id)"
          />
        </div>
      </div>
    </div>

    <!-- Result -->
    <div v-if="result" class="p-6 rounded-lg border border-gray-200 dark:border-gray-700">
      <pre class="whitespace-pre-wrap text-sm leading-relaxed">{{ result }}</pre>
    </div>
  </div>
</template>
