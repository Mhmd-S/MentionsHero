import { createClient } from '@supabase/supabase-js'

interface NgramData {
  phrase: string
  count: number
  briefings_with_phrase: number
  total_briefings: number
  percentage: number
}

interface NgramsResponse {
  ngrams: NgramData[]
  n: number
  count: number
}

export default defineEventHandler(async (event): Promise<NgramsResponse> => {
  const config = useRuntimeConfig()
  const query = getQuery(event)
  const n = parseInt(query.n as string) || 2
  const minFrequency = parseInt(query.min_frequency as string) || 3
  const maxNgrams = parseInt(query.max_ngrams as string) || 200
  const folderId = query.folder_id as string | undefined
  const speakers = (query.speakers as string)?.split(',').map(s => s.trim()).filter(Boolean) || undefined

  if (n < 2 || n > 3) {
    throw createError({ statusCode: 400, message: 'n must be 2 or 3' })
  }

  // Try Python service first
  const pythonUrl = process.env.PYTHON_ANALYSIS_URL || 'http://localhost:8001'

  try {
    const response = await $fetch<NgramsResponse>(`${pythonUrl}/analyze/ngrams`, {
      method: 'POST',
      body: {
        n,
        min_frequency: minFrequency,
        max_ngrams: maxNgrams,
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
    return { ngrams: [], n, count: 0 }
  }

  const ngramCounts = new Map<string, number>()
  const ngramBriefingCounts = new Map<string, number>()
  let totalBriefings = 0

  for (const t of transcripts) {
    if (!t.transcript) continue

    totalBriefings++

    // Clean and tokenize - remove speaker labels like "Caroline:", "Reporter:", "SPEAKER_01:"
    const text = t.transcript
      .replace(/^\s*[A-Za-z]+:\s*\n?/gm, '') // Remove speaker labels (e.g., "Caroline:", "Reporter:")
      .replace(/^\s*SPEAKER_\d+:\s*\n?/gm, '') // Remove diarization labels
      .toLowerCase()

    const words = text.match(/\b[a-z]+\b/g) || []

    // Generate n-grams
    const uniqueNgrams = new Set<string>()

    for (let i = 0; i <= words.length - n; i++) {
      const ngram = words.slice(i, i + n).join(' ')
      ngramCounts.set(ngram, (ngramCounts.get(ngram) || 0) + 1)
      uniqueNgrams.add(ngram)
    }

    for (const ngram of uniqueNgrams) {
      ngramBriefingCounts.set(ngram, (ngramBriefingCounts.get(ngram) || 0) + 1)
    }
  }

  // Build results
  const ngrams: NgramData[] = []

  for (const [phrase, count] of ngramCounts) {
    if (count >= minFrequency) {
      const briefingCount = ngramBriefingCounts.get(phrase) || 0
      const percentage = totalBriefings > 0 ? (briefingCount / totalBriefings) * 100 : 0

      ngrams.push({
        phrase,
        count,
        briefings_with_phrase: briefingCount,
        total_briefings: totalBriefings,
        percentage: Math.round(percentage * 100) / 100
      })
    }
  }

  // Sort by count descending and limit
  ngrams.sort((a, b) => b.count - a.count)
  const limitedNgrams = ngrams.slice(0, maxNgrams)

  return { ngrams: limitedNgrams, n, count: limitedNgrams.length }
})
