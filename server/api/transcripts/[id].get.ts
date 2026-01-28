import { createClient } from '@supabase/supabase-js'
import { highlightTranscript, extractSpeakers } from '../../utils/transcript-filter'

export default defineEventHandler(async (event) => {
  const id = getRouterParam(event, 'id')
  const config = useRuntimeConfig()
  const supabase = createClient(config.supabaseUrl, config.supabaseServiceKey)
  
  const query = getQuery(event)
  const searchString = query.search as string | undefined
  const speakersParam = query.speakers as string | string[] | undefined
  let speakers: string[] | undefined
  if (speakersParam) {
    if (Array.isArray(speakersParam)) {
      speakers = speakersParam
    } else {
      // Handle comma-separated string
      speakers = speakersParam.split(',').map(s => s.trim()).filter(s => s.length > 0)
    }
  }

  const { data, error } = await supabase
    .from('transcripts')
    .select('*')
    .eq('id', id)
    .single()

  if (error) {
    throw createError({
      statusCode: 404,
      message: 'Transcript not found'
    })
  }

  // Extract available speakers
  const availableSpeakers = extractSpeakers(data.transcript)

  // Apply highlighting if search or speakers provided
  if (searchString || speakers) {
    const { highlightedTranscript, matchCount } = highlightTranscript(
      data.transcript,
      searchString,
      speakers
    )
    return {
      ...data,
      transcript: highlightedTranscript,
      matchCount,
      hasHighlights: true
    }
  }

  return {
    ...data,
    availableSpeakers
  }
})
