"""
Comprehensive Stock Scoring & Ranking Engine
Multi-dimensional scoring with 5 weighted pillars.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from app.tools.fundamentals import compute_fundamentals
from app.tools.dcf_valuation import perform_dcf_valuation
from app.tools.governance_analysis import analyze_corporate_governance
from app.tools.valuation import resolve_financial_inputs


def _f(x: Any) -> Optional[float]:
    """Safe float conversion with NaN guard — mirrors valuation.py._f."""
    try:
        v = float(x)
        return None if v != v else v
    except Exception:
        return None

logger = logging.getLogger(__name__)

# Industry average P/E ratios for sector-relative valuation
_INDUSTRY_PE = {
    "Technology": 25.0, "Healthcare": 22.0, "Financial Services": 12.0,
    "Consumer Cyclical": 18.0, "Consumer Defensive": 20.0, "Industrials": 16.0,
    "Energy": 15.0, "Utilities": 18.0, "Real Estate": 20.0,
    "Materials": 14.0, "Communication Services": 20.0, "Basic Materials": 14.0,
}

# Sector scoring weight multipliers
_SECTOR_ADJUSTMENTS = {
    "Technology": {"growth_prospects": 1.2, "valuation": 0.9},
    "Banking": {"financial_health": 1.1, "governance": 1.2},
    "Pharmaceuticals": {"growth_prospects": 1.1, "macro_sensitivity": 0.8},
    "Real Estate": {"financial_health": 1.2, "macro_sensitivity": 1.3},
    "Utilities": {"financial_health": 1.1, "growth_prospects": 0.8},
}


@dataclass
class ScoringWeights:
    financial_health: float = 0.30
    valuation: float = 0.25
    growth_prospects: float = 0.20
    governance: float = 0.15
    macro_sensitivity: float = 0.10

    def __post_init__(self):
        total = sum([self.financial_health, self.valuation, self.growth_prospects,
                     self.governance, self.macro_sensitivity])
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total}")


@dataclass
class PillarScore:
    score: float
    confidence: float
    key_metrics: Dict[str, Any]
    positive_factors: List[str]
    negative_factors: List[str]
    data_quality: str  # "High", "Medium", "Low"


@dataclass
class ComprehensiveScore:
    ticker: str
    overall_score: float
    overall_grade: str
    confidence_level: float
    recommendation: str
    financial_health: PillarScore
    valuation: PillarScore
    growth_prospects: PillarScore
    governance: PillarScore
    macro_sensitivity: PillarScore
    position_sizing_pct: float
    entry_zone: Tuple[float, float]
    entry_explanation: str
    target_price: float
    stop_loss: float
    time_horizon_months: int
    risk_rating: str
    key_risks: List[str]
    key_catalysts: List[str]


def _score_to_grade(score: float) -> str:
    thresholds = [(90, "A+"), (85, "A"), (80, "A-"), (75, "B+"), (70, "B"),
                  (65, "B-"), (60, "C+"), (55, "C"), (50, "C-"), (45, "D+"), (40, "D")]
    for threshold, grade in thresholds:
        if score >= threshold:
            return grade
    return "F"


def _default_pillar(err: Exception) -> PillarScore:
    return PillarScore(50.0, 0.1, {}, [], [str(err)[:100]], "Low")


class ComprehensiveScoringEngine:
    """Multi-dimensional stock scoring and ranking engine."""

    def __init__(self, weights: Optional[ScoringWeights] = None):
        self.weights = weights or ScoringWeights()

    async def score_ticker(self, ticker: str, current_price: Optional[float] = None) -> ComprehensiveScore:
        logger.info(f"Starting comprehensive scoring for {ticker}")

        results = await asyncio.gather(
            self._score_financial_health(ticker),
            self._score_valuation(ticker, current_price),
            self._score_growth_prospects(ticker),
            self._score_governance(ticker),
            self._score_macro_sensitivity(ticker),
            return_exceptions=True,
        )

        pillar_names = ["financial_health", "valuation", "growth_prospects", "governance", "macro_sensitivity"]
        pillar_scores = {
            name: (_default_pillar(result) if isinstance(result, Exception) else result)
            for name, result in zip(pillar_names, results)
        }

        # Log failed pillars
        for name, result in zip(pillar_names, results):
            if isinstance(result, Exception):
                logger.error(f"Failed to calculate {name} for {ticker}: {result}")

        # Apply sector adjustments
        sector = await self._identify_sector(ticker)
        if sector in _SECTOR_ADJUSTMENTS:
            for pillar_name, factor in _SECTOR_ADJUSTMENTS[sector].items():
                if pillar_name in pillar_scores:
                    pillar_scores[pillar_name].score = min(100.0, pillar_scores[pillar_name].score * factor)

        overall_score = round(sum(
            pillar_scores[name].score * getattr(self.weights, name)
            for name in pillar_names
        ), 1)
        overall_confidence = round(sum(
            pillar_scores[name].confidence * getattr(self.weights, name)
            for name in pillar_names
        ), 2)

        trading = await self._calculate_trading_parameters(ticker, overall_score, pillar_scores, current_price)
        risk = self._assess_risk_factors(pillar_scores)
        recommendation = self._generate_recommendation(overall_score, pillar_scores)

        return ComprehensiveScore(
            ticker=ticker,
            overall_score=overall_score,
            overall_grade=_score_to_grade(overall_score),
            confidence_level=overall_confidence,
            recommendation=recommendation,
            financial_health=pillar_scores["financial_health"],
            valuation=pillar_scores["valuation"],
            growth_prospects=pillar_scores["growth_prospects"],
            governance=pillar_scores["governance"],
            macro_sensitivity=pillar_scores["macro_sensitivity"],
            position_sizing_pct=trading["position_sizing"],
            entry_zone=trading["entry_zone"],
            entry_explanation=trading["entry_explanation"],
            target_price=trading["target_price"],
            stop_loss=trading["stop_loss"],
            time_horizon_months=trading["time_horizon"],
            risk_rating=risk["risk_rating"],
            key_risks=risk["key_risks"],
            key_catalysts=risk["key_catalysts"],
        )

    async def _score_financial_health(self, ticker: str) -> PillarScore:
        try:
            f = await compute_fundamentals(ticker)
            roe = f.get("roe", 0) or 0
            roic = f.get("roic", 0) or 0
            de = f.get("debtToEquity", 0) or 0
            ic = f.get("interestCoverage", 0) or 0
            fcf_yield = f.get("fcfYield", 0) or 0
            gm = f.get("grossMargins", 0) or 0
            om = f.get("operatingMargins", 0) or 0

            sector = f.get("sector", "")
            is_financial = "Financial" in sector or "Bank" in sector
            logger.info(f"Sector for {ticker}: '{sector}', is_financial={is_financial}, D/E={de:.1f}%")

            # ROE (0-25 pts)
            roe_pts = 25 if roe >= 20 else 20 if roe >= 15 else 15 if roe >= 12 else 10 if roe >= 8 else 5
            # ROIC (0-20 pts)
            roic_pts = 20 if roic >= 15 else 15 if roic >= 12 else 10 if roic >= 8 else 5
            # Leverage (0-20 pts) — bank-aware thresholds
            if is_financial:
                lev_pts = 20 if de <= 400 else 15 if de <= 700 else 10 if de <= 1000 else 5
            else:
                lev_pts = 20 if de <= 30 else 15 if de <= 60 else 10 if de <= 100 else 5
            # Interest coverage (0-15 pts)
            if not ic:
                ic_pts = 10
            elif ic >= 5:
                ic_pts = 15
            elif ic >= 3:
                ic_pts = 12
            elif ic >= 2:
                ic_pts = 8
            elif ic < 1:
                ic_pts = 2
            else:
                ic_pts = 5
            # FCF yield (0-10 pts)
            fcf_pts = 10 if fcf_yield >= 8 else 8 if fcf_yield >= 5 else 5 if fcf_yield >= 2 else 2
            # Margins (0-10 pts)
            margin_pts = (5 if om >= 20 else 4 if om >= 15 else 3 if om >= 10 else 0) + \
                         (5 if gm >= 50 else 3 if gm >= 30 else 2 if gm >= 20 else 0)

            total = roe_pts + roic_pts + lev_pts + ic_pts + fcf_pts + margin_pts

            pos, neg = [], []
            if roe >= 15:
                pos.append(f"Strong ROE of {roe:.1f}%")
            elif 0 < roe < 8:
                neg.append(f"Weak ROE of {roe:.1f}%")
            if is_financial:
                if de <= 500:
                    pos.append(f"Below-average leverage for bank (D/E: {de:.1f}%)")
                elif de > 1000:
                    neg.append(f"High leverage even for bank (D/E: {de:.1f}%)")
            else:
                if de <= 50:
                    pos.append(f"Conservative leverage (D/E: {de:.1f}%)")
                elif de > 100:
                    neg.append(f"High leverage (D/E: {de:.1f}%)")
            if ic and ic > 0:
                if ic >= 3:
                    pos.append(f"Adequate interest coverage ({ic:.1f}x)")
                elif ic < 2:
                    neg.append(f"Poor interest coverage ({ic:.1f}x)")
            if fcf_yield >= 5:
                pos.append(f"Good FCF yield ({fcf_yield:.1f}%)")

            dq = "High" if sum(1 for x in [roe, roic, de] if x != 0) >= 2 else "Medium"
            return PillarScore(
                score=min(100.0, total), confidence=0.8 if dq == "High" else 0.6,
                key_metrics={"roe": roe, "roic": roic, "debt_to_equity": de,
                             "interest_coverage": ic, "fcf_yield": fcf_yield, "operating_margins": om},
                positive_factors=pos, negative_factors=neg, data_quality=dq,
            )
        except Exception as e:
            logger.error(f"Financial health scoring failed for {ticker}: {e}")
            return _default_pillar(e)

    async def _score_valuation(self, ticker: str, current_price: Optional[float]) -> PillarScore:
        """
        Sector-aware valuation scoring.

        Financial Services (banks, NBFCs, insurance):
          - Primary model: Excess Returns (Residual Income) — BVPS + PV of excess returns
          - DCF is NOT used — FCF includes deposit/loan flows for banks, making it meaningless
          - Scored on: P/B vs peers (0-30 pts) + ROE vs cost of equity (0-30 pts) + P/E (0-25 pts) + PEG (0-15 pts)

        All other sectors:
          - Primary model: DCF with P/E / P/B / PEG comparables
          - Scored on: DCF margin-of-safety (0-50 pts) + P/E (0-25 pts) + P/B (0-15 pts) + PEG (0-10 pts)
        """
        try:
            import yfinance as yf

            f = await compute_fundamentals(ticker)
            sector   = f.get("sector", "") or ""
            industry = f.get("industry", "") or ""
            pe  = f.get("pe",  0) or 0
            pb  = f.get("pb",  0) or 0
            peg = f.get("peg", 0) or 0

            # Detect Financial Services: sector flag or industry keywords
            is_financial = (
                "Financial" in sector
                or "Bank" in sector
                or "bank" in industry.lower()
                or "insurance" in industry.lower()
                or "nbfc" in industry.lower()
            )

            pos: List[str] = []
            neg: List[str] = []

            if is_financial:
                # ── Financial Services path: Excess Returns (Residual Income) ────
                # Do NOT call perform_dcf_valuation — it produces meaningless results for banks.
                # Score on P/B vs peer benchmark, ROE vs cost of equity, and P/E.

                try:
                    info = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: yf.Ticker(ticker).info or {}
                    )
                except Exception:
                    info = {}

                price_used = current_price or _f(
                    info.get("currentPrice") or info.get("regularMarketPrice")
                )
                beta = _f(info.get("beta")) or 1.0

                # Cost of equity via CAPM (Indian G-Sec 7.0%, ERP 6.5%)
                is_indian = ticker.upper().endswith(".NS") or ticker.upper().endswith(".BO")
                rf  = 0.070 if is_indian else 0.045
                ke  = max(0.08, min(0.18, rf + beta * 0.065))
                tg  = 0.025

                # Resolve BVPS and ROE through the shared, exhaustive derivation chain.
                # This is the single place that handles all yfinance field inconsistencies —
                # do not add fallback logic here; fix resolve_financial_inputs() instead.
                fi   = resolve_financial_inputs(info, ticker, price_used)
                roe  = fi["roe"]
                bvps = fi["bvps"]

                # Excess Returns intrinsic value
                intrinsic_value = None
                margin_of_safety = None
                if roe is not None and bvps and bvps > 0 and ke > tg:
                    excess_return = roe - ke
                    tv = (bvps * excess_return) / (ke - tg)
                    intrinsic_value = round(bvps + tv, 2)
                    if price_used and price_used > 0:
                        margin_of_safety = (intrinsic_value - price_used) / price_used

                # P/B scoring (0-30 pts): P/B for private Indian banks, peer avg ~2.8x
                # Low P/B relative to peers = undervalued = higher score
                if is_indian and "Public" in (sector + industry):
                    peer_pb = 1.2  # PSU banks
                else:
                    peer_pb = 2.8  # Private banks / generic financial
                if pb > 0:
                    pb_ratio_to_peer = pb / peer_pb
                    pb_pts = (
                        30 if pb_ratio_to_peer <= 0.8 else
                        25 if pb_ratio_to_peer <= 1.0 else
                        18 if pb_ratio_to_peer <= 1.3 else
                        10 if pb_ratio_to_peer <= 1.6 else 5
                    )
                else:
                    pb_pts = 15  # neutral if missing

                # ROE vs Ke scoring (0-30 pts): excess return spread
                if roe is not None:
                    spread = roe - ke  # positive = value-creating
                    roe_pts = (
                        30 if spread >= 0.08 else
                        25 if spread >= 0.05 else
                        20 if spread >= 0.02 else
                        12 if spread >= 0.00 else
                        5   # value-destroying
                    )
                    if spread >= 0.05:
                        pos.append(f"ROE ({roe*100:.1f}%) well above cost of equity ({ke*100:.1f}%)")
                    elif spread < 0:
                        neg.append(f"ROE ({roe*100:.1f}%) below cost of equity ({ke*100:.1f}%) — value-destroying")
                else:
                    roe_pts = 15

                # P/E scoring (0-25 pts): peer avg for Indian private banks ~20x
                peer_pe = 20.0 if is_indian else 15.0
                if pe > 0:
                    pe_ratio = pe / peer_pe
                    pe_pts = (
                        25 if pe_ratio <= 0.8 else
                        20 if pe_ratio <= 1.0 else
                        15 if pe_ratio <= 1.3 else
                        8  if pe_ratio <= 1.6 else 4
                    )
                    if pe_ratio <= 0.9:
                        pos.append(f"Attractive P/E vs peers ({pe:.1f}x vs peer avg {peer_pe:.0f}x)")
                    elif pe_ratio > 1.4:
                        neg.append(f"Premium P/E vs peers ({pe:.1f}x vs peer avg {peer_pe:.0f}x)")
                else:
                    pe_pts = 12

                # PEG scoring (0-15 pts)
                peg_pts = (15 if peg <= 0.8 else 12 if peg <= 1.2 else 8 if peg <= 2 else 3) if peg > 0 else 7

                # Margin of safety commentary
                if margin_of_safety is not None:
                    if margin_of_safety >= 0.15:
                        pos.append(f"Trading at discount to Excess Returns IV (MoS: {margin_of_safety*100:.1f}%)")
                    elif margin_of_safety < -0.10:
                        neg.append(f"Trading above Excess Returns IV (premium: {-margin_of_safety*100:.1f}%)")

                if 0 < pb <= 1.5:
                    pos.append(f"Reasonable P/B ratio for financials ({pb:.1f}x)")
                elif pb > 4:
                    neg.append(f"High P/B ratio ({pb:.1f}x) — expensive vs book")

                total_score = min(100.0, pb_pts + roe_pts + pe_pts + peg_pts)
                # Confidence reflects whether inputs came directly or were derived
                direct_inputs = (fi["bvps_source"] == "bookValue" and
                                 fi["roe_source"] == "returnOnEquity")
                return PillarScore(
                    score=total_score,
                    confidence=0.75 if direct_inputs else (0.65 if (roe is not None and bvps) else 0.5),
                    key_metrics={
                        "intrinsic_value":   intrinsic_value or 0,
                        "margin_of_safety":  margin_of_safety or 0,
                        "pe_ratio":          pe,
                        "pb_ratio":          pb,
                        "peg_ratio":         peg,
                        "roe":               round(roe * 100, 2) if roe is not None else 0,
                        "cost_of_equity":    round(ke, 4),
                        "bvps":              bvps or 0,
                        "valuation_method":  "Excess Returns (Residual Income)",
                        "bvps_source":       fi["bvps_source"],
                        "roe_source":        fi["roe_source"],
                    },
                    positive_factors=pos,
                    negative_factors=neg,
                    data_quality="High" if direct_inputs else ("Medium" if (roe is not None and bvps) else "Low"),
                )

            else:
                # ── Non-financial path: DCF + comparables ────────────────────
                dcf = await perform_dcf_valuation(ticker, current_price)

                # DCF score (0-50 pts) or P/E fallback
                if "error" not in dcf and dcf.get("intrinsic_value"):
                    mos = dcf.get("margin_of_safety", 0)
                    dcf_pts = 50 if mos >= 0.3 else 40 if mos >= 0.2 else 30 if mos >= 0.1 else 20 if mos >= 0 else 10
                else:
                    logger.warning(f"DCF failed for {ticker}, using P/E fallback")
                    dcf_pts = self._calculate_pe_fallback_score(f, current_price, ticker)

                # P/E (0-25 pts)
                pe_pts = (25 if pe <= 12 else 20 if pe <= 18 else 15 if pe <= 25 else 10 if pe <= 35 else 5) if pe > 0 else 12
                # P/B (0-15 pts)
                pb_pts = (15 if pb <= 1 else 12 if pb <= 2 else 8 if pb <= 3 else 5) if pb > 0 else 8
                # PEG (0-10 pts)
                peg_pts = (10 if peg <= 0.8 else 8 if peg <= 1.2 else 5 if peg <= 2 else 2) if peg > 0 else 5

                if "error" not in dcf:
                    mos = dcf.get("margin_of_safety", 0)
                    if mos >= 0.2:
                        pos.append(f"Strong margin of safety ({mos*100:.1f}%)")
                    elif mos < 0:
                        neg.append(f"Trading above intrinsic value (MoS: {mos*100:.1f}%)")
                if 0 < pe <= 15:
                    pos.append(f"Attractive P/E ratio ({pe:.1f})")
                elif pe > 30:
                    neg.append(f"High P/E ratio ({pe:.1f})")
                if 0 < pb <= 1.5:
                    pos.append(f"Reasonable P/B ratio ({pb:.1f})")
                elif pb > 3:
                    neg.append(f"High P/B ratio ({pb:.1f})")

                return PillarScore(
                    score=min(100.0, dcf_pts + pe_pts + pb_pts + peg_pts),
                    confidence=0.8 if "error" not in dcf else 0.6,
                    key_metrics={
                        "intrinsic_value":  dcf.get("intrinsic_value", 0),
                        "margin_of_safety": dcf.get("margin_of_safety", 0),
                        "pe_ratio": pe, "pb_ratio": pb, "peg_ratio": peg,
                        "valuation_method": "DCF",
                    },
                    positive_factors=pos, negative_factors=neg,
                    data_quality="High" if "error" not in dcf else "Medium",
                )

        except Exception as e:
            logger.error(f"Valuation scoring failed for {ticker}: {e}")
            return _default_pillar(e)

    def _calculate_pe_fallback_score(self, f: Dict, current_price: Optional[float], ticker: str) -> float:
        try:
            pe = f.get("trailingPE") or f.get("forwardPE") if f else None
            if not pe or not isinstance(pe, (int, float)) or pe <= 0:
                return 25.0
            sector = (f.get("sector") or "Technology") if f else "Technology"
            industry_pe = _INDUSTRY_PE.get(sector, 18.0)
            ratio = pe / industry_pe
            score = 45 if ratio <= 0.6 else 35 if ratio <= 0.8 else 25 if ratio <= 1.0 else 15 if ratio <= 1.3 else 5
            logger.info(f"P/E fallback {ticker}: pe={pe:.1f}, industry={industry_pe:.1f}, ratio={ratio:.2f}, score={score}")
            return float(score)
        except Exception as e:
            logger.error(f"P/E fallback failed for {ticker}: {e}")
            return 25.0

    async def _score_growth_prospects(self, ticker: str) -> PillarScore:
        try:
            f = await compute_fundamentals(ticker)
            rg = f.get("revenueGrowth", 0) or 0
            gm = f.get("grossMargins", 0) or 0
            om = f.get("operatingMargins", 0) or 0
            roe = f.get("roe", 0) or 0

            rev_pts = 40 if rg >= 25 else 30 if rg >= 15 else 25 if rg >= 10 else 15 if rg >= 5 else 10 if rg >= 0 else 5
            mar_pts = 30 if om >= 20 else 25 if om >= 15 else 20 if om >= 10 else 15
            roe_pts = 30 if roe >= 20 else 25 if roe >= 15 else 20 if roe >= 12 else 15

            pos, neg = [], []
            if rg >= 15:
                pos.append(f"Strong revenue growth ({rg:.1f}%)")
            elif rg < 0:
                neg.append(f"Revenue decline ({rg:.1f}%)")
            if om >= 15:
                pos.append(f"Healthy operating margins ({om:.1f}%)")
            elif om < 5:
                neg.append(f"Weak operating margins ({om:.1f}%)")

            return PillarScore(
                score=min(100.0, rev_pts + mar_pts + roe_pts), confidence=0.7,
                key_metrics={"revenue_growth": rg, "gross_margins": gm, "operating_margins": om, "roe": roe},
                positive_factors=pos, negative_factors=neg, data_quality="Medium",
            )
        except Exception as e:
            logger.error(f"Growth prospects scoring failed for {ticker}: {e}")
            return _default_pillar(e)

    async def _score_governance(self, ticker: str) -> PillarScore:
        try:
            g = await analyze_corporate_governance(ticker)
            if "error" in g:
                return PillarScore(50.0, 0.2, {}, [], [g["error"]], "Low")

            gov_score = g.get("governance_score", 50)
            red_flags = g.get("red_flags", [])
            critical = [rf for rf in red_flags if rf["severity"] == "Critical"]
            high = [rf for rf in red_flags if rf["severity"] == "High"]

            pos = ["Strong corporate governance standards"] if gov_score >= 80 else []
            neg = (["Below-average governance quality"] if gov_score < 60 else []) + \
                  [rf["description"][:50] + "..." for rf in critical[:2]] + \
                  [rf["description"][:50] + "..." for rf in high[:1]]

            return PillarScore(
                score=gov_score, confidence=0.7,
                key_metrics={"governance_score": gov_score,
                             "governance_grade": g.get("governance_grade", "C"),
                             "critical_red_flags": len(critical), "high_red_flags": len(high)},
                positive_factors=pos, negative_factors=neg, data_quality="Medium",
            )
        except Exception as e:
            logger.error(f"Governance scoring failed for {ticker}: {e}")
            return _default_pillar(e)

    async def _score_macro_sensitivity(self, ticker: str) -> PillarScore:
        try:
            f = await compute_fundamentals(ticker)
            de = f.get("debtToEquity", 0) or 0
            beta = 1.0  # Would fetch from market data

            int_pts = 30 if de <= 30 else 25 if de <= 60 else 20 if de <= 100 else 15
            mkt_pts = 25 if beta <= 0.8 else 20 if beta <= 1.2 else 15
            total = int_pts + mkt_pts + 20 + 25  # cyclicality + regulatory: neutral

            pos = ["Low interest rate sensitivity"] if de <= 50 else []
            neg = ["High interest rate sensitivity"] if de > 100 else []

            return PillarScore(
                score=min(100.0, total), confidence=0.5,
                key_metrics={"debt_to_equity": de, "estimated_beta": beta},
                positive_factors=pos, negative_factors=neg, data_quality="Low",
            )
        except Exception as e:
            logger.error(f"Macro sensitivity scoring failed for {ticker}: {e}")
            return _default_pillar(e)

    async def _identify_sector(self, ticker: str) -> Optional[str]:
        return None  # Future: proper sector classification

    def _generate_recommendation(self, score: float, pillar_scores: Dict[str, PillarScore]) -> str:
        rec = "Strong Buy" if score >= 80 else "Buy" if score >= 70 else "Hold" if score >= 60 else "Weak Hold" if score >= 50 else "Sell"
        # Downgrade for poor governance or severe overvaluation
        if pillar_scores["governance"].score < 40 or pillar_scores["valuation"].score < 30:
            if rec in ("Strong Buy", "Buy"):
                rec = "Hold"
        return rec

    async def _calculate_trading_parameters(
        self, ticker: str, overall_score: float, pillar_scores: Dict[str, PillarScore], current_price: Optional[float]
    ) -> Dict[str, Any]:
        confidence = sum(pillar_scores[n].confidence * getattr(self.weights, n)
                         for n in ["financial_health", "valuation", "growth_prospects", "governance", "macro_sensitivity"])

        position_sizing = (7.0 if overall_score >= 80 and confidence >= 0.7 else
                           5.0 if overall_score >= 70 and confidence >= 0.6 else
                           3.0 if overall_score >= 60 else 1.0)

        intrinsic_value = pillar_scores["valuation"].key_metrics.get("intrinsic_value", 0)

        # Try technical entry zone first
        entry_zone, entry_explanation = (0.0, 0.0), "Insufficient data for entry zone calculation"
        try:
            from app.tools.finance import fetch_ohlcv
            from app.graph.nodes.technicals import _calculate_support_resistance, _calculate_entry_zone

            df = await fetch_ohlcv(ticker)
            if not df.empty and len(df) >= 20:
                if isinstance(df.columns, pd.MultiIndex):
                    def pick(col):
                        cols = [c for c in df.columns if isinstance(c, tuple) and col in c]
                        if not cols:
                            return None

                        data = df[cols[0]]

                        # FIX: Handle both Series and DataFrame safely
                        if isinstance(data, pd.DataFrame):
                            return data.iloc[:, 0]
                        elif isinstance(data, pd.Series):
                            return data
                        return None

                    high_s = pick("High")
                    low_s = pick("Low")
                    close_s = pick("Close")
                else:
                    high_s = df.get("High")
                    low_s = df.get("Low")
                    close_s = df.get("Close")

                support_levels, resistance_levels = _calculate_support_resistance(high_s, low_s, close_s)
                sma20 = close_s.astype(float).ffill().bfill().rolling(20).mean().iloc[-1] if close_s is not None and len(close_s) >= 20 else None
                sma50 = close_s.astype(float).ffill().bfill().rolling(50).mean().iloc[-1] if close_s is not None and len(close_s) >= 50 else None

                tech = _calculate_entry_zone(current_price, support_levels, resistance_levels, sma20, sma50)
                entry_zone = (tech["entry_zone_low"], tech["entry_zone_high"])
                entry_explanation = tech["explanation"]
                logger.info(f"Using technical entry zone for {ticker}: {entry_zone}")
            else:
                entry_zone, entry_explanation = await self._fallback_entry_zone(ticker, current_price, intrinsic_value)
        except Exception as e:
            logger.warning(f"Technical entry zone failed for {ticker}: {e}, using fallback")
            entry_zone, entry_explanation = await self._fallback_entry_zone(ticker, current_price, intrinsic_value)

        # Target price and stop loss
        # For Financial Services stocks, perform_dcf_valuation() correctly returns
        # dcf_applicable=False — in that case it has no buy_zone or target_price.
        # We must not fall through and use current_price * 1.25 based on a stale/wrong price.
        # Instead we derive target/stop-loss from the intrinsic_value already computed
        # by _score_valuation (Excess Returns IV for banks, DCF IV for others).
        try:
            dcf = await perform_dcf_valuation(ticker, current_price)
            if "error" not in dcf and dcf.get("dcf_applicable", True) and dcf.get("target_price"):
                target_price = dcf.get("target_price", 0)
                stop_loss = dcf.get("stop_loss", 0)
            elif intrinsic_value and intrinsic_value > 0 and current_price and current_price > 0:
                # Use intrinsic value from scoring (Excess Returns for banks, DCF for others)
                # Target = intrinsic value; stop-loss = 15% below current price
                target_price = intrinsic_value
                stop_loss = current_price * 0.85
            elif current_price and current_price > 0:
                target_price = current_price * 1.25
                stop_loss = current_price * 0.85
            else:
                target_price = 0.0
                stop_loss = 0.0
        except Exception:
            if intrinsic_value and intrinsic_value > 0 and current_price and current_price > 0:
                target_price = intrinsic_value
                stop_loss = current_price * 0.85
            elif current_price and current_price > 0:
                target_price = current_price * 1.25
                stop_loss = current_price * 0.85
            else:
                target_price = 0.0
                stop_loss = 0.0

        time_horizon = 18 if overall_score >= 75 else 12 if overall_score >= 60 else 6

        return {
            "position_sizing": position_sizing,
            "entry_zone": entry_zone,
            "entry_explanation": entry_explanation,
            "target_price": target_price,
            "stop_loss": stop_loss,
            "time_horizon": time_horizon,
        }

    async def _fallback_entry_zone(self, ticker: str, current_price: Optional[float], intrinsic_value: float) -> tuple:
        """
        Compute a fallback entry zone when the technical entry zone calculation fails.

        Priority order:
          1. If intrinsic_value is valid AND within a credible range of current_price
             (within 2× or above 50% of current price), use it to anchor the zone.
          2. Otherwise anchor the zone to current_price directly.

        We deliberately do NOT call perform_dcf_valuation() here for financial stocks
        because it returns dcf_applicable=False with buy_zone=0, causing the zone to
        collapse to the wrong price (the bug that produced entry zone 884–910 for
        HDFCBANK when the price was 1857).
        """
        try:
            cp = current_price or 0.0
            if cp <= 0:
                return (0.0, 0.0), "Insufficient data for entry zone calculation"

            # Use intrinsic value if it is plausible relative to current price
            if intrinsic_value and intrinsic_value > 0:
                ratio = intrinsic_value / cp
                if 0.5 <= ratio <= 2.0:
                    # IV is within a credible range — anchor zone around current price
                    # discounted toward IV (or capped at current if IV > current)
                    anchor = min(cp, intrinsic_value)
                    lo = round(anchor * 0.95, 2)
                    hi = round(anchor * 1.02, 2)
                    label = "IV-anchored" if intrinsic_value < cp else "current price"
                    return (lo, hi), f"Fallback: {label} entry zone ₹{lo:.2f}–₹{hi:.2f}"

            # Default: ±5% band around current price
            lo = round(cp * 0.95, 2)
            hi = round(cp * 1.05, 2)
            return (lo, hi), f"Fallback: ±5% band around current price ₹{lo:.2f}–₹{hi:.2f}"
        except Exception as e:
            logger.error(f"Fallback entry zone failed for {ticker}: {e}")
            if current_price and current_price > 0:
                lo = round(current_price * 0.95, 2)
                hi = round(current_price * 1.05, 2)
                return (lo, hi), f"Emergency fallback: ₹{lo:.2f}–₹{hi:.2f}"
            return (0.0, 0.0), "Emergency fallback: No price data available"

    def _assess_risk_factors(self, pillar_scores: Dict[str, PillarScore]) -> Dict[str, Any]:
        fh = pillar_scores["financial_health"].score
        gov = pillar_scores["governance"].score
        risk_rating = (
            "Very High" if fh < 40 or gov < 40 else
            "High" if fh < 60 or gov < 60 else
            "Medium" if fh < 75 and gov < 75 else "Low"
        )
        key_risks = [f for p in pillar_scores.values() for f in p.negative_factors[:2]][:5]
        key_catalysts = [f for p in pillar_scores.values() for f in p.positive_factors[:2]][:5]
        return {"risk_rating": risk_rating, "key_risks": key_risks, "key_catalysts": key_catalysts}


async def score_stock_comprehensively(
    ticker: str,
    current_price: Optional[float] = None,
    custom_weights: Optional[ScoringWeights] = None,
) -> ComprehensiveScore:
    """Convenience function: perform comprehensive stock scoring."""
    return await ComprehensiveScoringEngine(custom_weights).score_ticker(ticker, current_price)
