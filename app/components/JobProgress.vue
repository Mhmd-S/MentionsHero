<template>
  <div v-if="progress" class="space-y-3">
    <div class="flex items-center justify-between">
      <span class="text-sm font-medium">{{ statusLabel }}</span>
      <span v-if="chunkInfo" class="text-xs text-gray-500">{{ chunkInfo }}</span>
    </div>

    <UProgress
      :value="progressPercent"
      :color="progressColor"
      size="md"
    />

    <div v-if="isJobActive && substepLabel" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
      <UIcon name="i-heroicons-cog-6-tooth" class="size-4 animate-spin" />
      <span>{{ substepLabel }}</span>
    </div>
    <p v-if="isJobActive && substepDetail" class="text-xs text-gray-500 dark:text-gray-500 ml-6">
      {{ substepDetail }}
    </p>

    <p v-if="progress.status === 'failed' && progress.error_message" class="text-sm text-red-600 dark:text-red-400">
      {{ progress.error_message }}
    </p>
  </div>
</template>

<script setup lang="ts">
import type { JobProgress, JobStatus } from '~/composables/useJobProgress'

const props = defineProps<{
  progress: JobProgress | null
  statusLabel: string
  chunkInfo: string | null
  substepLabel: string | null
  substepDetail: string | null
}>()

const isJobActive = computed(() => {
  return props.progress && !['completed', 'failed', 'cancelled'].includes(props.progress.status)
})

const stages: JobStatus[] = ['pending', 'downloading', 'transcribing', 'saving', 'completed', 'cancelled']

const progressPercent = computed(() => {
  if (!props.progress) return 0

  if (props.progress.status === 'failed') return 100
  if (props.progress.status === 'completed') return 100
  if (props.progress.status === 'cancelled') return 100

  const stageIndex = stages.indexOf(props.progress.status)
  if (stageIndex === -1) return 0

  const baseProgress = (stageIndex / (stages.length - 1)) * 100

  // Add granular progress for transcribing stage
  if (props.progress.status === 'transcribing' && props.progress.stage_progress) {
    const { current_chunk, total_chunks } = props.progress.stage_progress
    if (current_chunk && total_chunks && total_chunks > 1) {
      const stageSize = 100 / (stages.length - 1)
      const chunkProgress = ((current_chunk - 1) / total_chunks) * stageSize
      return baseProgress + chunkProgress
    }
  }

  return baseProgress
})

const progressColor = computed(() => {
  if (!props.progress) return 'primary'
  if (props.progress.status === 'failed') return 'error'
  if (props.progress.status === 'completed') return 'success'
  if (props.progress.status === 'cancelled') return 'warning'
  return 'primary'
})
</script>
