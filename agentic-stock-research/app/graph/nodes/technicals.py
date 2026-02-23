from __future__ import annotations

import logging
import math
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
try:
    import pandas_ta as ta  # type: ignore
except Exception:
    ta = None  # type: ignore

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.finance import fetch_ohlcv
from app.utils.technical_indicators import TechnicalIndicators, PANDAS_TA_AVAILABLE
from app.utils.async_utils import monitor_performance

logger = logging.getLogger(__name__)

if ta is not None and not PANDAS_TA_AVAILABLE:
    ta = None


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None: return None
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return None


def _format_date_index(index: pd.Index) -> List[str]:
    labels = []
    for d in index:
        try:
            labels.append((d if isinstance(d, datetime) else pd.to_datetime(d)).strftime("%Y-%m-%d"))
        except Exception:
            labels.append(str(d))
    return labels


def _pick_series(df: pd.DataFrame, col: str) -> Optional[pd.Series]:
    """Extract a named column from a regular or MultiIndex DataFrame."""
    try:
        if isinstance(df.columns, pd.MultiIndex):
            cols = [c for c in df.columns if isinstance(c, tuple) and col in c]
            if cols:
                s = df[cols[0]]
                return s.iloc[:, 0] if isinstance(s, pd.DataFrame) else s
        elif col in df.columns:
            s = df[col]
            return s.iloc[:, 0] if isinstance(s, pd.DataFrame) else s
    except Exception:
        pass
    return None


def _signal_components(last_close, sma50, sma200, rsi14, macd_hist, mom20) -> Dict[str, float]:
    c: Dict[str, float] = {}
    if last_close is not None and sma200 is not None:
        c["above200"] = 1.0 if last_close > sma200 else -1.0
    if last_close is not None and sma50 is not None:
        c["above50"] = 1.0 if last_close > sma50 else -1.0
    if sma50 is not None and sma200 is not None:
        c["sma50_gt_200"] = 1.0 if sma50 > sma200 else -1.0
    if rsi14 is not None:
        c["rsi_tilt"] = max(-1.0, min(1.0, (rsi14 - 50.0) / 25.0))
    if macd_hist is not None:
        c["macd_hist"] = 1.0 if macd_hist > 0 else -1.0
    if mom20 is not None:
        c["mom20"] = math.tanh(mom20 * 3.0)
    return c


def _compute_signal_score(last_close, sma50, sma200, rsi14, macd_hist, mom20) -> float:
    weights = {"above200": 0.20, "above50": 0.10, "sma50_gt_200": 0.10,
               "rsi_tilt": 0.20, "macd_hist": 0.10, "mom20": 0.30}
    comps = _signal_components(last_close, sma50, sma200, rsi14, macd_hist, mom20)
    score = 0.5 + sum(comps.get(k, 0) * w / 2.0 for k, w in weights.items())
    return float(max(0.0, min(1.0, score)))


def _calculate_support_resistance(high_s, low_s, close_s):
    if high_s is None or low_s is None or close_s is None:
        return [], []
    try:
        highs, lows, closes = high_s.values, low_s.values, close_s.values
        if len(highs) < 20:
            return [], []
        window = 5
        swing_highs, swing_lows = [], []
        for i in range(window, len(highs) - window):
            if all(highs[j] < highs[i] for j in range(i - window, i + window + 1) if j != i):
                swing_highs.append(highs[i])
            if all(lows[j] > lows[i] for j in range(i - window, i + window + 1) if j != i):
                swing_lows.append(lows[i])
        rh, rl, rc = highs[-1], lows[-1], closes[-1]
        pivot = (rh + rl + rc) / 3
        cp = rc
        supports = sorted(
            [pivot - (rh - pivot), 2 * pivot - rh] + [s for s in swing_lows if s < cp],
            reverse=True
        )[:3]
        resistances = sorted(
            [pivot + (pivot - rl), 2 * pivot - rl] + [s for s in swing_highs if s > cp]
        )[:3]
        return supports, resistances
    except Exception as e:
        logger.warning(f"Error calculating support/resistance: {e}")
        return [], []


