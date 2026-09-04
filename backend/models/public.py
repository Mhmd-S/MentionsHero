"""Public-facing Pydantic models.

The public API is anonymous and free — there is no premium tier and nothing is
ever locked, so no model here carries a gate flag.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PublicPersona(BaseModel):
    """Public persona listing model."""
    id: str
    name: str
    description: str | None = None
    slug: str | None = None
    image_url: str | None = None
    aliases: list[str] = Field(default_factory=list)
    transcript_count: int = 0


class PublicTranscriptSummary(BaseModel):
    """Public transcript summary for listing."""
    id: str
    name: str | None = None
    created_at: datetime
    folder_id: str | None = None
    folder_name: str | None = None
    preview: str = ""


class PublicTranscriptDetail(BaseModel):
    """Public transcript detail with optional highlights."""
    id: str
    name: str | None = None
    youtube_url: str | None = None
    transcript: str
    created_at: datetime
    available_speakers: list[str] = Field(default_factory=list, alias="availableSpeakers")
    match_count: int | None = Field(None, alias="matchCount")
    speaker_frequencies: list[dict[str, Any]] | None = Field(None, alias="speakerFrequencies")
    has_highlights: bool = Field(False, alias="hasHighlights")

    class Config:
        populate_by_name = True


class PaginatedResponse(BaseModel):
    """Paginated response wrapper."""
    items: list[Any]
    total: int
    page: int
    page_size: int
    total_pages: int
