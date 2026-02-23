from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List

import yfinance as yf

from app.logging import get_logger

logger = get_logger()

_US_ETFS = {"XLK": "Technology", "XLF": "Financials", "XLV": "Healthcare", "XLE": "Energy",
            "XLI": "Industrials", "XLY": "Consumer Discretionary", "XLP": "Consumer Staples",
            "XLU": "Utilities", "XLB": "Materials", "XLRE": "Real Estate", "XLC": "Communication Services"}
_IN_ETFS = {"^CNXIT": "IT", "^CNXFMCG": "FMCG", "^CNXPHARMA": "Pharma", "^CNXAUTO": "Auto",
            "^NSEBANK": "Banking", "^CNXENERGY": "Energy", "^CNXMETAL": "Metals", "^CNXREALTY": "Real Estate"}
_DEFENSIVE = {"Utilities", "Consumer Staples", "Healthcare", "Real Estate"}
_CYCLICAL = {"Technology", "Financials", "Industrials", "Materials", "Energy"}

_ACTION_ITEMS = {
    "Risk-Off": ["Consider defensive positioning in Utilities, Consumer Staples",
                 "Reduce exposure to cyclical sectors (Energy, Materials)",
                 "Monitor for sector rotation opportunities"],
    "Risk-On": ["Consider cyclical exposure in Energy, Materials, Industrials",
                "Monitor Technology and Consumer Discretionary for momentum continuation",
                "Watch for rotation into growth sectors"],
    "Mixed": ["Focus on sector-specific opportunities", "Monitor individual sector momentum trends",
              "Consider diversified sector allocation"],
}


