"""Kalshi-related Pydantic models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ----- Kalshi API response models (external API) -----


class KalshiMarketAPI(BaseModel):
    """Market as returned by Kalshi API."""
    ticker: str
    event_ticker: str
    market_type: str = "binary"
    yes_sub_title: str | None = None
    no_sub_title: str | None = None
    status: str = "active"
    result: str = ""
    last_price: float | None = None
    yes_bid: float | None = None
    yes_ask: float | None = None
    no_bid: float | None = None
    no_ask: float | None = None
    previous_price: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    close_time: str | None = None
    open_time: str | None = None
    rules_primary: str | None = None
    rules_secondary: str | None = None
    settlement_value: float | None = None

    class Config:
        populate_by_name = True


class KalshiEventAPI(BaseModel):
    """Event as returned by Kalshi API."""
    event_ticker: str
    series_ticker: str | None = None
    title: str | None = None
    sub_title: str | None = None
    mutually_exclusive: bool = False
    category: str | None = None
    status: str = "active"
    strike_date: str | None = None
    strike_period: str | None = None
    markets: list[KalshiMarketAPI] = Field(default_factory=list)

    class Config:
        populate_by_name = True


class KalshiSeriesAPI(BaseModel):
    """Series as returned by Kalshi API."""
    ticker: str
    title: str | None = None
    frequency: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    settlement_sources: list[dict] = Field(default_factory=list)
    fee_type: str | None = None

    class Config:
        populate_by_name = True


# ----- DB record models -----


class KalshiSeriesRecord(BaseModel):
    """Stored Kalshi series (our DB row)."""
    id: str
    ticker: str
    title: str | None = None
    frequency: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    settlement_sources: list[dict] = Field(default_factory=list)
    fee_type: str | None = None
    status: str = "active"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class KalshiEventRecord(BaseModel):
    """Stored Kalshi event (our DB row)."""
    id: str
    event_ticker: str
    series_ticker: str | None = None
    series_id: str | None = None
    title: str | None = None
    sub_title: str | None = None
    mutually_exclusive: bool = False
    category: str | None = None
    status: str = "active"
    strike_date: datetime | None = None
    strike_period: str | None = None
    show_public: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class KalshiMarketRecord(BaseModel):
    """Stored Kalshi market (our DB row)."""
    id: str
    ticker: str
    event_ticker: str
    event_id: str
    market_type: str = "binary"
    question: str | None = None
    yes_sub_title: str | None = None
    no_sub_title: str | None = None
    status: str = "active"
    result: str | None = None
    last_price: float | None = None
    yes_bid: float | None = None
    yes_ask: float | None = None
    no_bid: float | None = None
    no_ask: float | None = None
    previous_price: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    close_time: datetime | None = None
    open_time: datetime | None = None
    settlement_value: float | None = None
    rules_primary: str | None = None
    rules_secondary: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MarketSearchConfigRecord(BaseModel):
    """Stored search criteria for a market."""
    id: str
    market_id: str
    search_terms: list[str] = Field(default_factory=list)
    min_count: int = 0
    logic: str = "at_least"
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ----- Request/Response models -----


class AddSeriesRequest(BaseModel):
    """Request to add a Kalshi series by ticker."""
    ticker: str


class AnalyzeRequest(BaseModel):
    """Request model for market analysis."""
    market_ticker: str
    term: str


class AnalyzeResponse(BaseModel):
    """Response model for market analysis."""
    market_id: str
    market_question: str
    term: str
    historical_percentage: float
    market_yes_price: float
    recommendation: Literal["yes", "no", "skip"]
    confidence: Literal["high", "medium", "low"]
    reason: str
    expected_value: float


