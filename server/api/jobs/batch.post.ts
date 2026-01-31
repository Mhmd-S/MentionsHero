import { createClient } from '@supabase/supabase-js'
import { updateJobProgress } from '../../utils/job-progress'

interface VideoInput {
  url: string
  title?: string
}

interface BatchJobsBody {
  videos: VideoInput[]
  folderId?: string | null
  playlistId?: string | null
  playlistName?: string | null
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const supabase = createClient(config.supabaseUrl, config.supabaseServiceKey)

  const body = await readBody<BatchJobsBody>(event)
  const { videos, folderId, playlistId, playlistName } = body

  if (!videos || videos.length === 0) {
    throw createError({
      statusCode: 400,
      message: 'At least one video is required'
    })
  }

  if (videos.length > 50) {
    throw createError({
      statusCode: 400,
      message: 'Maximum 50 videos per batch'
    })
  }

  const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+/

  // Validate all URLs
  for (const video of videos) {
    if (!video.url || !youtubeRegex.test(video.url)) {
      throw createError({
        statusCode: 400,
        message: `Invalid YouTube URL: ${video.url}`
      })
    }
  }

  const jobIds: string[] = []

  // Create all jobs in the database
  for (let i = 0; i < videos.length; i++) {
    const video = videos[i]!

    const { data: job, error } = await supabase
      .from('jobs')
      .insert({
        youtube_url: video.url,
        status: 'pending',
        stage_progress: {},
        playlist_id: playlistId || null,
        playlist_name: playlistName || null,
        playlist_index: playlistId ? i : null,
        video_title: video.title || null
      })
      .select()
      .single()

    if (error) {
      console.error(`Failed to create job for ${video.url}:`, error.message)
      continue
    }

    jobIds.push(job.id)
  }

  // Start processing jobs in background (limited concurrency)
  const MAX_CONCURRENT = 2

  async function processJob(jobId: string, video: VideoInput) {
    try {
      await $fetch('/api/download', {
        method: 'POST',
        body: {
          url: video.url,
          jobId,
          folderId,
          videoTitle: video.title
        }
      })
    } catch (err: any) {
      await updateJobProgress(jobId, 'failed', undefined, {
        error_message: err.data?.message || 'Processing failed'
      })
    }
  }

  // Process jobs with limited concurrency
  ;(async () => {
    for (let i = 0; i < jobIds.length; i += MAX_CONCURRENT) {
      const batch = jobIds.slice(i, i + MAX_CONCURRENT)
      const batchVideos = videos.slice(i, i + MAX_CONCURRENT)

      await Promise.all(
        batch.map((jobId, idx) => processJob(jobId, batchVideos[idx]!))
      )
    }
  })()

  return {
    jobIds,
    total: jobIds.length
  }
})
