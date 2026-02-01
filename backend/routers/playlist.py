"""Playlist info API routes."""

from fastapi import APIRouter, HTTPException

from backend.models.video import PlaylistInfo, PlaylistInfoRequest
from backend.services.youtube_service import get_playlist_info, validate_playlist_url

router = APIRouter(prefix="/api/playlist", tags=["playlist"])


@router.post("/info")
async def playlist_info(request: PlaylistInfoRequest) -> PlaylistInfo:
    """Get playlist information from YouTube URL."""
    if not request.url:
        raise HTTPException(status_code=400, detail="Playlist URL is required")

    if not validate_playlist_url(request.url):
        raise HTTPException(status_code=400, detail="Invalid playlist URL")

    try:
        info = await get_playlist_info(request.url)
        return info
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
