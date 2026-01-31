import { createClient } from '@supabase/supabase-js'
import { cancelProcess } from '../../utils/process-tracker'

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const supabase = createClient(config.supabaseUrl, config.supabaseServiceKey)

  const body = await readBody(event)
  const { playlistId } = body

  if (!playlistId) {
    throw createError({
      statusCode: 400,
      message: 'Playlist ID is required'
    })
  }

  // Get all pending/active jobs for this playlist
  const { data: jobs, error: fetchError } = await supabase
    .from('jobs')
    .select('id, status')
    .eq('playlist_id', playlistId)
    .not('status', 'in', '("completed","failed","cancelled")')

  if (fetchError) {
    throw createError({
      statusCode: 500,
      message: `Failed to fetch jobs: ${fetchError.message}`
    })
  }

  if (!jobs || jobs.length === 0) {
    return { cancelled: 0 }
  }

  // Mark all jobs as cancelled and request cancellation
  const { error: updateError } = await supabase
    .from('jobs')
    .update({
      cancel_requested: true,
      status: 'cancelled',
      updated_at: new Date().toISOString()
    })
    .eq('playlist_id', playlistId)
    .not('status', 'in', '("completed","failed","cancelled")')

  if (updateError) {
    throw createError({
      statusCode: 500,
      message: `Failed to cancel jobs: ${updateError.message}`
    })
  }

  // Kill any running processes
  for (const job of jobs) {
    cancelProcess(job.id)
  }

  return {
    cancelled: jobs.length
  }
})
