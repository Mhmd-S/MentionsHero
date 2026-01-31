import { spawn } from 'node:child_process'

export interface VideoInfo {
  id: string
  title: string
  duration: number
  durationFormatted: string
  thumbnail: string
  channel: string
  viewCount: number
  uploadDate: string
}

export default defineEventHandler(async (event) => {
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

  try {
    const info = await getVideoInfo(url)
    return info
  } catch (err: any) {
    throw createError({
      statusCode: 500,
      message: err.message || 'Failed to fetch video info'
    })
  }
})

function getVideoInfo(url: string): Promise<VideoInfo> {
  return new Promise((resolve, reject) => {
    const ytdlp = spawn('yt-dlp', [
      '--dump-json',
      '--no-download',
      '--no-playlist',
      url
    ])

    let output = ''
    let errorOutput = ''

    ytdlp.stdout.on('data', (data: Buffer) => {
      output += data.toString()
    })

    ytdlp.stderr.on('data', (data: Buffer) => {
      errorOutput += data.toString()
    })

    ytdlp.on('close', (code: number | null) => {
      if (code === 0 && output) {
        try {
          const data = JSON.parse(output)
          resolve({
            id: data.id,
            title: data.title,
            duration: data.duration || 0,
            durationFormatted: formatDuration(data.duration || 0),
            thumbnail: data.thumbnail || data.thumbnails?.[0]?.url || '',
            channel: data.channel || data.uploader || '',
            viewCount: data.view_count || 0,
            uploadDate: data.upload_date || ''
          })
        } catch (e) {
          reject(new Error('Failed to parse video info'))
        }
      } else {
        reject(new Error(errorOutput || 'Failed to fetch video info'))
      }
    })

    ytdlp.on('error', (err: Error) => {
      reject(new Error(`Failed to start yt-dlp: ${err.message}`))
    })
  })
}

function formatDuration(seconds: number): string {
  if (!seconds) return '0:00'

  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const secs = Math.floor(seconds % 60)

  if (hours > 0) {
    return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
  }
  return `${minutes}:${secs.toString().padStart(2, '0')}`
}
