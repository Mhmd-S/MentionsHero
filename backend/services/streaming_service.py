"""Trading session pipeline: download, transcribe, detect terms, and trade."""

import asyncio
import os
import re
import tempfile
from typing import Any

from backend.config import get_settings
from backend.core.database import get_supabase
from backend.core.exceptions import CancellationError
from backend.core.process_tracker import untrack_process
from backend.models.trading import (
    PositionStatus,
    SessionStatus,
    TradeTriggeredBy,
    TradingConfig,
)
from backend.services import trading_service
from backend.services.download_service import cleanup_audio_file, download_audio
from backend.services.transcription_service import transcribe_audio


class TermDetector:
    """Detects market-relevant terms in transcribed text."""

    def __init__(self, markets_with_terms: list[dict[str, Any]]):
        """
        Initialize with list of dicts:
        {
            "market_id": str,
            "token_id": str | None,
            "condition_id": str | None,
            "search_terms": list[str],
        }
        """
        self.markets = markets_with_terms
        self._triggered: set[tuple[str, str]] = set()  # (market_id, term) already fired

        # Pre-compile regex patterns
        self._patterns: list[tuple[dict[str, Any], str, re.Pattern]] = []
        for market in self.markets:
            for term in market.get("search_terms", []):
                pattern = re.compile(rf"\b{re.escape(term)}\b", re.IGNORECASE)
                self._patterns.append((market, term, pattern))

    def detect(self, text: str) -> list[dict[str, Any]]:
        """
        Detect terms in text. Returns list of detections:
        [{"market_id", "token_id", "condition_id", "term"}]

        Each market-term pair fires only once per session.
        """
        detections = []
        for market, term, pattern in self._patterns:
            key = (market["market_id"], term)
            if key in self._triggered:
                continue
            if pattern.search(text):
                self._triggered.add(key)
                detections.append({
                    "market_id": market["market_id"],
                    "token_id": market.get("token_id"),
                    "condition_id": market.get("condition_id"),
                    "term": term,
                })
        return detections


