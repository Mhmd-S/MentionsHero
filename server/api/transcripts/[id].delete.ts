import { createClient } from '@supabase/supabase-js'

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id')
  const config = useRuntimeConfig()
  const supabase = createClient(config.supabaseUrl, config.supabaseServiceKey)

  const { error } = await supabase
    .from('transcripts')
    .delete()
    .eq('id', id)

  if (error) {
    throw createError({
      statusCode: 500,
      message: error.message
    })
  }

  return { success: true }
})
