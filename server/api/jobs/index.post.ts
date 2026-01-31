import { createJob, updateJobProgress } from '../../utils/job-progress'

export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const { url, folderId, videoTitle } = body

  if (!url) {
    throw createError({
      statusCode: 400,
      message: 'YouTube URL is required'
    })
  }

  const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+/
  if (!youtubeRegex.test(url)) {
    throw createError({
      statusCode: 400,
      message: 'Invalid YouTube URL'
    })
  }

  // Create job in database
  const job = await createJob(url, { videoTitle })

  // Trigger processing in background (fire and forget)
  // The download endpoint will handle the actual processing
  $fetch('/api/download', {
    method: 'POST',
    body: { url, jobId: job.id, folderId, videoTitle }
  }).catch(async (err) => {
    // Update job status to failed if processing fails
    await updateJobProgress(job.id, 'failed', undefined, {
      error_message: err.data?.message || 'Processing failed'
    })
  })

  return {
    jobId: job.id,
    status: job.status
  }
})