def _calculate_entry_zone(current_price, support_levels, resistance_levels, sma20, sma50) -> Dict[str, Any]:
    if current_price is None:
        return {"entry_zone_low": 0.0, "entry_zone_high": 0.0,
                "explanation": "Insufficient price data for entry zone calculation"}
    try:
        is_bullish = sma20 is not None and sma50 is not None and current_price > sma20 > sma50
        is_bearish = sma20 is not None and sma50 is not None and current_price < sma20 < sma50

        if is_bullish and support_levels:
            supports_below = [s for s in support_levels if s < current_price]
            if supports_below:
                sup = max(supports_below)
                low, high = sup * 1.02, sup * 1.05
                explanation = f"Bullish trend. Entry zone based on support at ₹{sup:.2f}: ₹{low:.2f}-₹{high:.2f}."
            elif sma20 and sma20 < current_price:
                low, high = sma20 * 0.98, sma20 * 1.02
                explanation = f"Bullish trend. Entry zone based on SMA20 at ₹{sma20:.2f}: ₹{low:.2f}-₹{high:.2f}."
            else:
                low, high = current_price * 0.95, current_price * 1.02
                explanation = f"Bullish trend. Conservative entry zone: ₹{low:.2f}-₹{high:.2f}."
        elif is_bearish and resistance_levels:
            resis_above = [r for r in resistance_levels if r > current_price]
            if resis_above:
                res = min(resis_above)
                low, high = res * 1.02, res * 1.05
                explanation = f"Bearish trend. Entry after breakout above ₹{res:.2f}: ₹{low:.2f}-₹{high:.2f}."
            elif sma20 and sma20 > current_price:
                low, high = sma20 * 1.02, sma20 * 1.05
                explanation = f"Bearish trend. Entry after SMA20 breakout at ₹{sma20:.2f}: ₹{low:.2f}-₹{high:.2f}."
            else:
                low, high = current_price * 1.02, current_price * 1.05
                explanation = f"Bearish trend. Conservative entry: ₹{low:.2f}-₹{high:.2f}."
        else:
            if support_levels:
                sup = max(support_levels)
                low, high = sup * 1.02, sup * 1.05
                res_str = f" Resistance at ₹{min(resistance_levels):.2f}." if resistance_levels else ""
                explanation = f"Sideways market. Entry near support ₹{sup:.2f}: ₹{low:.2f}-₹{high:.2f}.{res_str}"
            elif sma20 and sma50:
                avg = (sma20 + sma50) / 2
                low, high = avg * 0.98, avg * 1.02
                explanation = f"Sideways market. Entry near SMA average: ₹{low:.2f}-₹{high:.2f}."
            else:
                low, high = current_price * 0.95, current_price * 1.02
                explanation = f"Sideways market. Conservative entry: ₹{low:.2f}-₹{high:.2f}."

        return {
            "entry_zone_low": round(low, 2), "entry_zone_high": round(high, 2),
            "explanation": explanation,
            "market_regime": "bullish" if is_bullish else "bearish" if is_bearish else "sideways",
            "strongest_support": max(support_levels) if support_levels else None,
            "weakest_resistance": min(resistance_levels) if resistance_levels else None,
        }
    except Exception as e:
        logger.warning(f"Error calculating entry zone: {e}")
        return {
            "entry_zone_low": current_price * 0.95 if current_price else 0.0,
            "entry_zone_high": current_price * 1.02 if current_price else 0.0,
            "explanation": f"Fallback range due to calculation error: {e}",
        }


def _calc_indicator(c: pd.Series, ta_fn, custom_fn, **kwargs):
    """Try pandas_ta first, fall back to custom implementation."""
    result = None
    if ta is not None:
        try:
            result = ta_fn(c, **kwargs)
        except Exception as e:
            logger.warning(f"pandas_ta failed: {e}")
    if result is None:
        result = custom_fn(c, **kwargs)
    return result


