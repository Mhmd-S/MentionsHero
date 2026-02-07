export interface Folder {
  id: string
  name: string
  parent_id: string | null
  created_at: string
  updated_at: string
}

export interface Transcript {
  id: string
  name: string | null
  folder_id: string | null
  youtube_url: string
  created_at: string
}

export function useFileTree() {
  const folders = useState<Folder[]>('file-tree-folders', () => [])
  const transcripts = useState<Transcript[]>('file-tree-transcripts', () => [])
  const loading = useState('file-tree-loading', () => false)
  const dropTargetId = useState<string | null>('file-tree-drop-target', () => null)

  async function fetchFolders() {
    try {
      const data = await $fetch<Folder[]>('/api/folders')
      folders.value = data
    } catch (err) {
      console.error('Failed to fetch folders:', err)
      folders.value = []
    }
  }

  async function fetchTranscripts() {
    const data = await $fetch<Transcript[]>('/api/transcripts')
    transcripts.value = data
  }

  async function fetchAll() {
    loading.value = true
    try {
      await Promise.all([fetchFolders(), fetchTranscripts()])
    } finally {
      loading.value = false
    }
  }

  async function createFolder(parentId: string | null = null) {
    const name = generateUniqueFolderName(parentId)
    const data = await $fetch<Folder>('/api/folders', {
      method: 'POST',
      body: { name, parent_id: parentId }
    })
    folders.value = [...folders.value, data]
    return data
  }

  function generateUniqueFolderName(parentId: string | null): string {
    const siblingFolders = folders.value.filter(f => f.parent_id === parentId)
    const baseName = 'New Folder'
    let name = baseName
    let counter = 1

    while (siblingFolders.some(f => f.name === name)) {
      name = `${baseName} ${counter}`
      counter++
    }

    return name
  }

  async function renameFolder(id: string, name: string) {
    const data = await $fetch<Folder>(`/api/folders/${id}`, {
      method: 'PATCH',
      body: { name }
    })
    folders.value = folders.value.map(f => f.id === id ? data : f)
    return data
  }

  async function moveFolder(id: string, parentId: string | null) {
    const folder = folders.value.find(f => f.id === id)
    if (!folder || folder.parent_id === parentId) return

    // Prevent moving to own descendants
    if (parentId && isDescendant(id, parentId)) {
      console.warn('Cannot move folder into its own descendant')
      return
    }

    const data = await $fetch<Folder>(`/api/folders/${id}`, {
      method: 'PATCH',
      body: { parent_id: parentId }
    })
    folders.value = folders.value.map(f => f.id === id ? data : f)
    return data
  }

  function isDescendant(folderId: string, potentialDescendantId: string): boolean {
    let current = folders.value.find(f => f.id === potentialDescendantId)
    while (current) {
      if (current.parent_id === folderId) return true
      current = folders.value.find(f => f.id === current!.parent_id)
    }
    return false
  }

  async function deleteFolder(id: string) {
    await $fetch(`/api/folders/${id}`, { method: 'DELETE' })

    // Update local state: move children to parent
    const deletedFolder = folders.value.find(f => f.id === id)
    const parentId = deletedFolder?.parent_id || null

    folders.value = folders.value
      .filter(f => f.id !== id)
      .map(f => f.parent_id === id ? { ...f, parent_id: parentId } : f)

    transcripts.value = transcripts.value.map(t =>
      t.folder_id === id ? { ...t, folder_id: parentId } : t
    )
  }

  async function deleteTranscript(id: string) {
    await $fetch(`/api/transcripts/${id}`, { method: 'DELETE' })
    transcripts.value = transcripts.value.filter(t => t.id !== id)
  }

  async function renameTranscript(id: string, name: string) {
    const data = await $fetch<Transcript>(`/api/transcripts/${id}`, {
      method: 'PATCH',
      body: { name }
    })
    transcripts.value = transcripts.value.map(t => t.id === id ? { ...t, ...data } : t)
    return data
  }

  async function moveTranscript(id: string, folderId: string | null) {
    const transcript = transcripts.value.find(t => t.id === id)
    if (!transcript || transcript.folder_id === folderId) return

    const data = await $fetch<Transcript>(`/api/transcripts/${id}`, {
      method: 'PATCH',
      body: { folder_id: folderId }
    })
    transcripts.value = transcripts.value.map(t => t.id === id ? { ...t, ...data } : t)
    return data
  }

  function setDropTarget(id: string | null) {
    dropTargetId.value = id
  }

  return {
    folders,
    transcripts,
    loading,
    dropTargetId,
    fetchAll,
    fetchFolders,
    fetchTranscripts,
    createFolder,
    renameFolder,
    moveFolder,
    deleteFolder,
    deleteTranscript,
    renameTranscript,
    moveTranscript,
    setDropTarget
  }
}
