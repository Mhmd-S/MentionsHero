"""Pydantic models for the trading bot feature."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SessionStatus(str, Enum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TradeStatus(str, Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    FAILED = "failed"


class TradeSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class TradeTriggeredBy(str, Enum):
    TERM_DETECTION = "term_detection"
    PROFIT_TARGET = "profit_target"
    STOP_LOSS = "stop_loss"
    MARKET_CLOSE = "market_close"
    SESSION_END = "session_end"


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED_PROFIT = "closed_profit"
    CLOSED_LOSS = "closed_loss"
    CLOSED_MARKET = "closed_market"
    CLOSED_SESSION = "closed_session"


class TradingConfig(BaseModel):
    """Session configuration with sensible defaults."""

    profit_target_pct: float = Field(default=30.0, ge=1.0, le=200.0)
    stop_loss_pct: float = Field(default=20.0, ge=1.0, le=100.0)
    max_price_to_buy: float = Field(default=0.90, ge=0.01, le=0.99)
    buy_amount_usd: float = Field(default=5.0, ge=1.0, le=100.0)
    max_concurrent_positions: int = Field(default=10, ge=1, le=50)
    price_poll_interval_s: int = Field(default=10, ge=5, le=60)


class StartSessionRequest(BaseModel):
    """Request to start a new trading session."""

    youtube_url: str
    persona_id: str
    series_id: str
    market_ids: list[str] = []  # empty = all markets in newest event
    video_title: str | None = None
    config: TradingConfig = Field(default_factory=TradingConfig)


class StartSessionResponse(BaseModel):
    """Response after starting a trading session."""

    session_id: str
    status: SessionStatus


class StopSessionResponse(BaseModel):
    """Response after stopping a trading session."""

    success: bool
    message: str


class StartSimulationRequest(BaseModel):
    """Request to start a simulation session against a past event."""

    youtube_url: str
    persona_id: str
    series_id: str
    event_id: str
    market_ids: list[str] = []
    video_title: str | None = None
    config: TradingConfig = Field(default_factory=TradingConfig)


class SimulationReport(BaseModel):
    """P&L report for a completed simulation."""

    total_pnl_usd: float = 0.0
    total_pnl_pct: float = 0.0
    win_rate: float = 0.0
    total_positions: int = 0
    winning_positions: int = 0
    losing_positions: int = 0
    pipeline_duration_s: float = 0.0
    transcript_download_duration_s: float = 0.0
    analysis_duration_s: float = 0.0
    per_market: list[dict[str, Any]] = Field(default_factory=list)


class TimelineEvent(BaseModel):
    """A single event in the simulation timeline."""

    id: str | None = None
    event_type: str
    simulated_timestamp: int
    wall_clock_timestamp: str | None = None
    market_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
