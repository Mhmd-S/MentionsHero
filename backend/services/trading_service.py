"""Trading service for Polymarket CLOB API interactions."""

import threading
from datetime import datetime, timezone
from typing import Any

from backend.config import get_settings
from backend.core.database import get_supabase
from backend.core.exceptions import TradingError
from backend.models.trading import (
    PositionStatus,
    SessionStatus,
    TradeSide,
    TradeStatus,
    TradeTriggeredBy,
    TradingConfig,
)
from backend.services.polymarket_service import get_token_price

# SSE events for trading sessions (same pattern as job_service.py)
_session_events: dict[str, threading.Event] = {}


def get_session_event(session_id: str) -> threading.Event:
    """Get or create a threading.Event for SSE notification."""
    if session_id not in _session_events:
        _session_events[session_id] = threading.Event()
    return _session_events[session_id]


def notify_session_changed(session_id: str) -> None:
    """Signal that session data has changed, waking up SSE listeners."""
    get_session_event(session_id).set()


def cleanup_session_event(session_id: str) -> None:
    """Remove session event after session ends."""
    _session_events.pop(session_id, None)


# Lazy-initialized CLOB client
_clob_client = None


def _get_clob_client():
    """Lazily initialize the py-clob-client ClobClient."""
    global _clob_client
    if _clob_client is not None:
        return _clob_client

    settings = get_settings()
    if not settings.polymarket_api_key or not settings.polymarket_private_key:
        raise TradingError("Polymarket API credentials not configured")

    try:
        from py_clob_client.client import ClobClient

        _clob_client = ClobClient(
            host="https://clob.polymarket.com",
            key=settings.polymarket_private_key,
            chain_id=settings.polymarket_chain_id,
            creds=ClobClient.derive_api_creds(
                ClobClient(
                    host="https://clob.polymarket.com",
                    key=settings.polymarket_private_key,
                    chain_id=settings.polymarket_chain_id,
                )
            ),
        )
        return _clob_client
    except Exception as e:
        raise TradingError(f"Failed to initialize CLOB client: {e}")


async def create_session(
    youtube_url: str,
    persona_id: str,
    series_id: str,
    config: TradingConfig,
    market_ids: list[str] | None = None,
    video_title: str | None = None,
) -> dict[str, Any]:
    """Create a new trading session in the database."""
    supabase = get_supabase()

    # Store market_ids alongside trading config in the config JSONB
    config_data = config.model_dump()
    if market_ids:
        config_data["market_ids"] = market_ids

    response = supabase.table("trading_sessions").insert({
        "youtube_url": youtube_url,
        "video_title": video_title,
        "persona_id": persona_id,
        "series_id": series_id,
        "status": SessionStatus.PENDING.value,
        "config": config_data,
        "stage_progress": {
            "status_detail": "",
            "terms_detected": 0,
            "trades_placed": 0,
            "positions_open": 0,
            "transcript_preview": "",
        },
    }).execute()

    return response.data[0]


async def get_session(session_id: str) -> dict[str, Any] | None:
    """Get a trading session by ID."""
    supabase = get_supabase()
    response = supabase.table("trading_sessions").select("*").eq("id", session_id).single().execute()
    return response.data


