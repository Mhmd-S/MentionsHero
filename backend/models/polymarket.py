"""Polymarket-related Pydantic models."""

from typing import Literal

from pydantic import BaseModel


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
