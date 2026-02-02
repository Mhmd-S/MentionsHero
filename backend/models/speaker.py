"""Speaker-related Pydantic models."""

from datetime import datetime

from pydantic import BaseModel


class SpeakerRecord(BaseModel):
    """Database speaker record."""
    id: str
    name: str
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class TranscriptSpeakerRecord(BaseModel):
    """Junction record linking transcript to speaker with segment count."""
    id: str
    transcript_id: str
    speaker_id: str
    segment_count: int = 0
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class SpeakerWithStats(BaseModel):
    """Speaker with aggregated stats (name, segment_count, briefings)."""
    name: str
    segment_count: int
    briefings: int
