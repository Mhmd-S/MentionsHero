import { ref, watch, computed, onUnmounted, type Ref } from 'vue'

export interface StageProgress {
  current_chunk?: number
  total_chunks?: number
  substep?: string
  substep_detail?: string
}

export type JobStatus = 'pending' | 'downloading' | 'transcribing' | 'cleaning' | 'saving' | 'completed' | 'failed' | 'cancelled'

export interface JobProgress {
  id: string
  youtube_url: string
  status: JobStatus
  stage_progress: StageProgress
  error_message: string | null
  transcript_id: string | null
  created_at: string
  updated_at: string
}

export function useJobProgress(jobId: Ref<string | null>) {
  const progress = ref<JobProgress | null>(null)
  const error = ref<string | null>(null)
  const eventSource = ref<EventSource | null>(null)

  const connect = () => {
    if (!jobId.value) return

    // EventSource is browser-only
    if (import.meta.server) return

    // Close existing connection
    if (eventSource.value) {
      eventSource.value.close()
    }

    const es = new EventSource(`/api/jobs/${jobId.value}/stream`)
    eventSource.value = es

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.error) {
          error.value = data.error
          es.close()
        } else {
          progress.value = data as JobProgress
          error.value = null

          // Close connection when job is done
          if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
            es.close()
          }
        }
      } catch (e) {
        console.error('Failed to parse SSE data:', e)
      }
    }

    es.onerror = () => {
      error.value = 'Connection lost'
      es.close()
    }
  }

  const disconnect = () => {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
  }

  // Watch for jobId changes
  watch(jobId, (newId) => {
    if (newId) {
      connect()
    } else {
      disconnect()
      progress.value = null
    }
  }, { immediate: true })

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect()
  })

  const isActive = computed(() => {
    return progress.value && !['completed', 'failed', 'cancelled'].includes(progress.value.status)
  })

  const statusLabel = computed(() => {
    if (!progress.value) return ''

    const labels: Record<JobStatus, string> = {
      pending: 'Starting...',
      downloading: 'Downloading audio...',
      transcribing: 'Transcribing...',
      cleaning: 'Cleaning up transcript...',
      saving: 'Saving transcript...',
      completed: 'Completed',
      failed: 'Failed',
      cancelled: 'Cancelled'
    }

    return labels[progress.value.status] || progress.value.status
  })

  const substepLabel = computed(() => {
    return progress.value?.stage_progress?.substep || null
  })

  const substepDetail = computed(() => {
    return progress.value?.stage_progress?.substep_detail || null
  })

  const chunkInfo = computed(() => {
    if (!progress.value?.stage_progress) return null
    const { current_chunk, total_chunks } = progress.value.stage_progress
    if (current_chunk && total_chunks && total_chunks > 1) {
      return `Chunk ${current_chunk} of ${total_chunks}`
    }
    return null
  })

  return {
    progress,
    error,
    isActive,
    statusLabel,
    chunkInfo,
    substepLabel,
    substepDetail,
    connect,
    disconnect
  }
}
