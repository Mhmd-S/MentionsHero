"""Background YouTube channel monitor for auto-starting trading sessions."""

import asyncio
import logging
from typing import Any

from backend.config import get_settings
from backend.core.database import get_supabase
from backend.models.trading import TradingConfig
from backend.services import trading_service
from backend.services.streaming_service import run_trading_session

logger = logging.getLogger(__name__)

_monitor_task: asyncio.Task | None = None
_last_video_ids: dict[str, str] = {}  # persona_id → last known video ID


def _get_personas_with_channels() -> list[dict[str, Any]]:
    """Query personas that have a youtube_channel_url set."""
    supabase = get_supabase()
    response = (
        supabase.table("personas")
        .select("id, name, youtube_channel_url")
        .neq("youtube_channel_url", None)
        .execute()
    )
    return [r for r in (response.data or []) if r.get("youtube_channel_url")]


def _get_auto_trade_series(persona_id: str) -> list[dict[str, str]]:
    """Get series with auto_trade=true for a persona."""
    supabase = get_supabase()
    links = (
        supabase.table("persona_polymarket_series")
        .select("polymarket_series_id")
        .eq("persona_id", persona_id)
        .eq("auto_trade", True)
        .execute()
    )
    return links.data or []


async def _get_latest_video_id(channel_url: str) -> str | None:
    """Get the latest video ID from a YouTube channel using yt-dlp."""
    try:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--flat-playlist",
            "--playlist-items", "1",
            "--print", "id",
            "--no-download",
            channel_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        if proc.returncode == 0 and stdout:
            video_id = stdout.decode().strip().split("\n")[0]
            return video_id if video_id else None
        if stderr:
            logger.warning("yt-dlp stderr for %s: %s", channel_url, stderr.decode()[:200])
        return None
    except asyncio.TimeoutError:
        logger.warning("yt-dlp timed out for channel: %s", channel_url)
        return None
    except Exception as e:
        logger.warning("Failed to get latest video for %s: %s", channel_url, e)
        return None


async def _seed_initial_state() -> None:
    """On startup, record the current latest video per persona (no trigger)."""
    personas = _get_personas_with_channels()
    for persona in personas:
        channel_url = persona["youtube_channel_url"]
        video_id = await _get_latest_video_id(channel_url)
        if video_id:
            _last_video_ids[persona["id"]] = video_id
            logger.info(
                "Channel monitor seeded %s (%s) → video %s",
                persona["name"], channel_url, video_id,
            )


async def _auto_start_session(persona_id: str, persona_name: str, series_id: str, video_id: str) -> None:
    """Auto-create and start a trading session for a new video."""
    youtube_url = f"https://www.youtube.com/watch?v={video_id}"

    # Check no active session already
    existing = await trading_service.get_active_session()
    if existing:
        logger.info(
            "Channel monitor: skipping auto-start for %s — active session %s exists",
            persona_name, existing["id"],
        )
        return

    session = await trading_service.create_session(
        youtube_url=youtube_url,
        persona_id=persona_id,
        series_id=series_id,
        config=TradingConfig(),
        market_ids=None,  # all markets from newest event
    )

    await trading_service.log_event(session["id"], "auto_started", {
        "persona_name": persona_name,
        "video_id": video_id,
        "series_id": series_id,
    })

    logger.info(
        "Channel monitor: auto-started session %s for %s (video %s)",
        session["id"], persona_name, video_id,
    )

    # Launch the trading pipeline
    asyncio.create_task(run_trading_session(session["id"]))


async def _monitor_loop() -> None:
    """Main poll loop for the channel monitor."""
    settings = get_settings()
    interval = settings.channel_poll_interval_s

    logger.info("Channel monitor starting — seeding initial state...")
    await _seed_initial_state()
    logger.info("Channel monitor active — polling every %ds", interval)

    while True:
        await asyncio.sleep(interval)
        try:
            personas = _get_personas_with_channels()
            for persona in personas:
                pid = persona["id"]
                channel_url = persona["youtube_channel_url"]

                video_id = await _get_latest_video_id(channel_url)
                if not video_id:
                    continue

                last_known = _last_video_ids.get(pid)
                if video_id == last_known:
                    continue

                # New video detected
                _last_video_ids[pid] = video_id
                logger.info(
                    "Channel monitor: new video detected for %s — %s (was %s)",
                    persona["name"], video_id, last_known,
                )

                # Check if persona has auto_trade series
                auto_series = _get_auto_trade_series(pid)
                if not auto_series:
                    logger.info("Channel monitor: no auto_trade series for %s, skipping", persona["name"])
                    continue

                # Use first auto_trade series
                series_id = auto_series[0]["polymarket_series_id"]
                await _auto_start_session(pid, persona["name"], series_id, video_id)

        except Exception as e:
            logger.error("Channel monitor error: %s", e, exc_info=True)


async def start_monitor() -> None:
    """Start the channel monitor background task."""
    global _monitor_task
    if _monitor_task and not _monitor_task.done():
        logger.warning("Channel monitor already running")
        return
    _monitor_task = asyncio.create_task(_monitor_loop())
    logger.info("Channel monitor task created")


async def stop_monitor() -> None:
    """Stop the channel monitor background task."""
    global _monitor_task
    if _monitor_task and not _monitor_task.done():
        _monitor_task.cancel()
        try:
            await _monitor_task
        except asyncio.CancelledError:
            pass
        logger.info("Channel monitor stopped")
    _monitor_task = None


def get_monitor_status() -> dict[str, Any]:
    """Get the current status of the channel monitor."""
    running = _monitor_task is not None and not _monitor_task.done()
    return {
        "running": running,
        "watched_personas": len(_last_video_ids),
        "last_video_ids": dict(_last_video_ids),
    }
