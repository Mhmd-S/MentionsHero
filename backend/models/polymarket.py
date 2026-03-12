"""Polymarket-related Pydantic models."""

from datetime import datetime

from pydantic import BaseModel, Field


# ----- Polymarket API response models (Gamma API) -----


class PolyMarketAPI(BaseModel):
    """Market as returned by Polymarket Gamma API."""
    id: str
    slug: str | None = None
    question: str | None = None
    groupItemTitle: str | None = None
    outcomePrices: str | None = None  # JSON string e.g. '["0.45", "0.55"]'
    outcomes: str | None = None  # JSON string e.g. '["Yes", "No"]'
    lastTradePrice: float | None = None
    oneDayPriceChange: float | None = None
    volume: str | None = None
    active: bool = True
    closed: bool = False
    closedTime: str | None = None
    negRisk: bool = False

    class Config:
        populate_by_name = True


class PolyEventAPI(BaseModel):
    """Event as returned by Polymarket Gamma API."""
    id: str
    slug: str
    title: str | None = None
    description: str | None = None
    startDate: str | None = None
    endDate: str | None = None
    active: bool = True
    closed: bool = False
    volume: float | None = None
    liquidity: float | None = None
    image: str | None = None
    negRisk: bool = False
    markets: list[PolyMarketAPI] = Field(default_factory=list)

    class Config:
        populate_by_name = True


# ----- DB record models -----


class PolyEventRecord(BaseModel):
    """Stored Polymarket event (our DB row)."""
    id: str
    poly_id: str
    slug: str
    title: str | None = None
    description: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    active: bool = True
    closed: bool = False
    volume: float | None = None
    liquidity: float | None = None
    image: str | None = None
    neg_risk: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PolyMarketRecord(BaseModel):
    """Stored Polymarket market (our DB row)."""
    id: str
    poly_id: str
    event_id: str
    slug: str | None = None
    question: str | None = None
    group_item_title: str | None = None
    outcome_prices: list | None = None
    outcomes: list | None = None
    last_trade_price: float | None = None
    one_day_price_change: float | None = None
    volume: float | None = None
    active: bool = True
    closed: bool = False
    closed_time: datetime | None = None
    neg_risk: bool = False
    result: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


# ----- Request/Response models -----


class AddPolyEventRequest(BaseModel):
    """Request to add a Polymarket event by slug."""
    slug: str


class PolySearchResult(BaseModel):
    """Lightweight search result for Polymarket event discovery."""
    poly_id: str
    slug: str
    title: str | None = None
    image: str | None = None
    market_count: int = 0
    volume: float | None = None
    end_date: str | None = None
