"""Auto-transcription Pydantic models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class AutoSource(BaseModel):
    """Auto-transcription source."""
    id: str
    persona_id: str
    persona_name: str | None = None
    source_type: str
    youtube_url: str
    source_name: str | None = None
    folder_id: str | None = None
    speaker_hint: str | None = None
    max_videos_per_check: int = 5
    backfill_limit: int | None = 500
    title_filter: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class AutoSourceCreate(BaseModel):
    """Request model for creating an auto-source."""
    persona_id: str
    source_type: Literal["channel", "playlist"]
    youtube_url: str
    folder_id: str | None = None
    speaker_hint: str | None = None
    max_videos_per_check: int = 5
    backfill_limit: int | None = 500
    title_filter: str | None = None


class AutoSourceUpdate(BaseModel):
    """Request model for updating an auto-source."""
    folder_id: str | None = None
    speaker_hint: str | None = None
    max_videos_per_check: int | None = None
    backfill_limit: int | None = None
    title_filter: str | None = None


class RunResultDetail(BaseModel):
    """One video's outcome from a manual run."""
    url: str
    title: str
    action: Literal["queued", "filtered", "exists", "error"]
    error: str | None = None


class RunResult(BaseModel):
    """Result of a manual run on a source."""
    videos_found: int
    videos_filtered: int
    videos_existing: int
    videos_queued: int
    details: list[RunResultDetail] = []


class TimelineEntry(BaseModel):
    """One row in the global auto-transcription timeline."""
    id: str
    auto_source_id: str
    source_name: str | None = None
    persona_id: str | None = None
    persona_name: str | None = None
    youtube_url: str
    video_title: str | None = None
    action: str
    job_id: str | None = None
    job_status: str | None = None
    job_error: str | None = None
    transcript_id: str | None = None
    created_at: datetime | None = None
