"""YouTube service for yt-dlp operations."""

import asyncio
import json
from typing import Any

from backend.models.video import VideoInfo, PlaylistInfo, PlaylistVideo
from backend.services.yt_dlp_utils import get_yt_dlp_base_args


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human-readable string."""
    if not seconds:
        return "0:00"

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


async def get_video_info(url: str) -> VideoInfo:
    """Fetch video information using yt-dlp."""
    yt_dlp_args = get_yt_dlp_base_args()
    yt_dlp_args.extend([
        '--dump-json',
        '--no-download',
        '--no-playlist',
        url
    ])

    proc = await asyncio.create_subprocess_exec(
        *yt_dlp_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode().strip() if stderr else "Failed to fetch video info"
        raise ValueError(error_msg)

    try:
        data = json.loads(stdout.decode())
    except json.JSONDecodeError:
        raise ValueError("Failed to parse video info")

    return VideoInfo(
        id=data.get("id", ""),
        title=data.get("title", ""),
        duration=data.get("duration", 0),
        duration_formatted=format_duration(data.get("duration", 0)),
        thumbnail=data.get("thumbnail") or (data.get("thumbnails", [{}])[0].get("url", "") if data.get("thumbnails") else ""),
        channel=data.get("channel") or data.get("uploader", ""),
        view_count=data.get("view_count", 0),
        upload_date=data.get("upload_date", "")
    )


async def get_playlist_info(url: str) -> PlaylistInfo:
    """Fetch playlist information using yt-dlp."""
    yt_dlp_args = get_yt_dlp_base_args()
    yt_dlp_args.extend([
        '--flat-playlist',
        '-j',
        '--no-download',
        url
    ])

    proc = await asyncio.create_subprocess_exec(
        *yt_dlp_args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        error_msg = stderr.decode().strip() if stderr else "Failed to fetch playlist info"
        raise ValueError(error_msg)

    output = stdout.decode().strip()
    if not output:
        raise ValueError("Empty response from yt-dlp")

    # Each line is a separate JSON object
    lines = output.split('\n')
    videos: list[PlaylistVideo] = []
    playlist_title = ""
    playlist_id = ""
    playlist_channel = ""

    for line in lines:
        if not line.strip():
            continue

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Extract playlist metadata from first entry
        if not playlist_id and data.get("playlist_id"):
            playlist_id = data["playlist_id"]
            playlist_title = data.get("playlist_title") or data.get("playlist", "Untitled Playlist")
            playlist_channel = data.get("playlist_uploader") or data.get("channel", "")

        # Extract video info
        if data.get("id") and data.get("title"):
            video_id = data["id"]
            duration = data.get("duration") or 0
            videos.append(PlaylistVideo(
                id=video_id,
                title=data["title"],
                duration=duration,
                duration_formatted=format_duration(duration),
                thumbnail=data.get("thumbnail") or f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg",
                channel=data.get("channel") or data.get("uploader") or "",
                url=data.get("url") or f"https://www.youtube.com/watch?v={video_id}"
            ))

    return PlaylistInfo(
        id=playlist_id,
        title=playlist_title,
        channel=playlist_channel,
        video_count=len(videos),
        videos=videos
    )


def validate_youtube_url(url: str) -> bool:
    """Validate that a URL is a valid YouTube URL."""
    import re
    pattern = r'^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+'
    return bool(re.match(pattern, url))


def validate_playlist_url(url: str) -> bool:
    """Validate that a URL is a valid YouTube playlist URL."""
    return "list=" in url
