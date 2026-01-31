import { createClient } from '@supabase/supabase-js'

interface TrendDataPoint {
  date: string | null
  count: number
  transcript_name: string
}

interface TrendsResponse {
  trends: Record<string, TrendDataPoint[]>
  terms: string[]
}

export default defineEventHandler(async (event): Promise<TrendsResponse> => {
  const config = useRuntimeConfig()
  const body = await readBody(event)

  const { terms, folder_id: folderId, speakers } = body

  if (!terms || !Array.isArray(terms) || terms.length === 0) {
    throw createError({ statusCode: 400, message: 'Terms array is required' })
  }

  if (terms.length > 10) {
    throw createError({ statusCode: 400, message: 'Maximum 10 terms allowed' })
  }

  const speakersList = Array.isArray(speakers)
    ? speakers.filter((s): s is string => typeof s === 'string').map(s => s.trim()).filter(Boolean)
    : typeof speakers === 'string'
      ? speakers.split(',').map(s => s.trim()).filter(Boolean)
      : undefined

  // Try Python service first
  const pythonUrl = process.env.PYTHON_ANALYSIS_URL || 'http://localhost:8001'

  try {
    const response = await $fetch<TrendsResponse>(`${pythonUrl}/analyze/temporal-trends`, {
      method: 'POST',
      body: { terms, folder_id: folderId || null, speakers: speakersList?.length ? speakersList : null }
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
    .order('created_at', { ascending: true })

  if (folderId) {
    dbQuery = dbQuery.eq('folder_id', folderId)
  }

  const { data: transcripts, error } = await dbQuery

  if (error) {
    throw createError({ statusCode: 500, message: error.message })
  }

  if (!transcripts || transcripts.length === 0) {
    const emptyTrends: Record<string, TrendDataPoint[]> = {}
    for (const term of terms) {
      emptyTrends[term] = []
    }
    return { trends: emptyTrends, terms }
  }

  const trends: Record<string, TrendDataPoint[]> = {}
  for (const term of terms) {
    trends[term] = []
  }

  for (const t of transcripts) {
    if (!t.transcript) continue

    const textLower = t.transcript.toLowerCase()
    const date = t.created_at ? t.created_at.slice(0, 10) : null

    for (const term of terms) {
      const escapedTerm = term.toLowerCase().replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      const regex = new RegExp(escapedTerm, 'g')
      const matches = textLower.match(regex)
      const count = matches ? matches.length : 0

      trends[term].push({
        date,
        count,
        transcript_name: t.name || ''
      })
    }
  }

  return { trends, terms }
})
