"""Video and playlist-related Pydantic models."""

from pydantic import BaseModel


class VideoInfoRequest(BaseModel):
    """Request model for video info."""
    url: str


class VideoInfo(BaseModel):
    """Video information from YouTube."""
    id: str
    title: str
    duration: int
    duration_formatted: str
    thumbnail: str
    channel: str
    view_count: int
    upload_date: str

    class Config:
        # Allow camelCase from frontend
        populate_by_name = True


class PlaylistInfoRequest(BaseModel):
    """Request model for playlist info."""
    url: str


class PlaylistVideo(BaseModel):
    """Video information within a playlist."""
    id: str
    title: str
    duration: int = 0
    duration_formatted: str = "0:00"
    thumbnail: str = ""
    channel: str = ""
    url: str

    class Config:
        populate_by_name = True


class PlaylistInfo(BaseModel):
    """Playlist information from YouTube."""
    id: str
    title: str
    channel: str
    video_count: int
    videos: list[PlaylistVideo]

    class Config:
        populate_by_name = True


class ChannelInfoRequest(BaseModel):
    """Request model for channel info."""
    url: str


class ChannelInfo(BaseModel):
    """Channel information from YouTube."""
    id: str
    title: str
    video_count: int
    videos: list[PlaylistVideo]

    class Config:
        populate_by_name = True
