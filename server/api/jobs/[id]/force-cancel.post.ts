import { createClient } from '@supabase/supabase-js'

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

  // Force update job to cancelled status regardless of current state
  const { error } = await supabase
    .from('jobs')
    .update({
      status: 'cancelled',
      cancel_requested: true,
      updated_at: new Date().toISOString()
    })
    .eq('id', jobId)

  if (error) {
    throw createError({
      statusCode: 500,
      message: `Failed to force cancel job: ${error.message}`
    })
  }

  return { success: true, message: 'Job force cancelled' }
})