class SectorRotationAnalyzer:
    """Analyzes sector rotation patterns and momentum."""

    def _market(self, ticker: str) -> str:
        return "India" if ticker.upper().endswith((".NS", ".BO")) else "US"

    def _etfs(self, market: str) -> Dict[str, str]:
        return _IN_ETFS if market == "India" else _US_ETFS

    def _std(self, vals: List[float]) -> float:
        if len(vals) < 2:
            return 0.0
        m = sum(vals) / len(vals)
        return (sum((x - m) ** 2 for x in vals) / len(vals)) ** 0.5

    async def _sector_performance(self, etfs: Dict[str, str], days: int) -> Dict[str, Any]:
        def _fetch():
            end = datetime.now()
            start = end - timedelta(days=days)
            data = {}
            for sym, name in etfs.items():
                try:
                    hist = yf.Ticker(sym).history(start=start, end=end)
                    if len(hist) == 0:
                        continue
                    ret = (hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0]
                    vol = hist["Close"].pct_change().dropna().std() * (252 ** 0.5)
                    mom = 0.0
                    if len(hist) >= 50:
                        mom = (hist["Close"].rolling(20).mean().iloc[-1] -
                               hist["Close"].rolling(50).mean().iloc[-1]) / hist["Close"].rolling(50).mean().iloc[-1]
                    data[name] = {"etf": sym, "total_return": ret, "volatility": vol,
                                  "momentum": mom, "current_price": hist["Close"].iloc[-1],
                                  "data_points": len(hist)}
                except Exception as e:
                    logger.warning(f"Failed to fetch {sym}: {e}")
            return data
        return await asyncio.to_thread(_fetch)

    async def _stock_sector(self, ticker: str) -> Dict[str, Any]:
        def _fetch():
            try:
                info = yf.Ticker(ticker).info
                return {"sector": info.get("sector", "Unknown"), "industry": info.get("industry", "Unknown"),
                        "market_cap": info.get("marketCap", 0), "sector_weight": info.get("sectorWeight", 0)}
            except Exception as e:
                logger.warning(f"Sector info failed for {ticker}: {e}")
                return {"sector": "Unknown", "industry": "Unknown"}
        return await asyncio.to_thread(_fetch)

    def _rotation_patterns(self, perf: Dict[str, Any]) -> Dict[str, Any]:
        if not perf:
            return {"error": "No sector data"}
        by_ret = sorted(perf.items(), key=lambda x: x[1]["total_return"], reverse=True)
        by_mom = sorted(perf.items(), key=lambda x: x[1]["momentum"], reverse=True)
        top3 = [s for s, _ in by_ret[:3]]
        bot3 = [s for s, _ in by_ret[-3:]]
        top_mom = [s for s, _ in by_mom[:3]]
        pos = sum(1 for d in perf.values() if d["total_return"] > 0)
        breadth = pos / len(perf)
        def_top = sum(1 for s in top3 if s in _DEFENSIVE)
        def_mom = sum(1 for s in top_mom if s in _DEFENSIVE)
        if breadth < 0.3:
            phase = "Risk-Off (Defensive Rotation)"
        elif breadth > 0.7 and def_top < 2:
            phase = "Risk-On (Cyclical Rotation)"
        elif def_mom >= 2:
            phase = "Defensive Rotation"
        elif breadth > 0.5:
            phase = "Mixed Rotation"
        else:
            phase = "Uncertain Rotation"

        # Sector correlations
        groups = {
            "cyclical": [s for s in perf if s in _CYCLICAL],
            "defensive": [s for s in perf if s in _DEFENSIVE],
            "growth": [s for s in perf if s not in _CYCLICAL | _DEFENSIVE],
        }
        avgs = {g: (sum(perf[s]["total_return"] for s in ss) / len(ss) if ss else 0)
                for g, ss in groups.items()}
        pattern = (max(avgs, key=avgs.get) + "_leadership") if avgs else "mixed_rotation"

        return {"rotation_phase": phase, "market_breadth": breadth,
                "top_performers": top3, "bottom_performers": bot3,
                "top_momentum": top_mom, "bottom_momentum": [s for s, _ in by_mom[-3:]],
                "sector_count": len(perf), "positive_sectors": pos,
                "correlation_analysis": {"correlation_strength": "moderate",
                                          "rotation_pattern": pattern,
                                          **{f"{k}_sectors": len(v) for k, v in groups.items()}}}

    def _recommendations(self, ticker: str, stock_sector: Dict, perf: Dict, rotation: Dict) -> Dict[str, Any]:
        name = stock_sector.get("sector", "Unknown")
        sd = perf.get(name, {})
        ret, mom = sd.get("total_return", 0), sd.get("momentum", 0)
        recs: Dict[str, Any] = {"sector_outlook": "Neutral", "rotation_signal": "Hold",
                                 "key_insights": [], "action_items": []}
        if ret > 0.05:
            recs["sector_outlook"] = "Positive"
            recs["key_insights"].append(f"{name} sector outperforming with {ret*100:.1f}% return")
        elif ret < -0.05:
            recs["sector_outlook"] = "Negative"
            recs["key_insights"].append(f"{name} sector underperforming with {ret*100:.1f}% return")
        else:
            recs["key_insights"].append(f"{name} sector showing neutral performance ({ret*100:+.1f}%)")
        if abs(mom) > 0.02:
            recs["rotation_signal"] = "Buy" if mom > 0.02 else "Sell"
            recs["key_insights"].append(f"{'Strong' if mom > 0 else 'Negative'} momentum trend ({mom*100:+.1f}%)")
        breadth = rotation.get("market_breadth", 0.5)
        if breadth > 0.7:
            recs["key_insights"].append("Broad market strength supporting sector rotation")
        elif breadth < 0.3:
            recs["key_insights"].append("Narrow leadership - selective sector opportunities")
        recs["key_insights"] = list(dict.fromkeys(recs["key_insights"]))
        phase = rotation.get("rotation_phase", "Uncertain Rotation")
        for key, items in _ACTION_ITEMS.items():
            if key in phase:
                recs["action_items"] = items
                break
        return recs

    def _overall_score(self, perf: Dict, rotation: Dict) -> float:
        try:
            breadth = rotation.get("market_breadth", 0.5)
            pos = rotation.get("positive_sectors", 0)
            total = rotation.get("sector_count", 1)
            phase = rotation.get("rotation_phase", "")
            phase_score = 20 if "Risk-On" in phase else 15 if "Defensive" in phase else 10 if "Mixed" in phase else 5
            return min(100, breadth * 50 + (pos / total) * 30 + phase_score)
        except Exception:
            return 50.0

    def _momentum_score(self, perf: Dict) -> float:
        moms = [d.get("momentum", 0) for d in perf.values()]
        if not moms:
            return 0.5
        return max(0, min(1, (sum(moms) / len(moms) + 0.1) / 0.2))

    def _rotation_signals(self, perf: Dict, rotation: Dict) -> List[Dict[str, str]]:
        signals = []
        if top := rotation.get("top_performers"):
            rd = perf.get(top[0], {}).get("total_return", 0) * 100
            signals.append({"signal_type": "Leading Sector", "description": f"{top[0]} sector leading with {rd:.1f}% returns"})
        phase = rotation.get("rotation_phase", "")
        if "Risk-Off" in phase:
            signals.append({"signal_type": "Market Phase", "description": "Risk-off rotation favoring defensive sectors"})
        elif "Risk-On" in phase:
            signals.append({"signal_type": "Market Phase", "description": "Risk-on rotation favoring cyclical sectors"})
        elif "Mixed" in phase:
            signals.append({"signal_type": "Market Phase", "description": "Mixed rotation creating sector-specific opportunities"})
        breadth = rotation.get("market_breadth", 0.5)
        if breadth > 0.7:
            signals.append({"signal_type": "Market Breadth", "description": "Broad market strength with diversified participation"})
        elif breadth < 0.3:
            signals.append({"signal_type": "Market Breadth", "description": "Narrow leadership - focus on outperforming sectors"})
        return signals[:5]

    async def analyze_sector_rotation(self, ticker: str, days_back: int = 90) -> Dict[str, Any]:
        try:
            market = self._market(ticker)
            etfs = self._etfs(market)
            perf = await self._sector_performance(etfs, days_back)
            rotation = self._rotation_patterns(perf)
            stock_sector = await self._stock_sector(ticker)
            recs = self._recommendations(ticker, stock_sector, perf, rotation)
            return {
                "ticker": ticker, "market": market, "stock_sector": stock_sector,
                "analysis_period_days": days_back, "sector_performance": perf,
                "rotation_patterns": rotation, "recommendations": recs,
                "timestamp": datetime.now().isoformat(), "status": "success",
                "overall_score": self._overall_score(perf, rotation),
                "recommendation": recs["rotation_signal"],
                "sector_performance_summary": {"current_phase": rotation["rotation_phase"],
                                                "momentum_score": self._momentum_score(perf)},
                "rotation_signals": self._rotation_signals(perf, rotation),
                "key_insights": recs["key_insights"],
            }
        except Exception as e:
            logger.error(f"Sector rotation error for {ticker}: {e}")
            return {"ticker": ticker, "status": "error", "error": str(e),
                    "timestamp": datetime.now().isoformat()}


async def analyze_sector_rotation(ticker: str, days_back: int = 90) -> Dict[str, Any]:
    return await SectorRotationAnalyzer().analyze_sector_rotation(ticker, days_back)
