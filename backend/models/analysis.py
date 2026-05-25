"""Analysis-related Pydantic models (speakers only)."""

from pydantic import BaseModel


class Speaker(BaseModel):
    """Speaker information."""
    name: str
    segment_count: int
    briefings: int


class SpeakersResponse(BaseModel):
    """Response model for speakers list."""
    speakers: list[Speaker]
