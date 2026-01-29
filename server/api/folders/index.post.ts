import { createClient } from '@supabase/supabase-js'

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const supabase = createClient(config.supabaseUrl, config.supabaseServiceKey)

  const body = await readBody(event)
  const { name, parent_id } = body

  if (!name || typeof name !== 'string' || name.trim().length === 0) {
    throw createError({
      statusCode: 400,
      message: 'Folder name is required'
    })
  }

  const { data, error } = await supabase
    .from('folders')
    .insert({
      name: name.trim(),
      parent_id: parent_id || null
    })
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
