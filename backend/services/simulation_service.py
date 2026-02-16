"""Simulation pipeline: re-process a video against resolved past events with historical prices."""

import json
import os
import re
import subprocess
import tempfile
import time
from typing import Any

from backend.core.database import get_supabase
from backend.core.process_tracker import untrack_process
from backend.models.trading import (
    PositionStatus,
    SessionStatus,
    TradeSide,
    TradeStatus,
    TradeTriggeredBy,
    TradingConfig,
)
from backend.services import trading_service
from backend.services.price_history_service import (
    fetch_price_history,
    get_price_at_timestamp,
)
from backend.services.streaming_service import TermDetector


def _get_video_info(youtube_url: str) -> dict[str, Any]:
    """Use yt-dlp --dump-json to get video metadata including upload timestamp."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--dump-json", "--no-download", youtube_url],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return {}
        return json.loads(result.stdout)
    except Exception as e:
        print(f"[simulation] Failed to get video info: {e}")
        return {}


def _extract_upload_timestamp(info: dict[str, Any]) -> int | None:
    """Extract upload timestamp from yt-dlp video info."""
    ts = info.get("timestamp")
    if ts:
        return int(ts)
    upload_date = info.get("upload_date")
    if upload_date:
        from datetime import datetime, timezone
        dt = datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    return None


def _download_transcript(youtube_url: str, work_dir: str) -> str | None:
    """
    Download YouTube auto-generated subtitles via yt-dlp and clean to plain text.

    Uses --skip-download to avoid downloading audio/video.
    Downloads auto-subs in SRT format, strips timestamps/numbering/tags.
    """
    output_template = os.path.join(work_dir, "transcript.%(ext)s")
    srt_path = os.path.join(work_dir, "transcript.en.srt")
    output_path = os.path.join(work_dir, "output.txt")

    try:
        # Download subtitles
        result = subprocess.run(
            [
                "yt-dlp",
                "--skip-download",
                "--write-subs",
                "--write-auto-subs",
                "--sub-lang", "en",
                "--sub-format", "ttml",
                "--convert-subs", "srt",
                "--output", output_template,
                youtube_url,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=work_dir,
        )
        if result.returncode != 0:
            print(f"[simulation] yt-dlp subtitle download failed: {result.stderr}")
            return None

        if not os.path.exists(srt_path):
            print(f"[simulation] SRT file not found at {srt_path}")
            return None

        # Read and clean the SRT file in Python (portable, no sed dependency issues)
        with open(srt_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip sequence numbers (pure digits)
            if re.match(r"^\d{1,4}$", stripped):
                continue
            # Skip timestamp lines
            if re.match(r"^\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}", stripped):
                continue
            # Strip HTML/XML tags
            cleaned = re.sub(r"<[^>]*>", "", stripped)
            if cleaned:
                cleaned_lines.append(cleaned)

        transcript = "\n".join(cleaned_lines)

        # Write output file and cleanup SRT
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(transcript)
        try:
            os.remove(srt_path)
        except OSError:
            pass

        return transcript

    except subprocess.TimeoutExpired:
        print("[simulation] yt-dlp subtitle download timed out")
        return None
    except Exception as e:
        print(f"[simulation] Transcript download failed: {e}")
        return None


def _load_markets_for_simulation(
    event_id: str,
    market_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Load ALL markets for a specific event (including closed) with search configs.

    Unlike _load_markets_for_session() which filters active=True, closed=False,
    this loads all markets since we're simulating against resolved past events.
    """
    supabase = get_supabase()

    if market_ids:
        markets_data = []
        for mid in market_ids:
            rows = (
                supabase.table("polymarket_markets")
                .select("id, condition_id, active, closed, outcome_prices")
                .eq("id", mid)
                .execute()
            )
            markets_data.extend(rows.data or [])
    else:
        rows = (
            supabase.table("polymarket_markets")
            .select("id, condition_id, active, closed, outcome_prices")
            .eq("event_id", event_id)
            .execute()
        )
        markets_data = rows.data or []

    if not markets_data:
        return []

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
            "token_id": condition_id,
            "condition_id": condition_id,
            "search_terms": search_terms,
        })

    return result


