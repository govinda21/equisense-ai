from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

import pandas as pd
import math
try:
    import pandas_ta as ta  # type: ignore
except Exception:  # pragma: no cover
    ta = None  # type: ignore

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.finance import fetch_ohlcv
from app.utils.technical_indicators import TechnicalIndicators, PANDAS_TA_AVAILABLE
from app.utils.async_utils import monitor_performance

logger = logging.getLogger(__name__)

# Disable pandas_ta if it's broken
if ta is not None and not PANDAS_TA_AVAILABLE:
    logger.warning("pandas_ta is available but broken, using custom indicators")
    ta = None


def _format_date_index(index: pd.Index) -> List[str]:
    labels: List[str] = []
    for d in index:  # pandas Timestamp or datetime
        if isinstance(d, datetime):
            labels.append(d.strftime("%Y-%m-%d"))
        else:
            try:
                labels.append(pd.to_datetime(d).strftime("%Y-%m-%d"))
            except Exception:
                labels.append(str(d))
    return labels


@monitor_performance("technical_analysis")
async def technicals_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    df = await fetch_ohlcv(ticker)  # default 1y daily
    labels: List[str] = []
    closes: List[float] = []
    indicators: Dict[str, Any] = {}
    signals: Dict[str, Any] = {}
    
    # Technical analysis processing
    if not df.empty:
        labels = _format_date_index(df.index)
        open_s: Optional[pd.Series] = None
        high_s: Optional[pd.Series] = None
        low_s: Optional[pd.Series] = None
        close_s: Optional[pd.Series] = None
        try:
            if isinstance(df.columns, pd.MultiIndex):
                def pick(col: str) -> Optional[pd.Series]:
                    cols = [c for c in df.columns if isinstance(c, tuple) and col in c]
                    if cols:
                        series = df[cols[0]]
                        # If we get a DataFrame instead of Series, extract the first column
                        if isinstance(series, pd.DataFrame):
                            series = series.iloc[:, 0]
                        return series
                    return None
                open_s = pick("Open")
                high_s = pick("High")
                low_s = pick("Low")
                close_s = pick("Close")
                # Successfully extracted OHLC data from MultiIndex DataFrame
            else:
                if "Open" in df.columns: 
                    open_s = df["Open"]
                    if isinstance(open_s, pd.DataFrame): open_s = open_s.iloc[:, 0]
                if "High" in df.columns: 
                    high_s = df["High"]
                    if isinstance(high_s, pd.DataFrame): high_s = high_s.iloc[:, 0]
                if "Low" in df.columns: 
                    low_s = df["Low"]
                    if isinstance(low_s, pd.DataFrame): low_s = low_s.iloc[:, 0]
                if "Close" in df.columns: 
                    close_s = df["Close"]
                    if isinstance(close_s, pd.DataFrame): close_s = close_s.iloc[:, 0]
        except Exception:
            open_s = high_s = low_s = close_s = None

        if close_s is not None:
            # If we accidentally got a DataFrame (e.g., multi-ticker shape), squeeze to Series
            if isinstance(close_s, pd.DataFrame):
                if close_s.shape[1] >= 1:
                    close_s = close_s.iloc[:, 0]
                else:
                    close_s = None

        if close_s is not None:
            try:
                closes = (
                    close_s.astype(float)
                    .ffill()
                    .bfill()
                    .to_list()
                )
            except Exception:
                closes = []

        # Indicators
        try:
            if close_s is not None and len(close_s) >= 50:
                c = close_s.astype(float).ffill().bfill()
                sma20 = c.rolling(20).mean().iloc[-1] if len(c) >= 20 else None
                sma50 = c.rolling(50).mean().iloc[-1] if len(c) >= 50 else None
                sma200 = c.rolling(200).mean().iloc[-1] if len(c) >= 200 else None

                rsi14 = None
                if len(c) >= 15:
                    if ta is not None:
                        try:
                            r = ta.rsi(c, length=14)
                            if r is not None and not r.empty:
                                # RSI is usually a Series, get the last value
                                rsi14 = float(r.iloc[-1]) if not math.isnan(r.iloc[-1]) else None
                                logger.debug(f"RSI14 calculated (pandas_ta): {rsi14}")
                            else:
                                logger.warning("RSI calculation returned empty result")
                        except Exception as e:
                            logger.warning(f"pandas_ta RSI calculation failed: {e}")
                            rsi14 = None
                    
                    # Fallback to custom implementation
                    if rsi14 is None:
                        rsi14 = TechnicalIndicators.rsi(c, length=14)
                        if rsi14 is not None:
                            logger.debug(f"RSI14 calculated (custom): {rsi14}")

                macd_val = macd_sig = macd_hist = None
                if len(c) >= 35:
                    if ta is not None:
                        try:
                            macd_df = ta.macd(c, fast=12, slow=26, signal=9)
                            if macd_df is not None and not macd_df.empty:
                                logger.debug(f"MACD columns: {list(macd_df.columns)}")
                                # Try different possible column names
                                macd_cols = [col for col in macd_df.columns if 'MACD' in col and 'h' not in col and 's' not in col]
                                signal_cols = [col for col in macd_df.columns if 'signal' in col.lower() or 'MACDs' in col]
                                hist_cols = [col for col in macd_df.columns if 'hist' in col.lower() or 'MACDh' in col]
                                
                                if macd_cols:
                                    macd_val = float(macd_df.iloc[-1][macd_cols[0]])
                                    logger.debug(f"MACD value (pandas_ta): {macd_val}")
                                if signal_cols:
                                    macd_sig = float(macd_df.iloc[-1][signal_cols[0]])
                                    logger.debug(f"MACD signal (pandas_ta): {macd_sig}")
                                if hist_cols:
                                    macd_hist = float(macd_df.iloc[-1][hist_cols[0]])
                                    logger.debug(f"MACD histogram (pandas_ta): {macd_hist}")
                            else:
                                logger.warning("MACD calculation returned empty result")
                        except Exception as e:
                            logger.warning(f"pandas_ta MACD calculation failed: {e}")
                            macd_val = macd_sig = macd_hist = None
                    
                    # Fallback to custom implementation
                    if macd_val is None and macd_sig is None and macd_hist is None:
                        macd_result = TechnicalIndicators.macd(c, fast=12, slow=26, signal=9)
                        macd_val = macd_result['macd']
                        macd_sig = macd_result['signal']
                        macd_hist = macd_result['histogram']
                        if macd_val is not None:
                            logger.debug(f"MACD calculated (custom): val={macd_val}, sig={macd_sig}, hist={macd_hist}")

                bb_upper = bb_middle = bb_lower = None
                if len(c) >= 21:
                    if ta is not None:
                        try:
                            bb = ta.bbands(c, length=20, std=2)
                            if bb is not None and not bb.empty:
                                logger.debug(f"Bollinger Bands columns: {list(bb.columns)}")
                                # Try different possible column names
                                upper_cols = [col for col in bb.columns if 'upper' in col.lower() or 'BBU' in col]
                                middle_cols = [col for col in bb.columns if 'middle' in col.lower() or 'BBM' in col]
                                lower_cols = [col for col in bb.columns if 'lower' in col.lower() or 'BBL' in col]
                                
                                if upper_cols:
                                    bb_upper = float(bb.iloc[-1][upper_cols[0]])
                                    logger.debug(f"BB Upper (pandas_ta): {bb_upper}")
                                if middle_cols:
                                    bb_middle = float(bb.iloc[-1][middle_cols[0]])
                                    logger.debug(f"BB Middle (pandas_ta): {bb_middle}")
                                if lower_cols:
                                    bb_lower = float(bb.iloc[-1][lower_cols[0]])
                                    logger.debug(f"BB Lower (pandas_ta): {bb_lower}")
                            else:
                                logger.warning("Bollinger Bands calculation returned empty result")
                        except Exception as e:
                            logger.warning(f"pandas_ta Bollinger Bands calculation failed: {e}")
                            bb_upper = bb_middle = bb_lower = None
                    
                    # Fallback to custom implementation
                    if bb_upper is None and bb_middle is None and bb_lower is None:
                        bb_result = TechnicalIndicators.bollinger_bands(c, length=20, std=2)
                        bb_upper = bb_result['upper']
                        bb_middle = bb_result['middle']
                        bb_lower = bb_result['lower']
                        if bb_upper is not None:
                            logger.debug(f"Bollinger Bands calculated (custom): upper={bb_upper}, middle={bb_middle}, lower={bb_lower}")

                mom20 = None
                if len(c) >= 21 and c.iloc[-21] != 0:
                    mom20 = float((c.iloc[-1] / c.iloc[-21]) - 1.0)

                last_close = float(c.iloc[-1]) if len(c) else None
                indicators = {
                    "sma20": _safe_float(sma20),
                    "sma50": _safe_float(sma50),
                    "sma200": _safe_float(sma200),
                    "rsi14": _safe_float(rsi14),
                    "macd": {"macd": _safe_float(macd_val), "signal": _safe_float(macd_sig), "hist": _safe_float(macd_hist)},
                    "bollinger": {"upper": _safe_float(bb_upper), "middle": _safe_float(bb_middle), "lower": _safe_float(bb_lower)},
                    "momentum20d": _safe_float(mom20),
                    "last_close": _safe_float(last_close),
                }

                regime = "sideways"
                if last_close is not None and sma200 is not None and sma50 is not None:
                    if last_close > sma200 and sma50 > sma200:
                        regime = "bull"
                    elif last_close < sma200 and sma50 < sma200:
                        regime = "bear"

                score = _compute_signal_score(last_close, sma50, sma200, rsi14, macd_hist, mom20)
                signals = {
                    "regime": regime,
                    "score": score,
                    "components": _signal_components(last_close, sma50, sma200, rsi14, macd_hist, mom20),
                }
        except Exception:
            indicators = {}
            signals = {}

    tech_details = {"labels": labels, "closes": closes, "indicators": indicators, "signals": signals}
    state.setdefault("analysis", {})["technicals"] = tech_details
    state.setdefault("confidences", {})["technicals"] = 0.8 if len(closes) >= 10 else 0.3
    return state


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except Exception:
        return None


