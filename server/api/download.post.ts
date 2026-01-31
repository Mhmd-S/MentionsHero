import { spawn, type ChildProcess } from 'node:child_process'
import { join } from 'node:path'
import { readFile, stat } from 'node:fs/promises'
import { existsSync, mkdirSync, unlinkSync } from 'node:fs'
import { GoogleGenAI, createUserContent, createPartFromUri, Type } from '@google/genai'
import { createClient } from '@supabase/supabase-js'
import { updateJobProgress, checkCancellation, markJobCancelled } from '../utils/job-progress'
import { trackProcess, untrackProcess } from '../utils/process-tracker'

class CancellationError extends Error {
  constructor() {
    super('Job was cancelled')
    this.name = 'CancellationError'
  }
}

async function withRetry<T>(
  fn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000,
  serviceName: string = 'API'
): Promise<T> {
  let lastError: Error | undefined
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fn()
    } catch (error: any) {
      lastError = error
      const isRetryable = error?.response?.status === 502 ||
        error?.response?.status === 503 ||
        error?.response?.status === 504 ||
        error?.status === 429 ||
        error?.message?.includes('Bad Gateway') ||
        error?.message?.includes('rate limit')

      if (!isRetryable || attempt === maxRetries) {
        throw error
      }

      const delay = baseDelay * Math.pow(2, attempt)
      console.log(`${serviceName} error (attempt ${attempt + 1}/${maxRetries + 1}), retrying in ${delay}ms...`)
      await new Promise(resolve => setTimeout(resolve, delay))
    }
  }
  throw lastError
}

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const supabase = createClient(config.supabaseUrl, config.supabaseServiceKey)

  const body = await readBody(event)
  const { url, jobId, folderId, videoTitle } = body

  if (!url) {
    throw createError({
      statusCode: 400,
      message: 'YouTube URL is required'
    })
  }

  const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+/
  if (!youtubeRegex.test(url)) {
    throw createError({
      statusCode: 400,
      message: 'Invalid YouTube URL'
    })
  }

  const downloadsDir = join(process.cwd(), 'downloads')
  if (!existsSync(downloadsDir)) {
    mkdirSync(downloadsDir, { recursive: true })
  }

  const abortController = new AbortController()
  let audioPath: string | null = null

  // Helper to check for cancellation
  const checkForCancellation = async () => {
    if (jobId && await checkCancellation(jobId)) {
      throw new CancellationError()
    }
  }

  try {
    // Check cancellation before starting
    await checkForCancellation()

    // Download audio as MP3
    if (jobId) await updateJobProgress(jobId, 'downloading', {
      substep: 'Extracting audio',
      substep_detail: 'Using yt-dlp to download MP3'
    })
    audioPath = await downloadAudio(url, downloadsDir, jobId, abortController)

    // Check cancellation before transcribing
    await checkForCancellation()

    // Transcribe with speaker diarization
    if (jobId) await updateJobProgress(jobId, 'transcribing', {
      substep: 'Transcribing with speaker identification',
      substep_detail: 'Gemini 3 Flash'
    })
    const rawTranscript = await transcribeAudio(config.geminiApiKey, audioPath, jobId, abortController.signal)

    // Clean up the audio file
    if (existsSync(audioPath)) {
      unlinkSync(audioPath)
      audioPath = null
    }

    // Check cancellation before saving
    await checkForCancellation()

    // Save to Supabase
    if (jobId) await updateJobProgress(jobId, 'saving', {
      substep: 'Saving transcript',
      substep_detail: 'Storing in database'
    })
    const { data, error } = await supabase
      .from('transcripts')
      .insert({
        youtube_url: url,
        transcript: rawTranscript,
        folder_id: folderId || null
      })
      .select()
      .single()

    if (error) {
      throw createError({
        statusCode: 500,
        message: `Failed to save transcript: ${error.message}`
      })
    }

    // Mark job as completed
    if (jobId) {
      await updateJobProgress(jobId, 'completed', undefined, { transcript_id: data.id })
    }

    return {
      success: true,
      transcript: rawTranscript,
      id: data.id
    }
  } catch (err: any) {
    // Clean up audio file on error
    if (audioPath && existsSync(audioPath)) {
      try {
        unlinkSync(audioPath)
      } catch {
        // Ignore cleanup errors
      }
    }

    if (err instanceof CancellationError) {
      if (jobId) {
        await markJobCancelled(jobId)
      }
      throw createError({
        statusCode: 499,
        message: 'Job was cancelled'
      })
    }

    // Mark job as failed
    if (jobId) {
      await updateJobProgress(jobId, 'failed', undefined, {
        error_message: err.data?.message || err.message || 'Processing failed'
      })
    }
    throw err
  } finally {
    // Untrack the process
    if (jobId) {
      untrackProcess(jobId)
    }
  }
})

