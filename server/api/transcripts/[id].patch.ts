import { createClient } from '@supabase/supabase-js'

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id')
  const config = useRuntimeConfig()
  const supabase = createClient(config.supabaseUrl, config.supabaseServiceKey)

  const body = await readBody(event)
  const { name, folder_id } = body

  const updates: Record<string, unknown> = {}

  if (name !== undefined) {
    if (typeof name !== 'string' || name.trim().length === 0) {
      throw createError({
        statusCode: 400,
        message: 'Transcript name cannot be empty'
      })
    }
    updates.name = name.trim()
  }

  if (folder_id !== undefined) {
    updates.folder_id = folder_id
  }

  if (Object.keys(updates).length === 0) {
    throw createError({
      statusCode: 400,
      message: 'No valid fields to update'
    })
  }

  const { data, error } = await supabase
    .from('transcripts')
    .update(updates)
    .eq('id', id)
    .select()
    .single()

  if (error) {
    throw createError({
      statusCode: 500,
      message: error.message
    })
  }

  return data
})
