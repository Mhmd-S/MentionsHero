import { createClient } from '@supabase/supabase-js'
import { cancelProcess } from '../../../utils/process-tracker'

export default defineEventHandler(async (event) => {
  const jobId = getRouterParam(event, 'id')

  if (!jobId) {
    throw createError({
      statusCode: 400,
      message: 'Job ID is required'
    })
  }

  const config = useRuntimeConfig()
  const supabase = createClient(config.supabaseUrl, config.supabaseServiceKey)

  // Get current job status
  const { data: job, error: fetchError } = await supabase
    .from('jobs')
    .select('status')
    .eq('id', jobId)
    .single()

  if (fetchError || !job) {
    throw createError({
      statusCode: 404,
      message: 'Job not found'
    })
  }

  // Check if job is in a terminal state
  const terminalStatuses = ['completed', 'failed', 'cancelled']
  if (terminalStatuses.includes(job.status)) {
    throw createError({
      statusCode: 400,
      message: `Cannot cancel job with status: ${job.status}`
    })
  }

  // Set cancel_requested flag in database
  const { error: updateError } = await supabase
    .from('jobs')
    .update({ cancel_requested: true })
    .eq('id', jobId)

  if (updateError) {
    throw createError({
      statusCode: 500,
      message: `Failed to request cancellation: ${updateError.message}`
    })
  }

  // Try to cancel the running process
  cancelProcess(jobId)

  return { success: true, message: 'Cancellation requested' }
})
