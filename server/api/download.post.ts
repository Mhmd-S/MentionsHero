import { spawn } from 'node:child_process'
import { join } from 'node:path'
import { existsSync, mkdirSync, readFileSync, unlinkSync } from 'node:fs'
import Replicate from 'replicate'
import { createClient } from '@supabase/supabase-js'
import { updateJobProgress } from '../utils/job-progress'

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const replicate = new Replicate({ auth: config.replicateApiKey })
  const supabase = createClient(config.supabaseUrl, config.supabaseServiceKey)

  const body = await readBody(event)
  const { url, jobId } = body

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

  try {
    // Download audio as MP3
    if (jobId) await updateJobProgress(jobId, 'downloading')
    const audioPath = await downloadAudio(url, downloadsDir)

    // Split audio into chunks and transcribe
    if (jobId) await updateJobProgress(jobId, 'transcribing')
    const rawTranscript = await transcribeAudio(replicate, audioPath, downloadsDir, jobId)

    // Clean up the audio file
    if (existsSync(audioPath)) {
      unlinkSync(audioPath)
    }

    // Clean up punctuation with Llama
    if (jobId) await updateJobProgress(jobId, 'cleaning')
    const transcript = await cleanupTranscript(replicate, rawTranscript)

    // Save to Supabase
    if (jobId) await updateJobProgress(jobId, 'saving')
    const { data, error } = await supabase
      .from('transcripts')
      .insert({
        youtube_url: url,
        transcript
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
      transcript,
      id: data.id
    }
  } catch (err: any) {
    // Mark job as failed
    if (jobId) {
      await updateJobProgress(jobId, 'failed', undefined, {
        error_message: err.data?.message || err.message || 'Processing failed'
      })
    }
    throw err
  }
})

function downloadAudio(url: string, downloadsDir: string): Promise<string> {
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
  })
}

async function getAudioDuration(audioPath: string): Promise<number> {
  return new Promise((resolve, reject) => {
    const ffprobe = spawn('ffprobe', [
      '-v', 'error',
      '-show_entries', 'format=duration',
      '-of', 'default=noprint_wrappers=1:nokey=1',
      audioPath
    ])

    let output = ''

    ffprobe.stdout.on('data', (data: Buffer) => {
      output += data.toString()
    })

    ffprobe.on('close', (code: number | null) => {
      if (code === 0) {
        resolve(parseFloat(output.trim()))
      } else {
        reject(new Error('Failed to get audio duration'))
      }
    })

    ffprobe.on('error', () => {
      reject(new Error('ffprobe not found'))
    })
  })
}

function splitAudio(audioPath: string, startTime: number, duration: number, outputPath: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const ffmpeg = spawn('ffmpeg', [
      '-i', audioPath,
      '-ss', startTime.toString(),
      '-t', duration.toString(),
      '-acodec', 'libmp3lame',
      '-y',
      outputPath
    ])

    ffmpeg.on('close', (code: number | null) => {
      if (code === 0) {
        resolve()
      } else {
        reject(new Error('Failed to split audio'))
      }
    })

    ffmpeg.on('error', () => {
      reject(new Error('ffmpeg not found'))
    })
  })
}

async function transcribeChunk(replicate: Replicate, audioPath: string): Promise<string> {
  const audioBuffer = readFileSync(audioPath)
  const base64Audio = audioBuffer.toString('base64')
  const dataUri = `data:audio/mp3;base64,${base64Audio}`

  const output = await replicate.run('openai/gpt-4o-transcribe', {
    input: {
      audio_file: dataUri
    }
  })

  // The output is the transcription text
  if (typeof output === 'string') {
    return output
  }
  if (output && typeof output === 'object' && 'text' in output) {
    return (output as { text: string }).text
  }
  return String(output)
}

async function transcribeAudio(replicate: Replicate, audioPath: string, downloadsDir: string, jobId?: string): Promise<string> {
  const CHUNK_DURATION = 600 // 10 minutes per chunk to stay within limits

  let totalDuration: number
  try {
    totalDuration = await getAudioDuration(audioPath)
  } catch {
    // If ffprobe fails, transcribe the whole file
    if (jobId) await updateJobProgress(jobId, 'transcribing', { current_chunk: 1, total_chunks: 1 })
    return await transcribeChunk(replicate, audioPath)
  }

  // If audio is short enough, transcribe directly
  if (totalDuration <= CHUNK_DURATION) {
    if (jobId) await updateJobProgress(jobId, 'transcribing', { current_chunk: 1, total_chunks: 1 })
    return await transcribeChunk(replicate, audioPath)
  }

  // Split into chunks and transcribe each
  const transcripts: string[] = []
  const numChunks = Math.ceil(totalDuration / CHUNK_DURATION)

  for (let i = 0; i < numChunks; i++) {
    const startTime = i * CHUNK_DURATION
    const chunkPath = join(downloadsDir, `chunk_${i}.mp3`)

    // Update progress with current chunk
    if (jobId) await updateJobProgress(jobId, 'transcribing', { current_chunk: i + 1, total_chunks: numChunks })

    await splitAudio(audioPath, startTime, CHUNK_DURATION, chunkPath)

    const chunkTranscript = await transcribeChunk(replicate, chunkPath)
    transcripts.push(chunkTranscript)

    // Clean up chunk
    if (existsSync(chunkPath)) {
      unlinkSync(chunkPath)
    }
  }

  return transcripts.join(' ')
}

async function cleanupTranscript(replicate: Replicate, transcript: string): Promise<string> {
  const MAX_CHUNK_CHARS = 1500 // ~500 tokens to stay well under 8096 limit with prompt

  // If short enough, process directly
  if (transcript.length <= MAX_CHUNK_CHARS) {
    return await cleanupChunk(replicate, transcript)
  }

  // Split into chunks at word boundaries
  const chunks: string[] = []
  const words = transcript.split(/\s+/)
  let currentChunk = ''

  for (const word of words) {
    if ((currentChunk + ' ' + word).length > MAX_CHUNK_CHARS && currentChunk) {
      chunks.push(currentChunk.trim())
      currentChunk = word
    } else {
      currentChunk += (currentChunk ? ' ' : '') + word
    }
  }
  if (currentChunk) {
    chunks.push(currentChunk.trim())
  }

  // Clean each chunk sequentially to avoid rate limits
  const cleanedChunks: string[] = []
  for (const chunk of chunks) {
    const cleaned = await cleanupChunk(replicate, chunk)
    cleanedChunks.push(cleaned)
  }

  return cleanedChunks.join(' ')
}

async function cleanupChunk(replicate: Replicate, text: string): Promise<string> {
  const output = await replicate.run('meta/meta-llama-3-8b-instruct', {
    input: {
      prompt: `Fix punctuation only. Output ONLY the corrected text, nothing else. No introduction, no explanation, no "Here is" - just the text with fixed punctuation.

${text}`,
      max_tokens: 4096
    }
  })

  let result: string
  if (typeof output === 'string') {
    result = output
  } else if (Array.isArray(output)) {
    result = output.join('')
  } else {
    return text
  }

  // Strip common LLM preambles
  const preambles = [
    /^here is the cleaned[^:]*:\s*/i,
    /^here is the corrected[^:]*:\s*/i,
    /^here is the fixed[^:]*:\s*/i,
    /^here is the transcript[^:]*:\s*/i,
    /^the corrected[^:]*:\s*/i,
    /^corrected[^:]*:\s*/i,
    /^transcript[^:]*:\s*/i,
    /^cleaned[^:]*:\s*/i,
  ]

  for (const preamble of preambles) {
    result = result.replace(preamble, '')
  }

  return result.trim()
}
