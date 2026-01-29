import { createClient } from '@supabase/supabase-js'

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id')
  const config = useRuntimeConfig()
  const supabase = createClient(config.supabaseUrl, config.supabaseServiceKey)

  const body = await readBody(event)
  const { name, parent_id } = body

  const updates: Record<string, unknown> = {
    updated_at: new Date().toISOString()
  }

  if (name !== undefined) {
    if (typeof name !== 'string' || name.trim().length === 0) {
      throw createError({
        statusCode: 400,
        message: 'Folder name cannot be empty'
      })
    }
    updates.name = name.trim()
  }

  if (parent_id !== undefined) {
    // Prevent moving a folder into itself or its descendants
    if (parent_id === id) {
      throw createError({
        statusCode: 400,
        message: 'Cannot move a folder into itself'
      })
    }
    updates.parent_id = parent_id
  }

  const { data, error } = await supabase
    .from('folders')
    .update(updates)
    .eq('id', id)
    .select()
    .single()

  if (error) {
    if (error.code === '23505') {
      throw createError({
        statusCode: 409,
        message: 'A folder with this name already exists in this location'
      })
    }
    throw createError({
      statusCode: 500,
      message: error.message
    })
  }

  return data
})
