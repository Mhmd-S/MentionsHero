"""Analysis-related Pydantic models."""

from typing import Any

from pydantic import BaseModel, Field


class TermFrequencyRequest(BaseModel):
    """Request model for term frequency analysis."""
    term: str
    case_sensitive: bool = False
    folder_id: str | None = None
    speakers: list[str] | None = None


class MentionByDate(BaseModel):
    """Mention count by date."""
    date: str | None  # YouTube upload date
    name: str
    count: int


class TermFrequencyResponse(BaseModel):
    """Response model for term frequency analysis."""
    term: str
    total_mentions: int
    briefings_with_term: int
    total_briefings: int
    percentage: float
    trend: str
    mentions_by_date: list[MentionByDate]


class AllTermsRequest(BaseModel):
    """Request model for all terms analysis."""
    min_frequency: int = Field(default=5, ge=1)
    max_terms: int = Field(default=500, ge=1, le=1000)
    folder_id: str | None = None
    speakers: list[str] | None = None


class TermInfo(BaseModel):
    """Individual term information."""
    term: str
    count: int
    briefings_with_term: int
    total_briefings: int
    percentage: float


class AllTermsResponse(BaseModel):
    """Response model for all terms analysis."""
    terms: list[TermInfo]
    count: int
    folder_id: str | None = None


class NgramsRequest(BaseModel):
    """Request model for n-grams analysis."""
    n: int = Field(default=2, ge=2, le=3)
    min_frequency: int = Field(default=3, ge=1)
    max_ngrams: int = Field(default=200, ge=1, le=500)
    folder_id: str | None = None
    speakers: list[str] | None = None


class NgramInfo(BaseModel):
    """Individual n-gram information."""
    phrase: str
    count: int
    briefings_with_phrase: int
    total_briefings: int
    percentage: float


class NgramsResponse(BaseModel):
    """Response model for n-grams analysis."""
    ngrams: list[NgramInfo]
    n: int
    count: int
    folder_id: str | None = None


class SearchRequest(BaseModel):
    """Request model for search."""
    query: str
    context_chars: int = Field(default=200, ge=50, le=500)
    folder_id: str | None = None
    speakers: list[str] | None = None


class SearchMatch(BaseModel):
    """Individual search match."""
    transcript_id: str
    transcript_name: str
    date: str | None
    context: str
    position: int


class SearchResponse(BaseModel):
    """Response model for search."""
    query: str
    total_matches: int
    transcripts_with_matches: int
    matches: list[SearchMatch]


class Speaker(BaseModel):
    """Speaker information."""
    name: str
    segment_count: int
    briefings: int


class SpeakersResponse(BaseModel):
    """Response model for speakers list."""
    speakers: list[Speaker]


class TranscriptAnalysisRequest(BaseModel):
    """Request model for LLM transcript analysis."""
    folder_id: str = Field(alias="folderId")

    class Config:
        populate_by_name = True
