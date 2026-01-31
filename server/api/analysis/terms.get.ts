import { createClient } from '@supabase/supabase-js'

interface TermData {
  term: string
  count: number
  briefings_with_term: number
  total_briefings: number
  percentage: number
}

interface TermsResponse {
  terms: TermData[]
  count: number
}

export default defineEventHandler(async (event): Promise<TermsResponse> => {
  const config = useRuntimeConfig()
  const query = getQuery(event)
  const minFrequency = parseInt(query.min_frequency as string) || 5
  const maxTerms = parseInt(query.max_terms as string) || 500
  const folderId = query.folder_id as string | undefined
  const speakers = (query.speakers as string)?.split(',').map(s => s.trim()).filter(Boolean) || undefined

  // Try Python service first
  const pythonUrl = process.env.PYTHON_ANALYSIS_URL || 'http://localhost:8001'

  try {
    const response = await $fetch<TermsResponse>(`${pythonUrl}/analyze/all-terms`, {
      method: 'POST',
      body: {
        min_frequency: minFrequency,
        max_terms: maxTerms,
        folder_id: folderId || null,
        speakers: speakers || null
      }
    })
    return response
  } catch (pythonError) {
    console.warn('Python analysis service unavailable, using fallback:', pythonError)
  }

  // Fallback: Direct database analysis
  const supabase = createClient(config.supabaseUrl, config.supabaseServiceKey)

  let dbQuery = supabase
    .from('transcripts')
    .select('id, transcript, name, created_at, folder_id')

  if (folderId) {
    dbQuery = dbQuery.eq('folder_id', folderId)
  }

  const { data: transcripts, error } = await dbQuery

  if (error) {
    throw createError({ statusCode: 500, message: error.message })
  }

  if (!transcripts || transcripts.length === 0) {
    return { terms: [], count: 0 }
  }

  // Common stop words to exclude
  const stopWords = new Set([
    'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
    'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
    'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
    'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
    'that', 'this', 'these', 'those', 'it', 'its', 'i', 'you', 'he',
    'she', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your',
    'his', 'our', 'their', 'what', 'which', 'who', 'whom', 'whose',
    'when', 'where', 'why', 'how', 'all', 'each', 'every', 'both',
    'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
    'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'also',
    'now', 'here', 'there', 'then', 'if', 'because', 'about', 'into',
    'through', 'during', 'before', 'after', 'above', 'below', 'up',
    'down', 'out', 'off', 'over', 'under', 'again', 'further', 'once',
    'any', 'being', 'going', 'get', 'got', 'know', 'think', 'want',
    'said', 'say', 'says', 'like', 'well', 'back', 'one', 'two',
    'yeah', 'yes', 'okay', 'right', 'really', 'very', 'much', 'many'
  ])

  const wordCounts = new Map<string, number>()
  const wordBriefingCounts = new Map<string, number>()
  let totalBriefings = 0

  for (const t of transcripts) {
    if (!t.transcript) continue

    totalBriefings++

    // Clean and tokenize - remove speaker labels like "Caroline:", "Reporter:", "SPEAKER_01:"
    const text = t.transcript
      .replace(/^\s*[A-Za-z]+:\s*\n?/gm, '') // Remove speaker labels (e.g., "Caroline:", "Reporter:")
      .replace(/^\s*SPEAKER_\d+:\s*\n?/gm, '') // Remove diarization labels
      .toLowerCase()

    const words = text.match(/\b[a-z]{3,}\b/g) || []
    const uniqueWords = new Set<string>()

    for (const word of words) {
      if (!stopWords.has(word)) {
        wordCounts.set(word, (wordCounts.get(word) || 0) + 1)
        uniqueWords.add(word)
      }
    }

    for (const word of uniqueWords) {
      wordBriefingCounts.set(word, (wordBriefingCounts.get(word) || 0) + 1)
    }
  }

  // Build results
  const terms: TermData[] = []

  for (const [word, count] of wordCounts) {
    if (count >= minFrequency) {
      const briefingCount = wordBriefingCounts.get(word) || 0
      const percentage = totalBriefings > 0 ? (briefingCount / totalBriefings) * 100 : 0

      terms.push({
        term: word,
        count,
        briefings_with_term: briefingCount,
        total_briefings: totalBriefings,
        percentage: Math.round(percentage * 100) / 100
      })
    }
  }

  // Sort by count descending and limit
  terms.sort((a, b) => b.count - a.count)
  const limitedTerms = terms.slice(0, maxTerms)

  return { terms: limitedTerms, count: limitedTerms.length }
})
