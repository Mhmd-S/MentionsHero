import { spawn } from 'node:child_process'
import { join } from 'node:path'
import { existsSync, mkdirSync, readFileSync, unlinkSync } from 'node:fs'
import Replicate from 'replicate'
import { createClient } from '@supabase/supabase-js'

export default defineEventHandler(async (event) => {
  const config = useRuntimeConfig()
  const replicate = new Replicate({ auth: config.replicateApiKey })
  const supabase = createClient(config.supabaseUrl, config.supabaseServiceKey)

  const body = await readBody(event)
  const { url } = body

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

  // Download audio as MP3
  const audioPath = await downloadAudio(url, downloadsDir)

  // Split audio into chunks and transcribe
  const rawTranscript = await transcribeAudio(replicate, audioPath, downloadsDir)

  // Clean up the audio file
  if (existsSync(audioPath)) {
    unlinkSync(audioPath)
  }

  // Clean up punctuation with Llama
  const transcript = await cleanupTranscript(replicate, rawTranscript)

  // Save to Supabase
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

  return {
    success: true,
    transcript,
    id: data.id
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

async function transcribeAudio(replicate: Replicate, audioPath: string, downloadsDir: string): Promise<string> {
  const CHUNK_DURATION = 600 // 10 minutes per chunk to stay within limits

  let totalDuration: number
  try {
    totalDuration = await getAudioDuration(audioPath)
  } catch {
    // If ffprobe fails, transcribe the whole file
    return await transcribeChunk(replicate, audioPath)
  }

  // If audio is short enough, transcribe directly
  if (totalDuration <= CHUNK_DURATION) {
    return await transcribeChunk(replicate, audioPath)
  }

  // Split into chunks and transcribe each
  const transcripts: string[] = []
  const numChunks = Math.ceil(totalDuration / CHUNK_DURATION)

  for (let i = 0; i < numChunks; i++) {
    const startTime = i * CHUNK_DURATION
    const chunkPath = join(downloadsDir, `chunk_${i}.mp3`)

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
  const output = await replicate.run('meta/meta-llama-3-8b-instruct', {
    input: {
      prompt: `Clean up the punctuation in this transcript. Fix commas, apostrophes, periods, and other punctuation marks. Do NOT change any words, spelling, or grammar - only fix punctuation. Return only the cleaned transcript with no other text.

Transcript:
${transcript}`,
      max_tokens: 4096
    }
  })

  if (typeof output === 'string') {
    return output
  }
  if (Array.isArray(output)) {
    return output.join('')
  }
  return transcript
}
