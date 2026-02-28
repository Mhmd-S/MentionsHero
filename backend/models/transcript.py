"""Transcript-related Pydantic models."""

from datetime import datetime

from pydantic import BaseModel, Field


class Transcript(BaseModel):
    """Transcript model."""
    id: str
    youtube_url: str | None = None
    transcript: str
    name: str | None = None
    created_at: datetime
    folder_id: str | None = None
    speakers: list[str] | None = None
    upload_date: str | None = None  # YouTube upload date (YYYYMMDD format)
    is_public: bool = False
    is_premium: bool = False

    class Config:
        from_attributes = True


class TranscriptCreate(BaseModel):
    """Request model for creating a transcript."""
    youtube_url: str
    transcript: str
    folder_id: str | None = None


class TranscriptUpdate(BaseModel):
    """Request model for updating a transcript."""
    name: str | None = None
    folder_id: str | None = None
    is_public: bool | None = None
    is_premium: bool | None = None


class SpeakerFrequency(BaseModel):
    """Speaker frequency for search results."""
    speaker: str
    count: int


class TranscriptWithHighlights(BaseModel):
    """Transcript with highlighting information."""
    id: str
    youtube_url: str | None = None
    transcript: str
    name: str | None = None
    created_at: datetime
    folder_id: str | None = None
    speakers: list[str] | None = None
    available_speakers: list[str] = Field(default_factory=list, alias="availableSpeakers")
    match_count: int | None = Field(None, alias="matchCount")
    speaker_frequencies: list[SpeakerFrequency] | None = Field(None, alias="speakerFrequencies")
    has_highlights: bool = Field(False, alias="hasHighlights")

    class Config:
        from_attributes = True
        populate_by_name = True