function downloadAudio(url: string, downloadsDir: string, jobId?: string, abortController?: AbortController): Promise<string> {
  return new Promise((resolve, reject) => {
    const outputTemplate = join(downloadsDir, '%(id)s.%(ext)s')

    const ytdlp = spawn('yt-dlp', [
      '-x',
      '--audio-format', 'mp3',
      '--audio-quality', '0',
      '-o', outputTemplate,
      '--print', 'after_move:filepath',
      url
    ])

    // Track the process for cancellation
    if (jobId && abortController) {
      trackProcess(jobId, ytdlp, abortController)
    }

    let outputPath = ''
    let errorOutput = ''

    ytdlp.stdout.on('data', (data: Buffer) => {
      const line = data.toString().trim()
      if (line && !line.startsWith('[')) {
        outputPath = line
      }
    })

    ytdlp.stderr.on('data', (data: Buffer) => {
      errorOutput += data.toString()
    })

    ytdlp.on('close', (code: number | null) => {
      if (code === 0 && outputPath) {
        resolve(outputPath)
      } else if (ytdlp.killed) {
        reject(new CancellationError())
      } else {
        reject(createError({
          statusCode: 500,
          message: `Download failed: ${errorOutput || 'Unknown error'}`
        }))
      }
    })

    ytdlp.on('error', (err: Error) => {
      reject(createError({
        statusCode: 500,
        message: `Failed to start yt-dlp: ${err.message}`
      }))
    })

    // Listen for abort signal
    if (abortController) {
      abortController.signal.addEventListener('abort', () => {
        if (!ytdlp.killed) {
          ytdlp.kill('SIGTERM')
        }
      })
    }
  })
}

interface DiarizedSegment {
  speaker: string
  text: string
  start: number
  end: number
}

interface GeminiSegment {
  speaker: string
  timestamp: string
  content: string
}

interface GeminiTranscriptResponse {
  segments: GeminiSegment[]
}

function formatGeminiTranscript(segments: GeminiSegment[]): string {
  const lines: string[] = []
  let currentSpeaker = ''

  for (const segment of segments) {
    if (segment.speaker !== currentSpeaker) {
      currentSpeaker = segment.speaker
      // Add newline before speaker label (except for first speaker)
      if (lines.length > 0) {
        lines.push('')
      }
      lines.push(`${segment.speaker}:`)
    }
    // Add content on a new line after speaker label
    lines.push(segment.content.trim())
  }

  return lines.join('\n').trim()
}

async function uploadAudioToGemini(ai: GoogleGenAI, audioPath: string, abortSignal?: AbortSignal): Promise<{ uri: string; mimeType: string }> {
  if (abortSignal?.aborted) {
    throw new CancellationError()
  }

  const stats = await stat(audioPath)
  
  // Use Files API for files > 20MB, inline for smaller files
  if (stats.size > 20 * 1024 * 1024) {
    const file = await withRetry(
      async () => {
        const result = await ai.files.upload({
          file: audioPath,
          config: { mimeType: 'audio/mp3' }
        })
        return result as { uri: string; mimeType: string }
      },
      3,
      1000,
      'Gemini Files API'
    )
    return { uri: file.uri, mimeType: file.mimeType }
  } else {
    // For smaller files, we'll use inline data in generateContent
    // Return a placeholder that indicates inline usage
    return { uri: 'inline', mimeType: 'audio/mp3' }
  }
}

