import { createClient } from '@supabase/supabase-js'
import { getFolderIdsInTree } from '../../../utils/folder-descendants'

interface TermFrequencyResult {
  term: string
  total_mentions: number
  briefings_with_term: number
  total_briefings: number
  percentage: number
  trend: string
  mentions_by_date: Array<{
    date: string | null
    name: string
    count: number
  }>
}

export default defineEventHandler(async (event): Promise<TermFrequencyResult> => {
  const config = useRuntimeConfig()
  const term = getRouterParam(event, 'term')
  const query = getQuery(event)
  const caseSensitive = query.case_sensitive === 'true'
  const folderId = query.folder_id as string | undefined
  const speakers = (query.speakers as string)?.split(',').map(s => s.trim()).filter(Boolean) || undefined

  if (!term) {
    throw createError({ statusCode: 400, message: 'Term parameter is required' })
  }

  const decodedTerm = decodeURIComponent(term)

  // Try Python service first
  const pythonUrl = process.env.PYTHON_ANALYSIS_URL || 'http://localhost:8001'

  try {
    const response = await $fetch<TermFrequencyResult>(`${pythonUrl}/analyze/term-frequency`, {
      method: 'POST',
      body: {
        term: decodedTerm,
        case_sensitive: caseSensitive,
        folder_id: folderId || null,
        speakers: speakers || null
      }
    })
    return response
  } catch (pythonError) {
    // Fallback to direct database analysis if Python service unavailable
    console.warn('Python analysis service unavailable, using fallback:', pythonError)
  }

  // Fallback: Direct Supabase analysis
  const supabase = createClient(config.supabaseUrl, config.supabaseServiceKey)

  let dbQuery = supabase
    .from('transcripts')
    .select('id, transcript, name, created_at, folder_id')

  if (folderId) {
    const folderIds = await getFolderIdsInTree(supabase, folderId)
    dbQuery = dbQuery.in('folder_id', folderIds)
  }

  const { data: transcripts, error } = await dbQuery

  if (error) {
    throw createError({ statusCode: 500, message: error.message })
  }

  if (!transcripts || transcripts.length === 0) {
    return {
      term: decodedTerm,
      total_mentions: 0,
      briefings_with_term: 0,
      total_briefings: 0,
      percentage: 0,
      trend: 'stable',
      mentions_by_date: []
    }
  }

  // Helper to clean transcript text (remove speaker labels)
  function cleanTranscript(text: string): string {
    return text
      .replace(/^\s*[A-Za-z]+:\s*\n?/gm, '') // Remove speaker labels (e.g., "Caroline:", "Reporter:")
      .replace(/^\s*SPEAKER_\d+:\s*\n?/gm, '') // Remove diarization labels
  }

  function filterTranscriptBySpeakers(transcript: string, speakerList: string[]): string {
    if (!speakerList.length) return transcript

    const speakerLower = speakerList.map(s => s.toLowerCase())
    const lines = transcript.split('\n')
    const speakerPattern = /^([A-Z][a-zA-Z'-]*(?:\s+[A-Z][a-zA-Z'-]*)?|SPEAKER_\d+):\s*(.*)$/

    let currentSpeaker: string | null = null
    let currentContent: string[] = []
    const segments: Array<{ speaker: string; content: string }> = []

    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed) continue

      const match = speakerPattern.exec(trimmed)
      if (match) {
        if (currentSpeaker && currentContent.length > 0) {
          segments.push({ speaker: currentSpeaker, content: currentContent.join(' ').trim() })
        }
        currentSpeaker = match[1]
        currentContent = match[2] ? [match[2]] : []
        continue
      }

      if (currentSpeaker) {
        currentContent.push(trimmed)
      }
    }

    if (currentSpeaker && currentContent.length > 0) {
      segments.push({ speaker: currentSpeaker, content: currentContent.join(' ').trim() })
    }

    const matchesSpeaker = (segmentSpeaker: string) => {
      const segLower = segmentSpeaker.toLowerCase()
      return speakerLower.some(sl => segLower === sl || segLower.startsWith(sl) || segLower.includes(sl))
    }

    return segments
      .filter(segment => matchesSpeaker(segment.speaker))
      .map(segment => segment.content)
      .filter(Boolean)
      .join(' ')
      .trim()
  }

  function escapeRegExp(value: string): string {
    return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  }

  // Simple term frequency calculation
  let totalMentions = 0
  let briefingsWithTerm = 0
  const mentionsByDate: Array<{ date: string | null; name: string; count: number }> = []

  const searchTerm = caseSensitive ? decodedTerm : decodedTerm.toLowerCase()
  const regex = new RegExp(escapeRegExp(searchTerm), 'g')

  for (const t of transcripts) {
    if (!t.transcript) continue

    const text = speakers?.length
      ? filterTranscriptBySpeakers(t.transcript, speakers)
      : t.transcript

    if (!text) continue

    // Clean the transcript to remove speaker labels before counting
    const cleanedText = cleanTranscript(text)
    const normalizedText = caseSensitive ? cleanedText : cleanedText.toLowerCase()
    const matches = normalizedText.match(regex)
    const count = matches ? matches.length : 0

    if (count > 0) {
      briefingsWithTerm++
      totalMentions += count
      mentionsByDate.push({
        date: t.created_at ? t.created_at.slice(0, 10) : null,
        name: t.name || '',
        count
      })
    }
  }

  const totalBriefings = transcripts.filter(t => t.transcript).length
  const percentage = totalBriefings > 0 ? (briefingsWithTerm / totalBriefings) * 100 : 0

  // Simple trend calculation
  let trend = 'stable'
  if (mentionsByDate.length >= 4) {
    const mid = Math.floor(mentionsByDate.length / 2)
    const firstHalfAvg = mentionsByDate.slice(0, mid).reduce((sum, m) => sum + m.count, 0) / mid
    const secondHalfAvg = mentionsByDate.slice(mid).reduce((sum, m) => sum + m.count, 0) / (mentionsByDate.length - mid)

    if (secondHalfAvg > firstHalfAvg * 1.2) trend = 'increasing'
    else if (secondHalfAvg < firstHalfAvg * 0.8) trend = 'decreasing'
  }

  return {
    term: decodedTerm,
    total_mentions: totalMentions,
    briefings_with_term: briefingsWithTerm,
    total_briefings: totalBriefings,
    percentage: Math.round(percentage * 100) / 100,
    trend,
    mentions_by_date: mentionsByDate.sort((a, b) =>
      (b.date || '').localeCompare(a.date || '')
    )
  }
})
