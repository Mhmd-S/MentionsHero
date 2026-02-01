"""Job-related Pydantic models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job status enumeration."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    SAVING = "saving"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageProgress(BaseModel):
    """Progress information for the current job stage."""
    current_chunk: int | None = None
    total_chunks: int | None = None
    substep: str | None = None
    substep_detail: str | None = None


class Job(BaseModel):
    """Job model representing a transcription job."""
    id: str
    youtube_url: str
    status: JobStatus
    stage_progress: StageProgress | dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    transcript_id: str | None = None
    cancel_requested: bool = False
    playlist_id: str | None = None
    playlist_name: str | None = None
    playlist_index: int | None = None
    video_title: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VideoInput(BaseModel):
    """Video input for batch job creation."""
    url: str
    title: str | None = None


class CreateJobRequest(BaseModel):
    """Request model for creating a new job."""
    url: str
    folder_id: str | None = Field(None, alias="folderId")
    video_title: str | None = Field(None, alias="videoTitle")
    speaker_hint: str | None = Field(None, alias="speakerHint")

    class Config:
        populate_by_name = True


class CreateJobResponse(BaseModel):
    """Response model for job creation."""
    job_id: str = Field(alias="jobId")
    status: JobStatus

    class Config:
        populate_by_name = True


class BatchJobsRequest(BaseModel):
    """Request model for batch job creation."""
    videos: list[VideoInput]
    folder_id: str | None = Field(None, alias="folderId")
    playlist_id: str | None = Field(None, alias="playlistId")
    playlist_name: str | None = Field(None, alias="playlistName")
    speaker_hint: str | None = Field(None, alias="speakerHint")

    class Config:
        populate_by_name = True


class BatchJobsResponse(BaseModel):
    """Response model for batch job creation."""
    job_ids: list[str] = Field(alias="jobIds")
    total: int

    class Config:
        populate_by_name = True


class BulkCancelRequest(BaseModel):
    """Request model for bulk job cancellation."""
    playlist_id: str = Field(alias="playlistId")

    class Config:
        populate_by_name = True


class BulkCancelResponse(BaseModel):
    """Response model for bulk cancellation."""
    cancelled: int


class CancelResponse(BaseModel):
    """Response model for job cancellation."""
    success: bool
    message: str
