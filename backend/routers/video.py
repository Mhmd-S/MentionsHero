"""Video info API routes."""

from fastapi import APIRouter, HTTPException

from backend.models.video import VideoInfo, VideoInfoRequest
from backend.services.youtube_service import get_video_info, validate_youtube_url

router = APIRouter(prefix="/api/video", tags=["video"])


@router.post("/info")
async def video_info(request: VideoInfoRequest) -> VideoInfo:
    """Get video information from YouTube URL."""
    if not request.url:
        raise HTTPException(status_code=400, detail="YouTube URL is required")

    if not validate_youtube_url(request.url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL")

    try:
        info = await get_video_info(request.url)
        return info
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
