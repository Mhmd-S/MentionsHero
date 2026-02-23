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


class PublicSegment(BaseModel):
    """A single transcript segment for the public viewer."""
    speaker: str          # resolved canonical name (or raw if unresolved)
    speaker_raw: str      # original Gemini label
    resolved: bool        # True if matched a persona
    content: str          # HTML-escaped text


class PublicTranscriptResponse(BaseModel):
    """Response from the public transcript endpoint."""
    id: str
    name: str | None = None
    youtube_url: str | None = None
    upload_date: str | None = None
    created_at: datetime
    segments: list[PublicSegment]
    speaker_map: dict[str, str]     # {raw_label -> display_name}
    speakers: list[str]             # unique display names, ordered by first appearance
    segment_counts: dict[str, int]  # {display_name -> segment count}


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


class RecordReadRequest(BaseModel):
    """Request to record a transcript read."""
    transcript_id: str


class ReadStatusResponse(BaseModel):
    """Response with read metering status."""
    allowed: bool
    reads_this_month: int
    limit: int