async def get_active_session() -> dict[str, Any] | None:
    """Get the currently active trading session (if any)."""
    supabase = get_supabase()
    active_statuses = (
        f"({SessionStatus.PENDING.value},{SessionStatus.DOWNLOADING.value},"
        f"{SessionStatus.TRANSCRIBING.value},{SessionStatus.ANALYZING.value})"
    )
    response = (
        supabase.table("trading_sessions")
        .select("*")
        .filter("status", "in", active_statuses)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


async def get_session_history(limit: int = 20) -> list[dict[str, Any]]:
    """Get past trading sessions."""
    supabase = get_supabase()
    response = (
        supabase.table("trading_sessions")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


async def update_session(
    session_id: str,
    status: SessionStatus | None = None,
    stage_progress: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> None:
    """Update a trading session."""
    supabase = get_supabase()
    update_data: dict[str, Any] = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if status is not None:
        update_data["status"] = status.value
        if status == SessionStatus.DOWNLOADING:
            update_data["started_at"] = datetime.now(timezone.utc).isoformat()
        elif status in (SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.CANCELLED):
            update_data["ended_at"] = datetime.now(timezone.utc).isoformat()
    if stage_progress is not None:
        update_data["stage_progress"] = stage_progress
    if error_message is not None:
        update_data["error_message"] = error_message

    supabase.table("trading_sessions").update(update_data).eq("id", session_id).execute()
    notify_session_changed(session_id)


async def check_cancellation(session_id: str) -> bool:
    """Check if cancellation has been requested."""
    supabase = get_supabase()
    response = (
        supabase.table("trading_sessions")
        .select("cancel_requested")
        .eq("id", session_id)
        .single()
        .execute()
    )
    if response.data:
        return response.data.get("cancel_requested", False)
    return False


async def request_cancellation(session_id: str) -> bool:
    """Request cancellation of a session."""
    session = await get_session(session_id)
    if not session:
        return False
    terminal = [SessionStatus.COMPLETED.value, SessionStatus.FAILED.value, SessionStatus.CANCELLED.value]
    if session.get("status") in terminal:
        return False
    supabase = get_supabase()
    supabase.table("trading_sessions").update({
        "cancel_requested": True,
    }).eq("id", session_id).execute()
    notify_session_changed(session_id)
    return True


async def log_event(session_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
    """Write an event to the trading session log."""
    supabase = get_supabase()
    supabase.table("trading_session_log").insert({
        "session_id": session_id,
        "event_type": event_type,
        "payload": payload or {},
    }).execute()
    notify_session_changed(session_id)


async def get_session_logs(session_id: str, limit: int = 100) -> list[dict[str, Any]]:
    """Get recent logs for a session."""
    supabase = get_supabase()
    response = (
        supabase.table("trading_session_log")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return response.data or []


async def get_session_trades(session_id: str) -> list[dict[str, Any]]:
    """Get all trades for a session."""
    supabase = get_supabase()
    response = (
        supabase.table("trades")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


async def get_session_positions(session_id: str) -> list[dict[str, Any]]:
    """Get all positions for a session."""
    supabase = get_supabase()
    response = (
        supabase.table("trading_positions")
        .select("*")
        .eq("session_id", session_id)
        .order("created_at", desc=True)
        .execute()
    )
    return response.data or []


async def get_open_positions(session_id: str) -> list[dict[str, Any]]:
    """Get open positions for a session."""
    supabase = get_supabase()
    response = (
        supabase.table("trading_positions")
        .select("*")
        .eq("session_id", session_id)
        .eq("status", PositionStatus.OPEN.value)
        .execute()
    )
    return response.data or []


async def execute_buy(
    session_id: str,
    market_id: str,
    token_id: str,
    condition_id: str | None,
    detected_term: str,
    config: TradingConfig,
) -> dict[str, Any] | None:
    """
    Execute a buy trade for a detected term.

    Pre-checks: trading enabled, market active, no existing position, price < max, positions < max.
    Returns the created trade record, or None if skipped.
    """
    settings = get_settings()
    supabase = get_supabase()

    # Check trading enabled
    if not settings.trading_enabled:
        await log_event(session_id, "buy_skipped", {
            "reason": "trading_disabled",
            "market_id": market_id,
            "term": detected_term,
        })
        return None

    # Check no existing open position for this market
    existing = (
        supabase.table("trading_positions")
        .select("id")
        .eq("session_id", session_id)
        .eq("market_id", market_id)
        .eq("status", PositionStatus.OPEN.value)
        .limit(1)
        .execute()
    )
    if existing.data:
        await log_event(session_id, "buy_skipped", {
            "reason": "position_already_open",
            "market_id": market_id,
            "term": detected_term,
        })
        return None

    # Check max concurrent positions
    open_positions = await get_open_positions(session_id)
    if len(open_positions) >= config.max_concurrent_positions:
        await log_event(session_id, "buy_skipped", {
            "reason": "max_positions_reached",
            "market_id": market_id,
            "term": detected_term,
            "current": len(open_positions),
            "max": config.max_concurrent_positions,
        })
        return None

    # Get current price
    current_price = await get_token_price(token_id, "buy") if token_id else None
    if current_price is None:
        await log_event(session_id, "buy_skipped", {
            "reason": "price_unavailable",
            "market_id": market_id,
            "term": detected_term,
        })
        return None

    # Check price not too high
    if current_price > config.max_price_to_buy:
        await log_event(session_id, "buy_skipped", {
            "reason": "price_too_high",
            "market_id": market_id,
            "term": detected_term,
            "price": current_price,
            "max_price": config.max_price_to_buy,
        })
        return None

    # Check market is still active
    market_row = supabase.table("polymarket_markets").select("active, closed").eq("id", market_id).single().execute()
    if market_row.data and (market_row.data.get("closed") or not market_row.data.get("active")):
        await log_event(session_id, "buy_skipped", {
            "reason": "market_closed",
            "market_id": market_id,
            "term": detected_term,
        })
        return None

    # Calculate shares
    shares = config.buy_amount_usd / current_price if current_price > 0 else 0

    # Execute trade (dry-run or real)
    order_id = "DRY_RUN"
    trade_status = TradeStatus.FILLED

    if not settings.trading_dry_run:
        try:
            client = _get_clob_client()
            from py_clob_client.order_builder.constants import BUY
            order = client.create_and_post_order({
                "token_id": token_id,
                "price": current_price,
                "size": shares,
                "side": BUY,
            })
            order_id = order.get("orderID", order.get("id", "unknown"))
            trade_status = TradeStatus.SUBMITTED
        except Exception as e:
            # Record failed trade
            trade_row = supabase.table("trades").insert({
                "session_id": session_id,
                "market_id": market_id,
                "token_id": token_id,
                "condition_id": condition_id,
                "side": TradeSide.BUY.value,
                "amount_usd": config.buy_amount_usd,
                "price": current_price,
                "shares": shares,
                "order_id": None,
                "status": TradeStatus.FAILED.value,
                "triggered_by": TradeTriggeredBy.TERM_DETECTION.value,
                "detected_term": detected_term,
            }).execute()

            await log_event(session_id, "buy_failed", {
                "market_id": market_id,
                "term": detected_term,
                "error": str(e),
            })
            return trade_row.data[0] if trade_row.data else None

    # Record the trade
    trade_row = supabase.table("trades").insert({
        "session_id": session_id,
        "market_id": market_id,
        "token_id": token_id,
        "condition_id": condition_id,
        "side": TradeSide.BUY.value,
        "amount_usd": config.buy_amount_usd,
        "price": current_price,
        "shares": shares,
        "order_id": order_id,
        "status": trade_status.value,
        "triggered_by": TradeTriggeredBy.TERM_DETECTION.value,
        "detected_term": detected_term,
    }).execute()

    trade = trade_row.data[0] if trade_row.data else None
    if not trade:
        return None

    # Create open position
    supabase.table("trading_positions").insert({
        "session_id": session_id,
        "market_id": market_id,
        "token_id": token_id,
        "buy_trade_id": trade["id"],
        "buy_price": current_price,
        "shares": shares,
        "current_price": current_price,
        "status": PositionStatus.OPEN.value,
    }).execute()

    await log_event(session_id, "buy_executed", {
        "market_id": market_id,
        "term": detected_term,
        "price": current_price,
        "shares": shares,
        "amount_usd": config.buy_amount_usd,
        "order_id": order_id,
        "dry_run": settings.trading_dry_run,
    })

    return trade


async def check_and_sell_positions(session_id: str, config: TradingConfig) -> int:
    """
    Check all open positions for sell conditions.

    Returns the number of positions closed.
    """
    positions = await get_open_positions(session_id)
    closed_count = 0

    for position in positions:
        token_id = position.get("token_id")
        if not token_id:
            continue

        # Get current price
        current_price = await get_token_price(token_id, "sell")
        if current_price is None:
            continue

        # Update current price
        supabase = get_supabase()
        supabase.table("trading_positions").update({
            "current_price": current_price,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", position["id"]).execute()

        buy_price = float(position.get("buy_price", 0))
        if buy_price <= 0:
            continue

        pnl_pct = ((current_price - buy_price) / buy_price) * 100

        # Check market closed
        market_id = position.get("market_id")
        if market_id:
            market_row = supabase.table("polymarket_markets").select("closed").eq("id", market_id).single().execute()
            if market_row.data and market_row.data.get("closed"):
                await _execute_sell(session_id, position, TradeTriggeredBy.MARKET_CLOSE, config, current_price, pnl_pct)
                closed_count += 1
                continue

        # Check profit target
        if pnl_pct >= config.profit_target_pct:
            await _execute_sell(session_id, position, TradeTriggeredBy.PROFIT_TARGET, config, current_price, pnl_pct)
            closed_count += 1
            continue

        # Check stop loss
        if pnl_pct <= -config.stop_loss_pct:
            await _execute_sell(session_id, position, TradeTriggeredBy.STOP_LOSS, config, current_price, pnl_pct)
            closed_count += 1
            continue

    return closed_count


async def _execute_sell(
    session_id: str,
    position: dict[str, Any],
    reason: TradeTriggeredBy,
    config: TradingConfig,
    current_price: float,
    pnl_pct: float,
) -> None:
    """Execute a sell for a position."""
    settings = get_settings()
    supabase = get_supabase()

    shares = float(position.get("shares", 0))
    amount_usd = shares * current_price
    token_id = position.get("token_id")
    market_id = position.get("market_id")

    order_id = "DRY_RUN"
    trade_status = TradeStatus.FILLED

    if not settings.trading_dry_run:
        try:
            client = _get_clob_client()
            from py_clob_client.order_builder.constants import SELL
            order = client.create_and_post_order({
                "token_id": token_id,
                "price": current_price,
                "size": shares,
                "side": SELL,
            })
            order_id = order.get("orderID", order.get("id", "unknown"))
            trade_status = TradeStatus.SUBMITTED
        except Exception as e:
            await log_event(session_id, "sell_failed", {
                "position_id": position["id"],
                "market_id": market_id,
                "reason": reason.value,
                "error": str(e),
            })
            return

    # Record sell trade
    trade_row = supabase.table("trades").insert({
        "session_id": session_id,
        "market_id": market_id,
        "token_id": token_id,
        "condition_id": position.get("condition_id"),
        "side": TradeSide.SELL.value,
        "amount_usd": amount_usd,
        "price": current_price,
        "shares": shares,
        "order_id": order_id,
        "status": trade_status.value,
        "triggered_by": reason.value,
    }).execute()

    sell_trade_id = trade_row.data[0]["id"] if trade_row.data else None

    # Map reason to position status
    status_map = {
        TradeTriggeredBy.PROFIT_TARGET: PositionStatus.CLOSED_PROFIT,
        TradeTriggeredBy.STOP_LOSS: PositionStatus.CLOSED_LOSS,
        TradeTriggeredBy.MARKET_CLOSE: PositionStatus.CLOSED_MARKET,
        TradeTriggeredBy.SESSION_END: PositionStatus.CLOSED_SESSION,
    }
    position_status = status_map.get(reason, PositionStatus.CLOSED_SESSION)

    # Update position
    supabase.table("trading_positions").update({
        "status": position_status.value,
        "sell_trade_id": sell_trade_id,
        "current_price": current_price,
        "profit_loss_pct": pnl_pct,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", position["id"]).execute()

    await log_event(session_id, "sell_executed", {
        "position_id": position["id"],
        "market_id": market_id,
        "reason": reason.value,
        "price": current_price,
        "pnl_pct": round(pnl_pct, 2),
        "shares": shares,
        "order_id": order_id,
        "dry_run": settings.trading_dry_run,
    })


async def close_all_positions(session_id: str, reason: TradeTriggeredBy) -> int:
    """Close all open positions at session end."""
    positions = await get_open_positions(session_id)
    closed_count = 0

    for position in positions:
        token_id = position.get("token_id")
        current_price = await get_token_price(token_id, "sell") if token_id else None
        if current_price is None:
            current_price = float(position.get("current_price", 0))

        buy_price = float(position.get("buy_price", 0))
        pnl_pct = ((current_price - buy_price) / buy_price) * 100 if buy_price > 0 else 0

        config = TradingConfig()  # defaults are fine for session-end sells
        await _execute_sell(session_id, position, reason, config, current_price, pnl_pct)
        closed_count += 1

    return closed_count


async def get_session_detail(session_id: str) -> dict[str, Any] | None:
    """Get full session detail with trades, positions, and logs."""
    session = await get_session(session_id)
    if not session:
        return None

    trades = await get_session_trades(session_id)
    positions = await get_session_positions(session_id)
    logs = await get_session_logs(session_id)

    return {
        "session": session,
        "trades": trades,
        "positions": positions,
        "logs": logs,
    }
