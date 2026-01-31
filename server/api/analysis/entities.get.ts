interface EntityData {
  entity: string
  type: string
  count: number
  briefings_with_entity: number
  total_briefings: number
  percentage: number
}

interface EntitiesResponse {
  entities: EntityData[]
  count: number
}

export default defineEventHandler(async (event): Promise<EntitiesResponse> => {
  const query = getQuery(event)
  const entityTypes = query.types
    ? (query.types as string).split(',')
    : null
  const folderId = query.folder_id as string | undefined
  const speakers = (query.speakers as string)?.split(',').map(s => s.trim()).filter(Boolean) || undefined

  // Entity extraction requires spaCy - only available via Python service
  const pythonUrl = process.env.PYTHON_ANALYSIS_URL || 'http://localhost:8001'

  try {
    const response = await $fetch<EntitiesResponse>(`${pythonUrl}/analyze/entities`, {
      method: 'POST',
      body: {
        entity_types: entityTypes,
        folder_id: folderId || null,
        speakers: speakers || null
      }
    })
    return response
  } catch (pythonError) {
    console.warn('Python analysis service unavailable:', pythonError)
    throw createError({
      statusCode: 503,
      message: 'Entity extraction requires the Python analysis service. Please ensure it is running.'
    })
  }
})