async function transcribeWithGemini(ai: GoogleGenAI, audioPath: string, abortSignal?: AbortSignal): Promise<string> {
  if (abortSignal?.aborted) {
    throw new CancellationError()
  }

  const prompt = `Process the audio file and generate a detailed transcription with speaker diarization.

Requirements:
1. Identify distinct speakers (e.g., Speaker 1, Speaker 2, or use SPEAKER_00, SPEAKER_01 format if names are not available).
2. Provide accurate timestamps for each segment (Format: MM:SS).
3. Transcribe the speech accurately, preserving the natural flow of conversation.
4. Group consecutive segments from the same speaker together.`

  const fileInfo = await uploadAudioToGemini(ai, audioPath, abortSignal)

  let contents: any
  if (fileInfo.uri === 'inline') {
    // Use inline data for smaller files
    const audioBuffer = await readFile(audioPath)
    const base64Audio = audioBuffer.toString('base64')
    contents = [
      { text: prompt },
      {
        inlineData: {
          mimeType: 'audio/mp3',
          data: base64Audio
        }
      }
    ]
  } else {
    // Use uploaded file URI
    contents = createUserContent([
      createPartFromUri(fileInfo.uri, fileInfo.mimeType),
      prompt
    ])
  }

  const response = await withRetry(
    async () => {
      const result = await ai.models.generateContent({
        model: 'gemini-3-flash-preview',
        contents,
        config: {
          responseMimeType: 'application/json',
          responseSchema: {
            type: Type.OBJECT,
            properties: {
              segments: {
                type: Type.ARRAY,
                description: 'List of transcribed segments with speaker and timestamp.',
                items: {
                  type: Type.OBJECT,
                  properties: {
                    speaker: {
                      type: Type.STRING,
                      description: 'Speaker identifier (e.g., SPEAKER_00, SPEAKER_01, or name if available)'
                    },
                    timestamp: {
                      type: Type.STRING,
                      description: 'Timestamp in MM:SS format'
                    },
                    content: {
                      type: Type.STRING,
                      description: 'Transcribed text content'
                    }
                  },
                  required: ['speaker', 'timestamp', 'content']
                }
              }
            },
            required: ['segments']
          }
        }
      })
      return result as { text: string }
    },
    3,
    1000,
    'Gemini API'
  )

  if (abortSignal?.aborted) {
    throw new CancellationError()
  }

  const responseText = response.text
  if (!responseText) {
    throw createError({
      statusCode: 500,
      message: 'Gemini API returned empty response'
    })
  }

  const parsedResponse = JSON.parse(responseText) as GeminiTranscriptResponse

  if (!parsedResponse.segments || parsedResponse.segments.length === 0) {
    throw createError({
      statusCode: 500,
      message: 'Gemini API returned no transcription segments'
    })
  }

  return formatGeminiTranscript(parsedResponse.segments)
}

async function transcribeAudio(geminiApiKey: string, audioPath: string, jobId?: string, abortSignal?: AbortSignal): Promise<string> {
  // Check for abort before starting
  if (abortSignal?.aborted) {
    throw new CancellationError()
  }

  if (!geminiApiKey) {
    throw createError({
      statusCode: 500,
      message: 'Gemini API key is not configured'
    })
  }

  const ai = new GoogleGenAI({ apiKey: geminiApiKey })

  if (jobId) {
    await updateJobProgress(jobId, 'transcribing', {
      current_chunk: 1,
      total_chunks: 1,
      substep: 'Transcribing with speaker identification',
      substep_detail: 'Gemini 3 Flash'
    })
  }

  return await transcribeWithGemini(ai, audioPath, abortSignal)
}
