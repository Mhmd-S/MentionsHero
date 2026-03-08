"""Channel info API routes."""

from fastapi import APIRouter, HTTPException

from backend.models.video import ChannelInfo, ChannelInfoRequest
from backend.services.youtube_service import get_channel_videos, validate_channel_url

router = APIRouter(prefix="/api/channel", tags=["channel"])


@router.post("/info")
async def channel_info(request: ChannelInfoRequest) -> ChannelInfo:
    """Get channel videos from YouTube channel URL."""
    if not request.url:
        raise HTTPException(status_code=400, detail="Channel URL is required")

    if not validate_channel_url(request.url):
        raise HTTPException(status_code=400, detail="Invalid channel URL")

    try:
        info = await get_channel_videos(request.url)
        return info
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
