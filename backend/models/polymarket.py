"""Polymarket-related Pydantic models."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ----- Gamma API response models (external API) -----


class PolymarketTag(BaseModel):
    """Polymarket tag/category."""
    id: str
    label: str
    slug: str


class PolymarketToken(BaseModel):
    """Polymarket token information."""
    token_id: str
    outcome: str


class PolymarketMarket(BaseModel):
    """Polymarket market information."""
    id: str
    question: str
    slug: str
    description: str
    outcomes: list[str]
    outcome_prices: list[str] | None = None
    volume: str
    liquidity: str
    end_date: str
    active: bool
    closed: bool
    category: str
    image: str | None = None
    condition_id: str | None = None
    tokens: list[PolymarketToken] | None = None

    class Config:
        populate_by_name = True


class PolymarketEvent(BaseModel):
    """Polymarket event containing multiple markets."""
    id: str
    slug: str
    title: str
    description: str
    start_date: str
    end_date: str
    active: bool
    closed: bool
    markets: list[PolymarketMarket]
    tags: list[PolymarketTag] | None = None
    image: str | None = None

    class Config:
        populate_by_name = True


class PolymarketSeriesEvent(BaseModel):
    """Event stub as returned by the Gamma Series API (no nested markets)."""
    id: str
    slug: str
    title: str | None = None
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    active: bool = True
    closed: bool = False
    image: str | None = None


class PolymarketSeries(BaseModel):
    """Gamma API series response model."""
    id: str
    slug: str
    title: str | None = None
    description: str | None = None
    image: str | None = None
    icon: str | None = None
    series_type: str | None = Field(None, alias="seriesType")
    recurrence: str | None = None
    active: bool = True
    closed: bool = False
    events: list[PolymarketSeriesEvent] = Field(default_factory=list)

    class Config:
        populate_by_name = True


class MarketsResponse(BaseModel):
    """Response model for markets endpoint."""
    markets: list[PolymarketMarket]
    count: int
    source: Literal["live", "mock"]


class AnalyzeRequest(BaseModel):
    """Request model for market analysis."""
    market: PolymarketMarket
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


# ----- DB-backed persona–event integration -----


class PolymarketMarketRecord(BaseModel):
    """Stored Polymarket market (our DB row)."""
    id: str
    event_id: str
    condition_id: str | None = None
    question: str | None = None
    slug: str | None = None
    active: bool | None = None
    closed: bool | None = None
    outcome_prices: list[str] | None = None
    resolved_outcome: str | None = None
    closed_time: datetime | None = None
    resolution_source: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MarketSearchConfigRecord(BaseModel):
    """Stored search criteria for a market (LLM-parsed)."""
    id: str
    market_id: str
    search_terms: list[str] = Field(default_factory=list)
    min_count: int = 0
    logic: str = "at_least"
    created_at: datetime | None = None
    updated_at: datetime | None = None


class MarketSearchResultRecord(BaseModel):
    """Stored term-search result for a market + persona."""
    market_id: str
    persona_id: str
    count: int = 0
    last_updated: datetime | None = None


class PolymarketSeriesRecord(BaseModel):
    """Stored Polymarket series (our DB row)."""
    id: str
    polymarket_id: str
    slug: str
    title: str | None = None
    description: str | None = None
    image: str | None = None
    icon: str | None = None
    series_type: str | None = None
    recurrence: str | None = None
    active: bool = True
    closed: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PolymarketEventRecord(BaseModel):
    """Stored Polymarket event (our DB row)."""
    id: str
    slug: str
    title: str | None = None
    image: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    series_id: str | None = None
    polymarket_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AddEventRequest(BaseModel):
    """Request to add a Polymarket event to a persona by slug."""
    persona_id: str
    slug: str


class AddSeriesRequest(BaseModel):
    """Request to add a Polymarket series by slug."""
    slug: str


class LinkPersonaToSeriesRequest(BaseModel):
    """Request to link a persona to a series."""
    persona_id: str


class MarketWithAnalysis(BaseModel):
    """Market record with its search config and latest result count."""
    market: PolymarketMarketRecord
    search_config: MarketSearchConfigRecord | None = None
    result_count: int | None = None
    result_last_updated: datetime | None = None


class PersonaEventWithMarkets(BaseModel):
    """Event record with markets and their analysis results for a persona."""
    event: PolymarketEventRecord
    markets: list[MarketWithAnalysis] = Field(default_factory=list)
