import { spawn } from 'node:child_process'

export interface PlaylistVideo {
  id: string
  title: string
  duration: number
  durationFormatted: string
  thumbnail: string
  channel: string
  url: string
}

export interface PlaylistInfo {
  id: string
  title: string
  channel: string
  videoCount: number
  videos: PlaylistVideo[]
}

export default defineEventHandler(async (event) => {
  const body = await readBody(event)
  const { url } = body

  if (!url) {
    throw createError({
      statusCode: 400,
      message: 'Playlist URL is required'
    })
  }

  if (!url.includes('list=')) {
    throw createError({
      statusCode: 400,
      message: 'Invalid playlist URL'
    })
  }

  try {
    const info = await getPlaylistInfo(url)
    return info
  } catch (err: any) {
    throw createError({
      statusCode: 500,
      message: err.message || 'Failed to fetch playlist info'
    })
  }
})

function getPlaylistInfo(url: string): Promise<PlaylistInfo> {
  return new Promise((resolve, reject) => {
    const ytdlp = spawn('yt-dlp', [
      '--flat-playlist',
      '-j',
      '--no-download',
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
          // Each line is a separate JSON object
          const lines = output.trim().split('\n').filter(Boolean)
          const videos: PlaylistVideo[] = []
          let playlistTitle = ''
          let playlistId = ''
          let playlistChannel = ''

          for (const line of lines) {
            const data = JSON.parse(line)

            // Extract playlist metadata from first entry
            if (!playlistId && data.playlist_id) {
              playlistId = data.playlist_id
              playlistTitle = data.playlist_title || data.playlist || 'Untitled Playlist'
              playlistChannel = data.playlist_uploader || data.channel || ''
            }

            // Extract video info
            if (data.id && data.title) {
              videos.push({
                id: data.id,
                title: data.title,
                duration: data.duration || 0,
                durationFormatted: formatDuration(data.duration || 0),
                thumbnail: data.thumbnail || `https://i.ytimg.com/vi/${data.id}/mqdefault.jpg`,
                channel: data.channel || data.uploader || '',
                url: data.url || `https://www.youtube.com/watch?v=${data.id}`
              })
            }
          }

          resolve({
            id: playlistId,
            title: playlistTitle,
            channel: playlistChannel,
            videoCount: videos.length,
            videos
          })
        } catch (e) {
          reject(new Error('Failed to parse playlist info'))
        }
      } else {
        reject(new Error(errorOutput || 'Failed to fetch playlist info'))
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
