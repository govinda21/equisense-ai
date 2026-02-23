from __future__ import annotations

import asyncio
import logging
from typing import Dict

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.finance import fetch_ohlcv, fetch_info
from app.utils.async_utils import AsyncProcessor, monitor_performance

logger = logging.getLogger(__name__)


def _safe_float(row, col: str, default: float = 0.0) -> float:
    try:
        val = row.get(col, default) if hasattr(row, "get") else getattr(row, col, default)
        return float(val.iloc[0] if hasattr(val, "iloc") else val)
    except (AttributeError, IndexError, TypeError):
        return default


@monitor_performance("data_collection")
async def data_collection_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    tickers = state["tickers"]
    if not tickers:
        state["raw_data"] = {}
        state.setdefault("confidences", {})["data_collection"] = 0.0
        return state

    ticker = tickers[0]

    async def fetch_ticker_data(t: str):
        try:
            ohlcv_df, info = await asyncio.gather(
                fetch_ohlcv(t), fetch_info(t), return_exceptions=True
            )
            ohlcv_summary = {}
            if not isinstance(ohlcv_df, Exception) and hasattr(ohlcv_df, "empty") and not ohlcv_df.empty:
                last = ohlcv_df.iloc[-1]
                ohlcv_summary = {
                    "last_close": _safe_float(last, "Close"),
                    "last_volume": _safe_float(last, "Volume"),
                    "rows": int(len(ohlcv_df)),
                }
            if isinstance(info, Exception):
                info = {}
            return t, {"ohlcv_summary": ohlcv_summary, "info": info}
        except Exception as e:
            logger.error(f"[{t}] Error fetching data: {e}")
            return t, {"ohlcv_summary": {}, "info": {}}

    async with AsyncProcessor(max_workers=15) as processor:
        results = await processor.gather_with_concurrency(
            *[fetch_ticker_data(t) for t in tickers],
            return_exceptions=True, timeout=20.0
        )

    raw_data: Dict[str, dict] = {}
    successful = 0
    for result in results:
        if isinstance(result, Exception):
            logger.error(f"[{ticker}] Failed ticker fetch: {result}")
            continue
        if isinstance(result, tuple) and len(result) == 2:
            result_ticker, data = result
            if result_ticker != ticker:
                logger.error(f"[{ticker}] Ticker mismatch: got {result_ticker}, rejecting")
                continue
            raw_data[result_ticker] = data
            successful += 1

    if ticker in raw_data:
        state["raw_data"] = {ticker: raw_data[ticker]}
    else:
        state["raw_data"] = {ticker: {}}

    state.setdefault("confidences", {})["data_collection"] = successful / len(tickers) if tickers else 0.0
    return state