def _signal_components(
    last_close: Optional[float],
    sma50: Optional[float],
    sma200: Optional[float],
    rsi14: Optional[float],
    macd_hist: Optional[float],
    mom20: Optional[float],
) -> Dict[str, float]:
    comps: Dict[str, float] = {}
    if last_close is not None and sma200 is not None:
        comps["above200"] = 1.0 if last_close > sma200 else -1.0
    if last_close is not None and sma50 is not None:
        comps["above50"] = 1.0 if last_close > sma50 else -1.0
    if sma50 is not None and sma200 is not None:
        comps["sma50_gt_200"] = 1.0 if sma50 > sma200 else -1.0
    if rsi14 is not None:
        comps["rsi_tilt"] = max(-1.0, min(1.0, (rsi14 - 50.0) / 25.0))
    if macd_hist is not None:
        comps["macd_hist"] = 1.0 if macd_hist > 0 else -1.0
    if mom20 is not None:
        comps["mom20"] = math.tanh(mom20 * 3.0)
    return comps


def _compute_signal_score(
    last_close: Optional[float],
    sma50: Optional[float],
    sma200: Optional[float],
    rsi14: Optional[float],
    macd_hist: Optional[float],
    mom20: Optional[float],
) -> float:
    comps = _signal_components(last_close, sma50, sma200, rsi14, macd_hist, mom20)
    weights = {
        "above200": 0.20,
        "above50": 0.10,
        "sma50_gt_200": 0.10,
        "rsi_tilt": 0.20,
        "macd_hist": 0.10,
        "mom20": 0.30,
    }
    score = 0.5
    for k, w in weights.items():
        v = comps.get(k)
        if v is None:
            continue
        score += (v * w) / 2.0
    return float(max(0.0, min(1.0, score)))