@monitor_performance("technical_analysis")
async def technicals_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    df = await fetch_ohlcv(ticker)
    labels: List[str] = []
    closes: List[float] = []
    indicators: Dict[str, Any] = {}
    signals: Dict[str, Any] = {}

    if not df.empty:
        labels = _format_date_index(df.index)
        open_s = _pick_series(df, "Open")
        high_s = _pick_series(df, "High")
        low_s  = _pick_series(df, "Low")
        close_s = _pick_series(df, "Close")

        if close_s is not None and isinstance(close_s, pd.DataFrame):
            close_s = close_s.iloc[:, 0] if close_s.shape[1] >= 1 else None

        if close_s is not None:
            try:
                closes = close_s.astype(float).ffill().bfill().tolist()
            except Exception:
                closes = []

        try:
            if close_s is not None and len(close_s) >= 50:
                c = close_s.astype(float).ffill().bfill()
                sma20  = _safe_float(c.rolling(20).mean().iloc[-1]) if len(c) >= 20 else None
                sma50  = _safe_float(c.rolling(50).mean().iloc[-1])
                sma200 = _safe_float(c.rolling(200).mean().iloc[-1]) if len(c) >= 200 else None

                # RSI
                rsi14 = None
                if len(c) >= 15:
                    if ta is not None:
                        try:
                            r = ta.rsi(c, length=14)
                            if r is not None and not r.empty:
                                rsi14 = _safe_float(r.iloc[-1])
                        except Exception as e:
                            logger.warning(f"pandas_ta RSI failed: {e}")
                    if rsi14 is None:
                        rsi14 = TechnicalIndicators.rsi(c, length=14)

                # MACD
                macd_val = macd_sig = macd_hist = None
                if len(c) >= 35:
                    if ta is not None:
                        try:
                            mdf = ta.macd(c, fast=12, slow=26, signal=9)
                            if mdf is not None and not mdf.empty:
                                m_cols = [col for col in mdf.columns if "MACD" in col and "h" not in col and "s" not in col]
                                s_cols = [col for col in mdf.columns if "signal" in col.lower() or "MACDs" in col]
                                h_cols = [col for col in mdf.columns if "hist" in col.lower() or "MACDh" in col]
                                if m_cols: macd_val = _safe_float(mdf.iloc[-1][m_cols[0]])
                                if s_cols: macd_sig = _safe_float(mdf.iloc[-1][s_cols[0]])
                                if h_cols: macd_hist = _safe_float(mdf.iloc[-1][h_cols[0]])
                        except Exception as e:
                            logger.warning(f"pandas_ta MACD failed: {e}")
                    if macd_val is None:
                        r = TechnicalIndicators.macd(c, fast=12, slow=26, signal=9)
                        macd_val, macd_sig, macd_hist = r["macd"], r["signal"], r["histogram"]

                # Bollinger Bands
                bb_upper = bb_middle = bb_lower = None
                if len(c) >= 21:
                    if ta is not None:
                        try:
                            bb = ta.bbands(c, length=20, std=2)
                            if bb is not None and not bb.empty:
                                u = [col for col in bb.columns if "upper" in col.lower() or "BBU" in col]
                                m = [col for col in bb.columns if "middle" in col.lower() or "BBM" in col]
                                l = [col for col in bb.columns if "lower" in col.lower() or "BBL" in col]
                                if u: bb_upper = _safe_float(bb.iloc[-1][u[0]])
                                if m: bb_middle = _safe_float(bb.iloc[-1][m[0]])
                                if l: bb_lower = _safe_float(bb.iloc[-1][l[0]])
                        except Exception as e:
                            logger.warning(f"pandas_ta BB failed: {e}")
                    if bb_upper is None:
                        r = TechnicalIndicators.bollinger_bands(c, length=20, std=2)
                        bb_upper, bb_middle, bb_lower = r["upper"], r["middle"], r["lower"]

                mom20 = None
                if len(c) >= 21 and c.iloc[-21] != 0:
                    mom20 = float((c.iloc[-1] / c.iloc[-21]) - 1.0)

                supports, resistances = _calculate_support_resistance(high_s, low_s, close_s)
                last_close = _safe_float(c.iloc[-1]) if len(c) else None
                current_price = _safe_float(close_s.iloc[-1]) if len(close_s) > 0 else None

                indicators = {
                    "sma20": sma20, "sma50": sma50, "sma200": sma200,
                    "rsi14": _safe_float(rsi14),
                    "macd": {"macd": _safe_float(macd_val), "signal": _safe_float(macd_sig), "hist": _safe_float(macd_hist)},
                    "bollinger": {"upper": _safe_float(bb_upper), "middle": _safe_float(bb_middle), "lower": _safe_float(bb_lower)},
                    "momentum20d": _safe_float(mom20),
                    "last_close": last_close,
                    "support_levels": supports,
                    "resistance_levels": resistances,
                    "entry_zone": _calculate_entry_zone(current_price, supports, resistances, sma20, sma50),
                    "current_price": _safe_float(current_price),
                }

                regime = "sideways"
                if last_close is not None and sma200 is not None and sma50 is not None:
                    if last_close > sma200 and sma50 > sma200: regime = "bull"
                    elif last_close < sma200 and sma50 < sma200: regime = "bear"

                signals = {
                    "regime": regime,
                    "score": _compute_signal_score(last_close, sma50, sma200, rsi14, macd_hist, mom20),
                    "components": _signal_components(last_close, sma50, sma200, rsi14, macd_hist, mom20),
                }
        except Exception:
            indicators = {}
            signals = {}

    state.setdefault("analysis", {})["technicals"] = {"labels": labels, "closes": closes, "indicators": indicators, "signals": signals}
    state.setdefault("confidences", {})["technicals"] = 0.8 if len(closes) >= 10 else 0.3
    return state