async def _record_timeline_event(
    session_id: str,
    event_type: str,
    simulated_ts: int,
    market_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Insert a timeline event for the simulation."""
    supabase = get_supabase()
    supabase.table("simulation_timeline_events").insert({
        "session_id": session_id,
        "event_type": event_type,
        "simulated_timestamp": simulated_ts,
        "market_id": market_id,
        "payload": payload or {},
    }).execute()


async def _simulate_position_lifecycle(
    prices: list[dict[str, Any]],
    buy_price: float,
    buy_ts: int,
    config: TradingConfig,
) -> dict[str, Any]:
    """
    Walk price curve forward from buy time to find sell point.

    Returns dict with sell_price, sell_ts, triggered_by, pnl_pct.
    """
    for point in prices:
        if point["t"] <= buy_ts:
            continue

        current_price = point["p"]
        if buy_price <= 0:
            continue

        pnl_pct = ((current_price - buy_price) / buy_price) * 100

        # Check profit target
        if pnl_pct >= config.profit_target_pct:
            return {
                "sell_price": current_price,
                "sell_ts": point["t"],
                "triggered_by": TradeTriggeredBy.PROFIT_TARGET,
                "pnl_pct": pnl_pct,
            }

        # Check stop loss
        if pnl_pct <= -config.stop_loss_pct:
            return {
                "sell_price": current_price,
                "sell_ts": point["t"],
                "triggered_by": TradeTriggeredBy.STOP_LOSS,
                "pnl_pct": pnl_pct,
            }

    # If neither hit, close at last available price
    if prices:
        last = prices[-1]
        pnl_pct = ((last["p"] - buy_price) / buy_price) * 100 if buy_price > 0 else 0
        return {
            "sell_price": last["p"],
            "sell_ts": last["t"],
            "triggered_by": TradeTriggeredBy.SESSION_END,
            "pnl_pct": pnl_pct,
        }

    return {
        "sell_price": buy_price,
        "sell_ts": buy_ts,
        "triggered_by": TradeTriggeredBy.SESSION_END,
        "pnl_pct": 0.0,
    }


async def run_simulation_session(session_id: str) -> None:
    """
    Main simulation orchestrator.

    Pipeline:
    1. Get video metadata + upload timestamp as baseline
    2. Download transcript via yt-dlp subtitles (real timing)
    3. Detect terms
    4. For each detection: look up historical price at simulated time, record buy
    5. For each position: walk price curve to find sell point
    6. Build simulation report and mark complete
    """
    session = await trading_service.get_session(session_id)
    if not session:
        return

    config_data = session.get("config", {})
    market_ids = config_data.pop("market_ids", []) if isinstance(config_data, dict) else []
    event_id = config_data.pop("event_id", None) if isinstance(config_data, dict) else None
    config = TradingConfig(**config_data)
    youtube_url = session["youtube_url"]

    if not event_id:
        await trading_service.update_session(
            session_id,
            status=SessionStatus.FAILED,
            error_message="No event_id specified for simulation",
        )
        return

    # Load markets (including closed ones)
    markets = _load_markets_for_simulation(event_id, market_ids or None)
    if not markets:
        await trading_service.update_session(
            session_id,
            status=SessionStatus.FAILED,
            error_message="No markets with search terms found for this event",
        )
        return

    await trading_service.log_event(session_id, "simulation_started", {
        "markets_loaded": len(markets),
        "total_terms": sum(len(m["search_terms"]) for m in markets),
        "config": config.model_dump(),
        "event_id": event_id,
    })

    progress = {
        "status_detail": "",
        "terms_detected": 0,
        "trades_placed": 0,
        "positions_open": 0,
        "transcript_preview": "",
    }

    work_dir = os.path.join(tempfile.gettempdir(), f"sim_{session_id}")
    os.makedirs(work_dir, exist_ok=True)
    pipeline_start = time.time()

    try:
        # --- Step 1: Get video metadata + upload timestamp ---
        await trading_service.update_session(
            session_id,
            status=SessionStatus.PENDING,
            stage_progress={**progress, "status_detail": "Fetching video metadata..."},
        )

        video_info = _get_video_info(youtube_url)
        baseline_ts = _extract_upload_timestamp(video_info)
        if baseline_ts is None:
            baseline_ts = int(time.time()) - 86400  # fallback: 24h ago
            await trading_service.log_event(session_id, "baseline_fallback", {
                "reason": "Could not get upload timestamp, using 24h ago",
            })

        await _record_timeline_event(session_id, "pipeline_start", baseline_ts)

        # --- Step 2: Download transcript via yt-dlp subtitles ---
        transcript_start = time.time()
        await trading_service.update_session(
            session_id,
            status=SessionStatus.DOWNLOADING,
            stage_progress={**progress, "status_detail": "Downloading transcript (subtitles)..."},
        )

        await _record_timeline_event(session_id, "transcript_download_start", baseline_ts)

        transcript = _download_transcript(youtube_url, work_dir)

        if not transcript:
            await trading_service.update_session(
                session_id,
                status=SessionStatus.FAILED,
                error_message="Failed to download subtitles for this video",
            )
            return

        transcript_duration = time.time() - transcript_start
        simulated_after_transcript = baseline_ts + int(transcript_duration)

        await _record_timeline_event(
            session_id, "transcript_download_end", simulated_after_transcript,
            payload={"duration_s": round(transcript_duration, 1), "text_length": len(transcript)},
        )

        await trading_service.log_event(session_id, "transcript_downloaded", {
            "text_length": len(transcript),
            "duration_s": round(transcript_duration, 1),
        })

        progress["transcript_preview"] = transcript[:500]
        await trading_service.update_session(session_id, stage_progress=progress)

        # --- Step 3: Detect terms ---
        analysis_start = time.time()
        await trading_service.update_session(
            session_id,
            status=SessionStatus.ANALYZING,
            stage_progress={**progress, "status_detail": "Detecting terms and simulating trades..."},
        )

        await _record_timeline_event(session_id, "analysis_start", simulated_after_transcript)

        term_detector = TermDetector(markets)
        detections = term_detector.detect(transcript)
        analysis_duration = time.time() - analysis_start

        supabase = get_supabase()
        positions_data: list[dict[str, Any]] = []

        # --- Step 4: Simulate buys ---
        for i, detection in enumerate(detections):
            progress["terms_detected"] += 1
            simulated_buy_ts = simulated_after_transcript + i  # stagger by 1s

            token_id = detection["token_id"]
            market_id = detection["market_id"]

            await trading_service.log_event(session_id, "term_detected", {
                "term": detection["term"],
                "market_id": market_id,
            })

            if not token_id:
                continue

            # Fetch historical prices around buy time
            price_window_start = simulated_buy_ts - 3600  # 1h before
            price_window_end = simulated_buy_ts + 86400  # 24h after
            prices = await fetch_price_history(token_id, price_window_start, price_window_end)

            if not prices:
                await trading_service.log_event(session_id, "sim_buy_skipped", {
                    "reason": "no_price_data",
                    "market_id": market_id,
                    "term": detection["term"],
                })
                continue

            buy_price = get_price_at_timestamp(prices, simulated_buy_ts)
            if buy_price is None or buy_price > config.max_price_to_buy:
                await trading_service.log_event(session_id, "sim_buy_skipped", {
                    "reason": "price_too_high" if buy_price else "price_unavailable",
                    "market_id": market_id,
                    "term": detection["term"],
                    "price": buy_price,
                })
                continue

            shares = config.buy_amount_usd / buy_price if buy_price > 0 else 0

            # Record simulated buy trade
            trade_row = supabase.table("trades").insert({
                "session_id": session_id,
                "market_id": market_id,
                "token_id": token_id,
                "condition_id": detection["condition_id"],
                "side": TradeSide.BUY.value,
                "amount_usd": config.buy_amount_usd,
                "price": buy_price,
                "shares": shares,
                "order_id": "SIMULATION",
                "status": TradeStatus.FILLED.value,
                "triggered_by": TradeTriggeredBy.TERM_DETECTION.value,
                "detected_term": detection["term"],
                "simulated_at": simulated_buy_ts,
            }).execute()

            buy_trade = trade_row.data[0] if trade_row.data else None
            if not buy_trade:
                continue

            progress["trades_placed"] += 1

            # Create position
            pos_row = supabase.table("trading_positions").insert({
                "session_id": session_id,
                "market_id": market_id,
                "token_id": token_id,
                "buy_trade_id": buy_trade["id"],
                "buy_price": buy_price,
                "shares": shares,
                "current_price": buy_price,
                "status": PositionStatus.OPEN.value,
            }).execute()

            position = pos_row.data[0] if pos_row.data else None
            if position:
                positions_data.append({
                    "position": position,
                    "buy_price": buy_price,
                    "buy_ts": simulated_buy_ts,
                    "token_id": token_id,
                    "market_id": market_id,
                    "prices": prices,
                    "term": detection["term"],
                })

            await _record_timeline_event(
                session_id, "sim_buy", simulated_buy_ts,
                market_id=market_id,
                payload={
                    "term": detection["term"],
                    "price": buy_price,
                    "shares": shares,
                },
            )

        progress["positions_open"] = len(positions_data)
        progress["status_detail"] = f"Simulating {len(positions_data)} position outcomes..."
        await trading_service.update_session(session_id, stage_progress=progress)

        # --- Step 5: Simulate position lifecycles ---
        total_pnl_usd = 0.0
        winning = 0
        losing = 0
        per_market_results: list[dict[str, Any]] = []

        for pos_data in positions_data:
            position = pos_data["position"]
            buy_price = pos_data["buy_price"]
            buy_ts = pos_data["buy_ts"]
            prices = pos_data["prices"]

            # May need extended price data for position lifecycle
            extended_end = buy_ts + 7 * 86400  # up to 7 days
            if prices and prices[-1]["t"] < extended_end:
                extended_prices = await fetch_price_history(
                    pos_data["token_id"], buy_ts, extended_end,
                )
                if extended_prices and len(extended_prices) > len(prices):
                    prices = extended_prices

            lifecycle = await _simulate_position_lifecycle(prices, buy_price, buy_ts, config)

            sell_price = lifecycle["sell_price"]
            sell_ts = lifecycle["sell_ts"]
            triggered_by = lifecycle["triggered_by"]
            pnl_pct = lifecycle["pnl_pct"]

            shares = float(position.get("shares", 0))
            pnl_usd = shares * (sell_price - buy_price)
            total_pnl_usd += pnl_usd

            if pnl_pct >= 0:
                winning += 1
            else:
                losing += 1

            # Record sell trade
            status_map = {
                TradeTriggeredBy.PROFIT_TARGET: PositionStatus.CLOSED_PROFIT,
                TradeTriggeredBy.STOP_LOSS: PositionStatus.CLOSED_LOSS,
                TradeTriggeredBy.MARKET_CLOSE: PositionStatus.CLOSED_MARKET,
                TradeTriggeredBy.SESSION_END: PositionStatus.CLOSED_SESSION,
            }
            position_status = status_map.get(triggered_by, PositionStatus.CLOSED_SESSION)

            sell_trade_row = supabase.table("trades").insert({
                "session_id": session_id,
                "market_id": pos_data["market_id"],
                "token_id": pos_data["token_id"],
                "condition_id": position.get("condition_id"),
                "side": TradeSide.SELL.value,
                "amount_usd": shares * sell_price,
                "price": sell_price,
                "shares": shares,
                "order_id": "SIMULATION",
                "status": TradeStatus.FILLED.value,
                "triggered_by": triggered_by.value,
                "simulated_at": sell_ts,
            }).execute()

            sell_trade_id = sell_trade_row.data[0]["id"] if sell_trade_row.data else None

            # Update position
            supabase.table("trading_positions").update({
                "status": position_status.value,
                "sell_trade_id": sell_trade_id,
                "current_price": sell_price,
                "profit_loss_pct": round(pnl_pct, 2),
            }).eq("id", position["id"]).execute()

            await _record_timeline_event(
                session_id, "sim_sell", sell_ts,
                market_id=pos_data["market_id"],
                payload={
                    "price": sell_price,
                    "pnl_pct": round(pnl_pct, 2),
                    "pnl_usd": round(pnl_usd, 2),
                    "triggered_by": triggered_by.value,
                },
            )

            per_market_results.append({
                "market_id": pos_data["market_id"],
                "term": pos_data["term"],
                "buy_price": buy_price,
                "sell_price": sell_price,
                "buy_ts": buy_ts,
                "sell_ts": sell_ts,
                "pnl_pct": round(pnl_pct, 2),
                "pnl_usd": round(pnl_usd, 2),
                "triggered_by": triggered_by.value,
            })

            await trading_service.log_event(session_id, "sim_position_closed", {
                "market_id": pos_data["market_id"],
                "buy_price": buy_price,
                "sell_price": sell_price,
                "pnl_pct": round(pnl_pct, 2),
                "triggered_by": triggered_by.value,
            })

        # --- Step 6: Build report and complete ---
        pipeline_duration = time.time() - pipeline_start
        total_invested = len(positions_data) * config.buy_amount_usd
        total_pnl_pct = (total_pnl_usd / total_invested * 100) if total_invested > 0 else 0
        total_positions = winning + losing
        win_rate = (winning / total_positions * 100) if total_positions > 0 else 0

        simulation_metadata = {
            "video_upload_timestamp": baseline_ts,
            "baseline_timestamp": baseline_ts,
            "transcript_download_duration_s": round(transcript_duration, 1),
            "analysis_duration_s": round(analysis_duration, 1),
            "total_pipeline_duration_s": round(pipeline_duration, 1),
            "total_pnl_usd": round(total_pnl_usd, 2),
            "total_pnl_pct": round(total_pnl_pct, 2),
            "win_rate": round(win_rate, 1),
            "total_positions": total_positions,
            "winning_positions": winning,
            "losing_positions": losing,
            "per_market": per_market_results,
        }

        # Update session with simulation metadata
        supabase.table("trading_sessions").update({
            "simulation_metadata": simulation_metadata,
        }).eq("id", session_id).execute()

        progress["positions_open"] = 0
        progress["status_detail"] = f"Simulation complete — P&L: ${total_pnl_usd:+.2f} ({total_pnl_pct:+.1f}%)"
        await trading_service.update_session(
            session_id,
            status=SessionStatus.COMPLETED,
            stage_progress=progress,
        )

        await _record_timeline_event(
            session_id, "simulation_complete", simulated_after_transcript + int(analysis_duration),
            payload=simulation_metadata,
        )

        await trading_service.log_event(session_id, "simulation_completed", simulation_metadata)

    except Exception as e:
        await trading_service.update_session(
            session_id,
            status=SessionStatus.FAILED,
            error_message=str(e),
        )
        await trading_service.log_event(session_id, "simulation_failed", {"error": str(e)})

    finally:
        try:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            pass
        untrack_process(f"sim_{session_id}")
        trading_service.cleanup_session_event(session_id)
