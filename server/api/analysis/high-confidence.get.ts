interface HighConfidencePhrase {
  phrase: string
  count: number
  briefings_with_phrase: number
  total_briefings: number
  percentage: number
}

interface HighConfidenceResponse {
  phrases: HighConfidencePhrase[]
  min_percentage: number
  count: number
}

export default defineEventHandler(async (event): Promise<HighConfidenceResponse> => {
  const query = getQuery(event)
  const minPercentage = parseFloat(query.min_percentage as string) || 90.0
  const folderId = query.folder_id as string | undefined
  const speakers = (query.speakers as string)?.split(',').map(s => s.trim()).filter(Boolean) || undefined

  if (minPercentage < 50 || minPercentage > 100) {
    throw createError({ statusCode: 400, message: 'min_percentage must be between 50 and 100' })
  }

  // Try Python service first (more accurate NLP)
  const pythonUrl = process.env.PYTHON_ANALYSIS_URL || 'http://localhost:8001'

  try {
    const response = await $fetch<HighConfidenceResponse>(`${pythonUrl}/analyze/high-confidence`, {
      method: 'POST',
      body: {
        min_percentage: minPercentage,
        folder_id: folderId || null,
        speakers: speakers || null
      }
    })
    return response
  } catch (pythonError) {
    console.warn('Python analysis service unavailable, using fallback:', pythonError)
  }

  // Fallback: Use the ngrams endpoint and filter
  const speakersQuery = speakers?.length ? { speakers: speakers.join(',') } : {}
  const bigramsResponse = await $fetch<{ ngrams: HighConfidencePhrase[] }>('/api/analysis/ngrams', {
    query: { n: 2, min_frequency: 1, max_ngrams: 500, folder_id: folderId, ...speakersQuery }
  })

  const trigramsResponse = await $fetch<{ ngrams: HighConfidencePhrase[] }>('/api/analysis/ngrams', {
    query: { n: 3, min_frequency: 1, max_ngrams: 500, folder_id: folderId, ...speakersQuery }
  })

  const allPhrases = [
    ...bigramsResponse.ngrams.map(ng => ({
      phrase: ng.phrase,
      count: ng.count,
      briefings_with_phrase: ng.briefings_with_phrase,
      total_briefings: ng.total_briefings,
      percentage: ng.percentage
    })),
    ...trigramsResponse.ngrams.map(ng => ({
      phrase: ng.phrase,
      count: ng.count,
      briefings_with_phrase: ng.briefings_with_phrase,
      total_briefings: ng.total_briefings,
      percentage: ng.percentage
    }))
  ]

  const highConfidence = allPhrases
    .filter(p => p.percentage >= minPercentage)
    .sort((a, b) => b.percentage - a.percentage || b.count - a.count)

  return {
    phrases: highConfidence,
    min_percentage: minPercentage,
    count: highConfidence.length
  }
})
