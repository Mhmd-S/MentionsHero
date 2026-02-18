"""Pydantic models for the application."""

from backend.models.job import (
    Job,
    JobStatus,
    StageProgress,
    CreateJobRequest,
    CreateJobResponse,
    BatchJobsRequest,
    BatchJobsResponse,
    VideoInput,
    BulkCancelRequest,
    BulkCancelResponse,
    CancelResponse,
)
from backend.models.transcript import (
    Transcript,
    TranscriptCreate,
    TranscriptUpdate,
    TranscriptWithHighlights,
    SpeakerFrequency,
)
from backend.models.folder import (
    Folder,
    FolderCreate,
    FolderUpdate,
)
from backend.models.analysis import (
    TermFrequencyRequest,
    TermFrequencyResponse,
    AllTermsRequest,
    AllTermsResponse,
    NgramsRequest,
    NgramsResponse,
    SearchRequest,
    SearchResponse,
    SpeakersResponse,
    Speaker,
)
from backend.models.video import (
    VideoInfo,
    VideoInfoRequest,
    PlaylistVideo,
    PlaylistInfo,
    PlaylistInfoRequest,
)
from backend.models.polymarket import (
    PolymarketMarket,
    PolymarketEvent,
    PolymarketTag,
    MarketsResponse,
    AnalyzeRequest,
    AnalyzeResponse,
)
__all__ = [
    # Job models
    "Job",
    "JobStatus",
    "StageProgress",
    "CreateJobRequest",
    "CreateJobResponse",
    "BatchJobsRequest",
    "BatchJobsResponse",
    "VideoInput",
    "BulkCancelRequest",
    "BulkCancelResponse",
    "CancelResponse",
    # Transcript models
    "Transcript",
    "TranscriptCreate",
    "TranscriptUpdate",
    "TranscriptWithHighlights",
    "SpeakerFrequency",
    # Folder models
    "Folder",
    "FolderCreate",
    "FolderUpdate",
    # Analysis models
    "TermFrequencyRequest",
    "TermFrequencyResponse",
    "AllTermsRequest",
    "AllTermsResponse",
    "NgramsRequest",
    "NgramsResponse",
    "SearchRequest",
    "SearchResponse",
    "SpeakersResponse",
    "Speaker",
    # Video models
    "VideoInfo",
    "VideoInfoRequest",
    "PlaylistVideo",
    "PlaylistInfo",
    "PlaylistInfoRequest",
    # Polymarket models
    "PolymarketMarket",
    "PolymarketEvent",
    "PolymarketTag",
    "MarketsResponse",
    "AnalyzeRequest",
    "AnalyzeResponse",
]
