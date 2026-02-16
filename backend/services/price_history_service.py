"""Service for fetching, caching, and interpolating historical Polymarket prices."""

import bisect
from typing import Any

import httpx

from backend.core.database import get_supabase

POLYMARKET_CLOB_API = "https://clob.polymarket.com"


async def fetch_price_history(
    token_id: str,
    start_ts: int,
    end_ts: int,
    fidelity: int = 1,
) -> list[dict[str, Any]]:
    """
    Fetch historical price data for a token.

    Checks cache first, then tries /prices-history, quality checks,
    falls back to /data/trades if data is too coarse, then caches the result.

    Returns list of {t: unix_ts, p: price} dicts sorted by time.
    """
    # Check cache first
    cached = _get_cached_prices(token_id, start_ts, end_ts)
    if cached is not None:
        return cached

    # Try /prices-history endpoint
    prices = await _fetch_from_prices_history(token_id, start_ts, end_ts, fidelity)
    source = "prices-history"

    # Quality check — if avg gap > 12 hours, try trades fallback
    if not prices or not _check_data_quality(prices):
        trade_prices = await _fetch_from_trades(token_id, start_ts, end_ts)
        if trade_prices and (not prices or len(trade_prices) > len(prices)):
            prices = trade_prices
            source = "trades"

    if not prices:
        return []

    # Cache the result
    _cache_prices(token_id, source, start_ts, end_ts, fidelity, prices)
    return prices


def get_price_at_timestamp(
    prices: list[dict[str, Any]],
    target_ts: int,
) -> float | None:
    """
    Get interpolated price at a specific timestamp from a sorted price list.

    Uses linear interpolation between the two nearest data points.
    """
    if not prices:
        return None

    timestamps = [p["t"] for p in prices]

    # Exact match or before first point
    idx = bisect.bisect_left(timestamps, target_ts)

    if idx == 0:
        return prices[0]["p"]
    if idx >= len(prices):
        return prices[-1]["p"]

    # Linear interpolation between idx-1 and idx
    t0, p0 = prices[idx - 1]["t"], prices[idx - 1]["p"]
    t1, p1 = prices[idx]["t"], prices[idx]["p"]

    if t1 == t0:
        return p0

    ratio = (target_ts - t0) / (t1 - t0)
    return p0 + ratio * (p1 - p0)


async def _fetch_from_prices_history(
    token_id: str,
    start_ts: int,
    end_ts: int,
    fidelity: int,
) -> list[dict[str, Any]]:
    """Fetch from CLOB /prices-history endpoint."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{POLYMARKET_CLOB_API}/prices-history",
                params={
                    "market": token_id,
                    "startTs": start_ts,
                    "endTs": end_ts,
                    "fidelity": fidelity,
                },
            )
            response.raise_for_status()
            data = response.json()

            # API returns {"history": [{"t": ts, "p": price}, ...]}
            history = data.get("history", [])
            return [{"t": int(p["t"]), "p": float(p["p"])} for p in history]
    except Exception as e:
        print(f"[price_history] /prices-history failed for {token_id}: {e}")
        return []


def _build_l2_headers() -> dict[str, str] | None:
    """Build CLOB L2 auth headers from settings. Returns None if credentials unavailable."""
    try:
        from backend.config import get_settings

        settings = get_settings()
        if not settings.polymarket_api_key or not settings.polymarket_api_secret:
            return None

        import base64
        import hashlib
        import hmac
        import time as _time

        timestamp = str(int(_time.time()))
        # L2 auth: HMAC-SHA256(api_secret, timestamp + method + path)
        message = timestamp + "GET" + "/data/trades"
        hmac_sig = hmac.new(
            base64.b64decode(settings.polymarket_api_secret),
            message.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        signature = base64.b64encode(hmac_sig).decode("utf-8")

        return {
            "POLY_API_KEY": settings.polymarket_api_key,
            "POLY_SIGNATURE": signature,
            "POLY_TIMESTAMP": timestamp,
            "POLY_PASSPHRASE": settings.polymarket_api_secret,
        }
    except Exception:
        return None


async def _fetch_from_trades(
    token_id: str,
    start_ts: int,
    end_ts: int,
) -> list[dict[str, Any]]:
    """
    Fallback: reconstruct price points from trade data.

    Requires POLYMARKET_API_KEY and POLYMARKET_API_SECRET for L2 auth.
    Returns empty list if credentials are unavailable.
    """
    headers = _build_l2_headers()
    if headers is None:
        # /data/trades requires L2 auth — optional fallback for finer granularity
        return []

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            all_trades = []
            cursor = None

            # Paginate through trades
            for _ in range(10):  # max 10 pages
                params: dict[str, Any] = {
                    "market": token_id,
                    "startTs": start_ts,
                    "endTs": end_ts,
                    "limit": 500,
                }
                if cursor:
                    params["cursor"] = cursor

                response = await client.get(
                    f"{POLYMARKET_CLOB_API}/data/trades",
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                data = response.json()

                trades = data if isinstance(data, list) else data.get("data", [])
                if not trades:
                    break

                all_trades.extend(trades)
                cursor = data.get("next_cursor") if isinstance(data, dict) else None
                if not cursor:
                    break

            # Convert trades to price points
            prices = []
            for trade in all_trades:
                ts = trade.get("timestamp") or trade.get("match_time")
                price = trade.get("price")
                if ts is not None and price is not None:
                    prices.append({"t": int(ts), "p": float(price)})

            prices.sort(key=lambda x: x["t"])
            return prices
    except Exception as e:
        print(f"[price_history] /data/trades fallback failed for {token_id}: {e}")
        return []


def _check_data_quality(prices: list[dict[str, Any]]) -> bool:
    """Returns False if average gap between data points exceeds 12 hours."""
    if len(prices) < 2:
        return False

    total_gap = prices[-1]["t"] - prices[0]["t"]
    avg_gap = total_gap / (len(prices) - 1)
    twelve_hours = 12 * 3600
    return avg_gap <= twelve_hours


def _get_cached_prices(
    token_id: str,
    start_ts: int,
    end_ts: int,
) -> list[dict[str, Any]] | None:
    """Check cache for existing price data covering the requested range."""
    try:
        supabase = get_supabase()
        response = (
            supabase.table("market_price_history")
            .select("prices")
            .eq("token_id", token_id)
            .lte("start_ts", start_ts)
            .gte("end_ts", end_ts)
            .order("fetched_at", desc=True)
            .limit(1)
            .execute()
        )
        if response.data:
            return response.data[0]["prices"]
    except Exception:
        pass
    return None


def _cache_prices(
    token_id: str,
    source: str,
    start_ts: int,
    end_ts: int,
    fidelity: int,
    prices: list[dict[str, Any]],
) -> None:
    """Cache price data, using upsert to avoid duplicates."""
    try:
        supabase = get_supabase()
        supabase.table("market_price_history").upsert(
            {
                "token_id": token_id,
                "source": source,
                "start_ts": start_ts,
                "end_ts": end_ts,
                "fidelity": fidelity,
                "prices": prices,
            },
            on_conflict="token_id,source,start_ts,end_ts",
        ).execute()
    except Exception as e:
        print(f"[price_history] Cache write failed: {e}")
