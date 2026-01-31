import { createClient } from '@supabase/supabase-js'

interface SearchMatch {
  transcript_id: string
  transcript_name: string
  date: string | null
  context: string
  position: number
}

interface SearchResponse {
  query: string
  total_matches: number
  transcripts_with_matches: number
  matches: SearchMatch[]
}

export default defineEventHandler(async (event): Promise<SearchResponse> => {
  const config = useRuntimeConfig()
  const body = await readBody(event)

  const { query: searchQuery, context_chars = 200, folder_id: folderId, speakers } = body

  if (!searchQuery || typeof searchQuery !== 'string' || !searchQuery.trim()) {
    throw createError({ statusCode: 400, message: 'Query parameter is required' })
  }

  const speakersList = Array.isArray(speakers)
    ? speakers.filter((s): s is string => typeof s === 'string').map(s => s.trim()).filter(Boolean)
    : typeof speakers === 'string'
      ? speakers.split(',').map(s => s.trim()).filter(Boolean)
      : undefined

  // Try Python service first
  const pythonUrl = process.env.PYTHON_ANALYSIS_URL || 'http://localhost:8001'

  try {
    const response = await $fetch<SearchResponse>(`${pythonUrl}/analyze/search`, {
      method: 'POST',
      body: {
        query: searchQuery,
        context_chars,
        folder_id: folderId || null,
        speakers: speakersList?.length ? speakersList : null
      }
    })
    return response
  } catch (pythonError) {
    console.warn('Python analysis service unavailable, using fallback:', pythonError)
  }

  // Fallback: Direct database search
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
    return {
      query: searchQuery,
      total_matches: 0,
      transcripts_with_matches: 0,
      matches: []
    }
  }

  const matches: SearchMatch[] = []
  const transcriptIds = new Set<string>()

  const escapedQuery = searchQuery.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const regex = new RegExp(escapedQuery, 'gi')

  for (const t of transcripts) {
    if (!t.transcript) continue

    let match: RegExpExecArray | null
    while ((match = regex.exec(t.transcript)) !== null) {
      const start = Math.max(0, match.index - context_chars)
      const end = Math.min(t.transcript.length, match.index + match[0].length + context_chars)

      let context = t.transcript.slice(start, end)
      if (start > 0) context = '...' + context
      if (end < t.transcript.length) context = context + '...'

      transcriptIds.add(t.id)

      matches.push({
        transcript_id: t.id,
        transcript_name: t.name || '',
        date: t.created_at ? t.created_at.slice(0, 10) : null,
        context,
        position: match.index
      })

      // Limit matches per transcript
      if (matches.filter(m => m.transcript_id === t.id).length >= 10) {
        break
      }
    }
  }

  // Limit total matches
  const limitedMatches = matches.slice(0, 100)

  return {
    query: searchQuery,
    total_matches: matches.length,
    transcripts_with_matches: transcriptIds.size,
    matches: limitedMatches
  }
})