def _load_markets_for_session(
    persona_id: str, series_id: str, market_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Load active markets with search terms for a persona's series.

    If market_ids is non-empty, load those specific markets (active + not closed).
    Otherwise, get the newest event in the series and load all its active markets.
    """
    supabase = get_supabase()

    if market_ids:
        # Load specific markets by ID
        markets_data = []
        for mid in market_ids:
            rows = (
                supabase.table("polymarket_markets")
                .select("id, condition_id, active, closed, outcome_prices")
                .eq("id", mid)
                .eq("active", True)
                .eq("closed", False)
                .execute()
            )
            markets_data.extend(rows.data or [])
    else:
        # Get newest event in series (by end_date DESC, then created_at DESC)
        newest_event = (
            supabase.table("polymarket_events")
            .select("id")
            .eq("series_id", series_id)
            .order("end_date", desc=True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not newest_event.data:
            return []

        event_id = newest_event.data[0]["id"]
        rows = (
            supabase.table("polymarket_markets")
            .select("id, condition_id, active, closed, outcome_prices")
            .eq("event_id", event_id)
            .eq("active", True)
            .eq("closed", False)
            .execute()
        )
        markets_data = rows.data or []

    if not markets_data:
        return []

    # Get search configs and build term detector input
    result = []
    for market in markets_data:
        market_id = market["id"]
        cfg = (
            supabase.table("market_search_configs")
            .select("search_terms")
            .eq("market_id", market_id)
            .limit(1)
            .execute()
        )
        search_terms = (cfg.data[0].get("search_terms") or []) if cfg.data else []
        if not search_terms:
            continue

        condition_id = market.get("condition_id")
        result.append({
            "market_id": market_id,
            "token_id": condition_id,  # CLOB uses condition_id as token_id for YES
            "condition_id": condition_id,
            "search_terms": search_terms,
        })

    return result


async def run_trading_session(session_id: str) -> None:
    """
    Main orchestrator for a trading session.

    Pipeline:
    1. DOWNLOADING — download_audio() → mp3 file
    2. TRANSCRIBING — transcribe_audio() → full transcript text
    3. ANALYZING — TermDetector.detect() → execute buys
    4. Monitor positions until all closed or session stopped
    5. COMPLETED — close remaining positions
    """
    settings = get_settings()
    cancel_event = asyncio.Event()

    session = await trading_service.get_session(session_id)
    if not session:
        return

    config_data = session.get("config", {})
    # Extract market_ids from config before building TradingConfig
    market_ids = config_data.pop("market_ids", []) if isinstance(config_data, dict) else []
    config = TradingConfig(**config_data)
    persona_id = session["persona_id"]
    series_id = session.get("series_id", "")
    youtube_url = session["youtube_url"]

    # Load markets and search terms
    markets = _load_markets_for_session(persona_id, series_id, market_ids or None)
    if not markets:
        await trading_service.update_session(
            session_id,
            status=SessionStatus.FAILED,
            error_message="No active markets with search terms found for this series",
        )
        return

    await trading_service.log_event(session_id, "session_started", {
        "markets_loaded": len(markets),
        "total_terms": sum(len(m["search_terms"]) for m in markets),
        "config": config.model_dump(),
        "market_ids": market_ids,
    })

    progress = {
        "status_detail": "",
        "terms_detected": 0,
        "trades_placed": 0,
        "positions_open": 0,
        "transcript_preview": "",
    }

    downloads_dir = os.path.join(tempfile.gettempdir(), f"trading_{session_id}")
    os.makedirs(downloads_dir, exist_ok=True)
    audio_path: str | None = None

    try:
        # --- 1. DOWNLOADING ---
        await trading_service.update_session(
            session_id, status=SessionStatus.DOWNLOADING,
            stage_progress={**progress, "status_detail": "Downloading audio from YouTube..."},
        )

        audio_path = await download_audio(
            url=youtube_url,
            downloads_dir=downloads_dir,
            job_id=f"trading_{session_id}",
            cancel_event=cancel_event,
        )

        if await trading_service.check_cancellation(session_id):
            cancel_event.set()
            raise CancellationError("Session cancelled during download")

        await trading_service.log_event(session_id, "download_completed", {
            "audio_path": audio_path,
        })

        # --- 2. TRANSCRIBING ---
        await trading_service.update_session(
            session_id, status=SessionStatus.TRANSCRIBING,
            stage_progress={**progress, "status_detail": "Transcribing audio with Gemini..."},
        )

        transcript = await transcribe_audio(
            audio_path=audio_path,
            cancel_event=cancel_event,
        )

        if await trading_service.check_cancellation(session_id):
            cancel_event.set()
            raise CancellationError("Session cancelled during transcription")

        # Cleanup audio file now that we have the transcript
        await cleanup_audio_file(audio_path)
        audio_path = None

        await trading_service.log_event(session_id, "transcription_completed", {
            "text_length": len(transcript),
            "text_preview": transcript[:200],
        })

        progress["transcript_preview"] = transcript[:500]
        progress["status_detail"] = "Transcription complete"
        await trading_service.update_session(session_id, stage_progress=progress)

        # --- 3. ANALYZING ---
        await trading_service.update_session(
            session_id, status=SessionStatus.ANALYZING,
            stage_progress={**progress, "status_detail": "Detecting terms and placing trades..."},
        )

        term_detector = TermDetector(markets)
        detections = term_detector.detect(transcript)

        for detection in detections:
            progress["terms_detected"] += 1

            await trading_service.log_event(session_id, "term_detected", {
                "term": detection["term"],
                "market_id": detection["market_id"],
            })

            trade = await trading_service.execute_buy(
                session_id=session_id,
                market_id=detection["market_id"],
                token_id=detection["token_id"],
                condition_id=detection["condition_id"],
                detected_term=detection["term"],
                config=config,
            )
            if trade and trade.get("status") != "failed":
                progress["trades_placed"] += 1

        open_positions = await trading_service.get_open_positions(session_id)
        progress["positions_open"] = len(open_positions)
        progress["status_detail"] = f"Analysis complete — {progress['terms_detected']} terms, {progress['trades_placed']} trades"
        await trading_service.update_session(session_id, stage_progress=progress)

        await trading_service.log_event(session_id, "analysis_completed", {
            "terms_detected": progress["terms_detected"],
            "trades_placed": progress["trades_placed"],
        })

        # --- 4. POSITION MONITOR ---
        if progress["positions_open"] > 0:
            progress["status_detail"] = "Monitoring positions..."
            await trading_service.update_session(session_id, stage_progress=progress)

            while not cancel_event.is_set():
                await asyncio.sleep(config.price_poll_interval_s)

                if cancel_event.is_set():
                    break

                if await trading_service.check_cancellation(session_id):
                    cancel_event.set()
                    break

                closed = await trading_service.check_and_sell_positions(session_id, config)
                open_positions = await trading_service.get_open_positions(session_id)
                progress["positions_open"] = len(open_positions)

                if closed > 0:
                    await trading_service.update_session(session_id, stage_progress=progress)

                if len(open_positions) == 0:
                    break

        # --- 5. COMPLETED ---
        closed = await trading_service.close_all_positions(
            session_id, TradeTriggeredBy.SESSION_END
        )

        final_status = SessionStatus.COMPLETED
        if cancel_event.is_set() or await trading_service.check_cancellation(session_id):
            final_status = SessionStatus.CANCELLED

        progress["positions_open"] = 0
        progress["status_detail"] = "Session complete"
        await trading_service.update_session(
            session_id,
            status=final_status,
            stage_progress=progress,
        )

        await trading_service.log_event(session_id, "session_completed", {
            "positions_closed_at_end": closed,
            "final_progress": progress,
        })

    except CancellationError:
        await trading_service.close_all_positions(session_id, TradeTriggeredBy.SESSION_END)
        await trading_service.update_session(session_id, status=SessionStatus.CANCELLED)
        await trading_service.log_event(session_id, "session_cancelled", {})

    except Exception as e:
        await trading_service.close_all_positions(session_id, TradeTriggeredBy.SESSION_END)
        await trading_service.update_session(
            session_id,
            status=SessionStatus.FAILED,
            error_message=str(e),
        )
        await trading_service.log_event(session_id, "session_failed", {
            "error": str(e),
        })

    finally:
        # Cleanup audio if still around
        if audio_path:
            try:
                await cleanup_audio_file(audio_path)
            except Exception:
                pass
        # Cleanup temp dir
        try:
            import shutil
            shutil.rmtree(downloads_dir, ignore_errors=True)
        except Exception:
            pass
        untrack_process(f"trading_{session_id}")
        trading_service.cleanup_session_event(session_id)
