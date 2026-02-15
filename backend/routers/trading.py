"""Trading bot API routes."""

import asyncio
import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse

from backend.config import get_settings
from backend.core.database import get_supabase
from backend.core.process_tracker import cancel_process
from backend.models.trading import (
    SessionStatus,
    StartSessionRequest,
    StartSessionResponse,
    StopSessionResponse,
)
from backend.services import trading_service, polymarket_service
from backend.services.channel_monitor_service import get_monitor_status
from backend.services.streaming_service import run_trading_session

router = APIRouter(prefix="/api/trading", tags=["trading"])


# Static routes first (per convention)


@router.get("/markets-for-series")
async def get_markets_for_series(series_id: str = Query(...)) -> dict[str, Any]:
    """Get newest event + its markets with search terms for the trading form UI."""
    supabase = get_supabase()

    # Get newest event in series
    newest_event = (
        supabase.table("polymarket_events")
        .select("*")
        .eq("series_id", series_id)
        .order("end_date", desc=True)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not newest_event.data:
        return {"event": None, "markets": []}

    event = newest_event.data[0]

    # Get all markets for this event
    markets_rows = (
        supabase.table("polymarket_markets")
        .select("id, condition_id, question, slug, active, closed, outcome_prices, resolved_outcome")
        .eq("event_id", event["id"])
        .execute()
    )
    markets = markets_rows.data or []

    # Attach search terms to each market
    for market in markets:
        cfg = (
            supabase.table("market_search_configs")
            .select("search_terms")
            .eq("market_id", market["id"])
            .limit(1)
            .execute()
        )
        market["search_terms"] = (cfg.data[0].get("search_terms") or []) if cfg.data else []

    return {"event": event, "markets": markets}


@router.get("/channel-monitor/status")
async def channel_monitor_status() -> dict[str, Any]:
    """Get the current status of the channel monitor."""
    return get_monitor_status()


@router.post("/channel-monitor/auto-trade")
async def toggle_auto_trade(
    persona_id: str = Query(...),
    series_id: str = Query(...),
    enabled: bool = Query(...),
) -> dict[str, Any]:
    """Toggle auto_trade on a persona-series link."""
    success = await polymarket_service.set_auto_trade(persona_id, series_id, enabled)
    if not success:
        raise HTTPException(status_code=404, detail="Persona-series link not found")
    return {"success": True, "auto_trade": enabled}


@router.get("/active")
async def get_active_session() -> dict[str, Any]:
    """Get the currently active trading session."""
    session = await trading_service.get_active_session()
    return {"session": session}


@router.get("/history")
async def get_session_history() -> dict[str, list[dict[str, Any]]]:
    """List past trading sessions."""
    sessions = await trading_service.get_session_history()
    return {"sessions": sessions}


@router.post("/start")
async def start_session(
    request: StartSessionRequest,
    background_tasks: BackgroundTasks,
) -> StartSessionResponse:
    """Start a new live trading session."""
    settings = get_settings()

    # Check trading is enabled
    if not settings.trading_enabled:
        raise HTTPException(
            status_code=400,
            detail="Trading is not enabled. Set TRADING_ENABLED=true to enable.",
        )

    # Check no existing active session
    existing = await trading_service.get_active_session()
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Active session already exists: {existing['id']}",
        )

    # Create session
    session = await trading_service.create_session(
        youtube_url=request.youtube_url,
        persona_id=request.persona_id,
        series_id=request.series_id,
        config=request.config,
        market_ids=request.market_ids or None,
        video_title=request.video_title,
    )

    # Launch background processing
    background_tasks.add_task(run_trading_session, session["id"])

    return StartSessionResponse(
        session_id=session["id"],
        status=SessionStatus.PENDING,
    )


@router.post("/stop")
async def stop_session() -> StopSessionResponse:
    """Stop the active trading session."""
    session = await trading_service.get_active_session()
    if not session:
        raise HTTPException(status_code=404, detail="No active session")

    # Request cancellation
    await trading_service.request_cancellation(session["id"])

    # Kill yt-dlp process
    cancel_process(f"trading_{session['id']}")

    return StopSessionResponse(success=True, message="Stop requested")


# Parameterized routes


@router.get("/{session_id}")
async def get_session_detail(session_id: str) -> dict[str, Any]:
    """Get full session detail with trades, positions, and logs."""
    detail = await trading_service.get_session_detail(session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Session not found")
    return detail


@router.get("/{session_id}/stream")
async def stream_session(session_id: str):
    """Stream session updates via Server-Sent Events."""
    session = await trading_service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session_event = trading_service.get_session_event(session_id)
    wait_timeout = 5.0

    async def event_generator():
        # Send initial state
        detail = await trading_service.get_session_detail(session_id)
        yield f"data: {json.dumps(detail)}\n\n"

        while True:
            try:
                session_event.clear()
                await asyncio.wait_for(
                    asyncio.shield(asyncio.to_thread(session_event.wait)),
                    timeout=wait_timeout,
                )
            except asyncio.TimeoutError:
                # Heartbeat — send current state
                pass
            except asyncio.CancelledError:
                break
            except Exception:
                break

            detail = await trading_service.get_session_detail(session_id)
            if not detail:
                break
            yield f"data: {json.dumps(detail)}\n\n"

            # Stop streaming if session is in terminal state
            status = detail.get("session", {}).get("status")
            if status in (
                SessionStatus.COMPLETED.value,
                SessionStatus.FAILED.value,
                SessionStatus.CANCELLED.value,
            ):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
