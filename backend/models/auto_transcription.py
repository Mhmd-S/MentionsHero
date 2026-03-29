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
    check_interval_minutes: int = 360
    max_videos_per_check: int = 5
    is_enabled: bool = True
    title_filter: str | None = None
    last_run_at: str | None = None
    last_run_status: str | None = None
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
    check_interval_minutes: int = 360
    max_videos_per_check: int = 5
    title_filter: str | None = None


class AutoSourceUpdate(BaseModel):
    """Request model for updating an auto-source."""
    folder_id: str | None = None
    speaker_hint: str | None = None
    check_interval_minutes: int | None = None
    max_videos_per_check: int | None = None
    title_filter: str | None = None
    is_enabled: bool | None = None


class AutoRun(BaseModel):
    """Auto-transcription run history entry."""
    id: str
    auto_source_id: str
    source_name: str | None = None
    persona_name: str | None = None
    status: str
    videos_found: int = 0
    videos_new: int = 0
    videos_queued: int = 0
    videos_skipped: int = 0
    error_message: str | None = None
    details: list[dict] = []
    started_at: datetime | None = None
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class ManualCheckResponse(BaseModel):
    """Response for manual check trigger."""
    message: str
    source_id: str
