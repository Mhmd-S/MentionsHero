"""Pydantic models for the analytical data procurement system."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# News items
# ---------------------------------------------------------------------------

class NewsItem(BaseModel):
    id: str
    persona_id: str
    title: str
    body: str | None = None
    url: str
    source_name: str | None = None
    source_domain: str | None = None
    published_at: datetime
    procurement_source: str = "ddgs"
    sentiment_score: float | None = None
    topics: list[str] = []
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class ProcureNewsRequest(BaseModel):
    persona_id: str
    query: str = "Trump"
    days_back: int = 7


# ---------------------------------------------------------------------------
# Truth Social posts
# ---------------------------------------------------------------------------

class TruthSocialPost(BaseModel):
    id: str
    persona_id: str
    external_id: str | None = None
    content: str
    post_url: str | None = None
    posted_at: datetime
    source: str = "ddgs"
    media_urls: list[str] = []
    engagement: dict | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class ProcureTruthSocialRequest(BaseModel):
    persona_id: str
    days_back: int = 3


# ---------------------------------------------------------------------------
# Event tags
# ---------------------------------------------------------------------------

EVENT_TYPES = Literal[
    "rally", "press_conference", "press_briefing", "interview",
    "prepared_remarks", "signing_ceremony", "bilateral_meeting",
    "cabinet_meeting", "reception", "ceremony", "summit", "roundtable",
    "announcement", "greeting", "troop_address", "other"
]

AUDIENCE_TYPES = Literal[
    "supporters", "general", "press", "congress", "foreign", "military",
    "cabinet", "invited", "industry", "mixed", "other"
]


class EventTag(BaseModel):
    id: str
    transcript_id: str
    event_type: str
    city: str | None = None
    state: str | None = None
    country: str | None = None
    venue: str | None = None
    interviewer: str | None = None
    network: str | None = None
    is_teleprompter: bool | None = None
    audience_type: str | None = None
    event_time: datetime | None = None
    event_time_local: str | None = None
    classification_source: str = "manual"
    confidence: float | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class EventTagCreate(BaseModel):
    transcript_id: str
    event_type: EVENT_TYPES
    city: str | None = None
    state: str | None = None
    country: str | None = None
    venue: str | None = None
    interviewer: str | None = None
    network: str | None = None
    is_teleprompter: bool | None = None
    audience_type: AUDIENCE_TYPES | None = None
    event_time: datetime | None = None
    event_time_local: str | None = None
    notes: str | None = None


class EventTagUpdate(BaseModel):
    event_type: EVENT_TYPES | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    venue: str | None = None
    interviewer: str | None = None
    network: str | None = None
    is_teleprompter: bool | None = None
    audience_type: AUDIENCE_TYPES | None = None
    event_time: datetime | None = None
    event_time_local: str | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# Context windows
# ---------------------------------------------------------------------------

class ContextWindow(BaseModel):
    id: str
    transcript_id: str
    persona_id: str
    window_start: datetime
    window_end: datetime
    truth_social_post_count: int = 0
    news_item_count: int = 0
    news_sentiment_avg: float | None = None
    top_news_topics: list[str] = []
    truth_social_topics: list[str] = []
    market_snapshot: dict | None = None
    computed_at: datetime | None = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Procurement runs (audit log)
# ---------------------------------------------------------------------------

class ProcurementRun(BaseModel):
    id: str
    source_type: str
    persona_id: str
    status: str
    items_found: int = 0
    items_new: int = 0
    items_skipped: int = 0
    error_message: str | None = None
    details: list[dict] = []
    started_at: datetime | None = None
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Shared responses
# ---------------------------------------------------------------------------

class ProcurementResult(BaseModel):
    message: str
    run_id: str
    items_found: int = 0
    items_new: int = 0
    items_skipped: int = 0


class BulkAutoTagResult(BaseModel):
    message: str
    tagged: int = 0
    skipped: int = 0
    failed: int = 0


class BulkBackfillMetadataResult(BaseModel):
    message: str
    run_id: str
    candidates: int = 0
    succeeded: int = 0
    failed: int = 0


class BulkComputeResult(BaseModel):
    message: str
    computed: int = 0
    skipped: int = 0
    failed: int = 0
