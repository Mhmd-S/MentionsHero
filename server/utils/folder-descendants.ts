import type { SupabaseClient } from '@supabase/supabase-js'

interface FolderRow {
  id: string
  name: string
  parent_id: string | null
}

/**
 * Return folder_id plus all descendant folder IDs (for use in transcript scope).
 * Fetches folders from Supabase and builds the set in memory.
 */
export async function getFolderIdsInTree(
  supabase: SupabaseClient,
  folderId: string
): Promise<string[]> {
  const { data: folders, error } = await supabase
    .from('folders')
    .select('id, name, parent_id')
    .order('name', { ascending: true })

  if (error) {
    throw createError({ statusCode: 500, message: error.message })
  }

  const list = (folders || []) as FolderRow[]
  const byParent = new Map<string | null, string[]>()
  for (const f of list) {
    const pid = f.parent_id ?? null
    if (!byParent.has(pid)) byParent.set(pid, [])
    byParent.get(pid)!.push(f.id)
  }

  const result: string[] = [folderId]
  const stack: string[] = [folderId]
  const seen = new Set<string>([folderId])

  while (stack.length > 0) {
    const current = stack.pop()!
    const children = byParent.get(current) ?? []
    for (const childId of children) {
      if (!seen.has(childId)) {
        seen.add(childId)
        result.push(childId)
        stack.push(childId)
      }
    }
  }

  return result
}
