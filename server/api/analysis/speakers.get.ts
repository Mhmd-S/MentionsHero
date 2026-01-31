interface SpeakerInfo {
  name: string
  segment_count: number
  briefings: number
}

interface SpeakersResponse {
  speakers: SpeakerInfo[]
}

export default defineEventHandler(async (event): Promise<SpeakersResponse> => {
  const query = getQuery(event)
  const folderId = query.folder_id as string | undefined

  const pythonUrl = process.env.PYTHON_ANALYSIS_URL || 'http://localhost:8001'

  try {
    const response = await $fetch<SpeakersResponse>(`${pythonUrl}/analyze/speakers`, {
      method: 'GET',
      query: folderId ? { folder_id: folderId } : undefined
    })
    return response
  } catch (pythonError) {
    console.warn('Python analysis service unavailable for speakers:', pythonError)
    return { speakers: [] }
  }
})
