import { getJob } from '../../../utils/job-progress'
import type { Job } from '../../../utils/job-progress'

export default defineEventHandler(async (event) => {
  const jobId = getRouterParam(event, 'id')

  if (!jobId) {
    throw createError({
      statusCode: 400,
      message: 'Job ID is required'
    })
  }

  // Set SSE headers
  setHeader(event, 'Content-Type', 'text/event-stream')
  setHeader(event, 'Cache-Control', 'no-cache')
  setHeader(event, 'Connection', 'keep-alive')

  const sendEvent = (data: Job | { error: string }) => {
    return `data: ${JSON.stringify(data)}\n\n`
  }

  // Return an async generator that polls the database
  return new ReadableStream({
    async start(controller) {
      let lastStatus = ''
      let lastProgress = ''
      let isClosed = false

      const closeController = () => {
        if (!isClosed) {
          isClosed = true
          controller.close()
        }
      }

      const poll = async () => {
        if (isClosed) return false

        try {
          const job = await getJob(jobId)

          if (!job) {
            controller.enqueue(sendEvent({ error: 'Job not found' }))
            closeController()
            return false
          }

          // Only send update if something changed
          const currentProgress = JSON.stringify(job.stage_progress)
          if (job.status !== lastStatus || currentProgress !== lastProgress) {
            lastStatus = job.status
            lastProgress = currentProgress
            controller.enqueue(sendEvent(job))
          }

          // Stop polling if job is completed, failed, or cancelled
          if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
            closeController()
            return false
          }

          return true
        } catch (err) {
          console.error('SSE poll error:', err)
          controller.enqueue(sendEvent({ error: 'Failed to fetch job status' }))
          closeController()
          return false
        }
      }

      // Initial poll
      const shouldContinue = await poll()
      if (!shouldContinue) return

      // Poll every second
      const interval = setInterval(async () => {
        const shouldContinue = await poll()
        if (!shouldContinue) {
          clearInterval(interval)
        }
      }, 1000)

      // Cleanup on connection close
      event.node.req.on('close', () => {
        clearInterval(interval)
        closeController()
      })
    }
  })
})
