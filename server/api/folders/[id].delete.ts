import { createClient } from '@supabase/supabase-js'

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id')
  const config = useRuntimeConfig()
  const supabase = createClient(config.supabaseUrl, config.supabaseServiceKey)

  // Get the folder to find its parent
  const { data: folder, error: fetchError } = await supabase
    .from('folders')
    .select('parent_id')
    .eq('id', id)
    .single()

  if (fetchError) {
    throw createError({
      statusCode: 404,
      message: 'Folder not found'
    })
  }

  const parentId = folder.parent_id

  // Move all child folders to the parent
  const { error: updateFoldersError } = await supabase
    .from('folders')
    .update({ parent_id: parentId, updated_at: new Date().toISOString() })
    .eq('parent_id', id)

  if (updateFoldersError) {
    throw createError({
      statusCode: 500,
      message: 'Failed to move child folders: ' + updateFoldersError.message
    })
  }

  // Move all transcripts in this folder to the parent
  const { error: updateTranscriptsError } = await supabase
    .from('transcripts')
    .update({ folder_id: parentId })
    .eq('folder_id', id)

  if (updateTranscriptsError) {
    throw createError({
      statusCode: 500,
      message: 'Failed to move transcripts: ' + updateTranscriptsError.message
    })
  }

  // Delete the folder
  const { error: deleteError } = await supabase
    .from('folders')
    .delete()
    .eq('id', id)

  if (deleteError) {
    throw createError({
      statusCode: 500,
      message: deleteError.message
    })
  }

  return { success: true }
})
