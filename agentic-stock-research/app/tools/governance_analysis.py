"""
Corporate Governance & Red Flag Analysis
Comprehensive governance scoring and red flag detection, India-focused.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import yfinance as yf

from app.utils.rate_limiter import get_yahoo_client

logger = logging.getLogger(__name__)


# ---------- data models ----------

@dataclass
class GovernanceMetrics:
    promoter_holding_pct: Optional[float] = None
    promoter_pledge_pct: Optional[float] = None
    institutional_holding_pct: Optional[float] = None
    public_holding_pct: Optional[float] = None
    independent_directors_pct: Optional[float] = None
    board_size: Optional[int] = None
    board_meetings_per_year: Optional[int] = None
    auditor_tenure_years: Optional[int] = None
    auditor_changes_3yr: Optional[int] = None
    audit_opinion_qualified: Optional[bool] = None
    rpt_as_pct_revenue: Optional[float] = None
    rpt_as_pct_profit: Optional[float] = None
    large_rpt_count: Optional[int] = None
    insider_buying_12m: Optional[float] = None
    insider_selling_12m: Optional[float] = None
    management_compensation_growth: Optional[float] = None


@dataclass
class RedFlag:
    category: str
    severity: str          # Low | Medium | High | Critical
    description: str
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    impact_score: float = 0.0  # 0-10


# ---------- thresholds (SEBI-aligned) ----------

_T = {
    "promoter_pledge_warning":   20.0,
    "promoter_pledge_critical":  50.0,
    "promoter_holding_low":      25.0,
    "promoter_holding_high":     75.0,
    "independent_directors_min": 33.3,
    "rpt_revenue_warning":       10.0,
    "rpt_revenue_critical":      20.0,
    "auditor_changes_warning":    2,
    "insider_selling_warning":   1_000_000,
    "debt_to_equity_high":       200.0,
    "interest_coverage_low":     2.0,
}


# ---------- data fetch ----------

async def _fetch_governance_data(ticker: str) -> Optional[Dict[str, Any]]:
    """Fetch info, institutional holders, and insider transactions via rate-limited client."""
    try:
        yahoo = get_yahoo_client()
        info = await yahoo.get_info(ticker)

        loop = asyncio.get_event_loop()
        t = await loop.run_in_executor(None, lambda: yf.Ticker(ticker))

        async def _get(attr):
            try:
                return await loop.run_in_executor(None, lambda: getattr(t, attr))
            except Exception:
                return None

        await yahoo.client.rate_limiter.acquire()
        try:
            institutional_holders = await _get("institutional_holders")
            insider_transactions   = await _get("insider_transactions")
        finally:
            yahoo.client.rate_limiter.release()

        return {"info": info,
                "institutional_holders": institutional_holders,
                "insider_transactions": insider_transactions}
    except Exception as e:
        logger.error(f"Governance data fetch failed for {ticker}: {e}")
        return None


# ---------- metric extraction ----------

def _extract_metrics(company_data: Dict[str, Any]) -> GovernanceMetrics:
    info = company_data["info"]
    m = GovernanceMetrics()

    held_inst = info.get("heldPercentInstitutions")
    m.institutional_holding_pct = held_inst * 100 if held_inst else None
    m.promoter_holding_pct      = m.institutional_holding_pct  # proxy (yfinance limitation)
    m.auditor_changes_3yr       = 0

    txn = company_data.get("insider_transactions")
    if txn is not None and not txn.empty and "Value" in txn.columns:
        cutoff = datetime.now() - timedelta(days=365)
        recent = txn[txn.index >= cutoff] if hasattr(txn.index, "date") else txn
        if not recent.empty and "Transaction" in recent.columns:
            m.insider_buying_12m  = recent[recent["Transaction"] == "Buy"]["Value"].sum()
            m.insider_selling_12m = recent[recent["Transaction"] == "Sale"]["Value"].sum()

    return m


# ---------- red flag detection ----------

def _detect_red_flags(m: GovernanceMetrics, info: Dict[str, Any]) -> List[RedFlag]:
    flags: List[RedFlag] = []

    def _flag(cat, sev, desc, val=None, thr=None, impact=0.0):
        flags.append(RedFlag(cat, sev, desc, val, thr, impact))

    # Promoter pledge
    if m.promoter_pledge_pct is not None:
        if m.promoter_pledge_pct > _T["promoter_pledge_critical"]:
            _flag("Ownership Risk", "Critical",
                  f"Extremely high promoter pledge {m.promoter_pledge_pct:.1f}%",
                  m.promoter_pledge_pct, _T["promoter_pledge_critical"], 9.0)
        elif m.promoter_pledge_pct > _T["promoter_pledge_warning"]:
            _flag("Ownership Risk", "High",
                  f"High promoter pledge {m.promoter_pledge_pct:.1f}%",
                  m.promoter_pledge_pct, _T["promoter_pledge_warning"], 6.0)

    # Promoter holding
    if m.promoter_holding_pct is not None:
        if m.promoter_holding_pct < _T["promoter_holding_low"]:
            _flag("Ownership Risk", "Medium",
                  f"Low promoter holding {m.promoter_holding_pct:.1f}%",
                  m.promoter_holding_pct, _T["promoter_holding_low"], 4.0)
        elif m.promoter_holding_pct > _T["promoter_holding_high"]:
            _flag("Liquidity Risk", "Medium",
                  f"Very high promoter holding {m.promoter_holding_pct:.1f}% limits float",
                  m.promoter_holding_pct, _T["promoter_holding_high"], 3.0)

    # Board independence
    if m.independent_directors_pct is not None and m.independent_directors_pct < _T["independent_directors_min"]:
        _flag("Board Governance", "High",
              f"Insufficient independent directors {m.independent_directors_pct:.1f}%",
              m.independent_directors_pct, _T["independent_directors_min"], 7.0)

    # Auditor churn
    if m.auditor_changes_3yr is not None and m.auditor_changes_3yr > _T["auditor_changes_warning"]:
        _flag("Financial Transparency", "High",
              f"Frequent auditor changes: {m.auditor_changes_3yr} in 3 yrs",
              m.auditor_changes_3yr, _T["auditor_changes_warning"], 8.0)

    # Related party transactions
    if m.rpt_as_pct_revenue is not None:
        if m.rpt_as_pct_revenue > _T["rpt_revenue_critical"]:
            _flag("Related Party Risk", "Critical",
                  f"Excessive RPTs {m.rpt_as_pct_revenue:.1f}% of revenue",
                  m.rpt_as_pct_revenue, _T["rpt_revenue_critical"], 9.0)
        elif m.rpt_as_pct_revenue > _T["rpt_revenue_warning"]:
            _flag("Related Party Risk", "Medium",
                  f"High RPTs {m.rpt_as_pct_revenue:.1f}% of revenue",
                  m.rpt_as_pct_revenue, _T["rpt_revenue_warning"], 5.0)

    # Insider selling
    if m.insider_selling_12m and m.insider_selling_12m > _T["insider_selling_warning"]:
        _flag("Management Confidence", "Medium",
              f"Significant insider selling ₹{m.insider_selling_12m:,.0f} in 12m",
              m.insider_selling_12m, _T["insider_selling_warning"], 4.0)

    # Leverage
    d2e = info.get("debtToEquity", 0)
    if d2e and d2e > _T["debt_to_equity_high"]:
        _flag("Financial Risk", "High",
              f"High leverage D/E {d2e:.1f}%", d2e, _T["debt_to_equity_high"], 7.0)

    # Interest coverage
    ebitda, interest = info.get("ebitda"), info.get("interestExpense")
    if ebitda and interest and interest > 0:
        ic = ebitda / interest
        if ic < _T["interest_coverage_low"]:
            sev = "Critical" if ic < 1.0 else "High"
            _flag("Financial Risk", sev,
                  f"Poor interest coverage {ic:.1f}x",
                  ic, _T["interest_coverage_low"], 8.0 if ic < 1 else 6.0)

    return flags


# ---------- scoring & grading ----------

def _score(m: GovernanceMetrics, flags: List[RedFlag]) -> float:
    penalty = (
        sum(1 for f in flags if f.severity == "Critical") * 15
        + sum(1 for f in flags if f.severity == "High")   *  8
        + sum(1 for f in flags if f.severity == "Medium") *  4
        + sum(f.impact_score for f in flags)               *  0.5
    )
    bonus = (
        (5.0 if m.independent_directors_pct and m.independent_directors_pct > 50 else 0)
        + (3.0 if m.insider_buying_12m and m.insider_buying_12m > 0 else 0)
    )
    return round(max(0.0, min(100.0, 75.0 - penalty + bonus)), 1)


_GRADES = [(85,"A+"), (80,"A"), (75,"A-"), (70,"B+"), (65,"B"), (60,"B-"),
           (55,"C+"), (50,"C"), (45,"C-"), (40,"D"), (0,"F")]

def _grade(score: float) -> str:
    return next(g for thr, g in _GRADES if score >= thr)


def _recommendations(flags: List[RedFlag], score: float) -> List[str]:
    recs = []
    critical = [f for f in flags if f.severity == "Critical"]
    high     = [f for f in flags if f.severity == "High"]
    if critical:
        recs += ["⚠️ CRITICAL: Address critical governance issues immediately"] + [f"  • {f.description}" for f in critical]
    if high:
        recs += ["🔴 HIGH PRIORITY: Resolve significant governance concerns"] + [f"  • {f.description}" for f in high[:3]]
    if score < 60:
        recs += ["📊 Governance below acceptable standards", "🔍 Conduct thorough due diligence"]
    elif score < 75:
        recs.append("📈 Moderate governance — monitor key metrics")
    else:
        recs.append("✅ Good governance standards maintained")
    return recs


# ---------- public API ----------

async def analyze_corporate_governance(ticker: str) -> Dict[str, Any]:
    """Perform comprehensive corporate governance analysis for a ticker."""
    try:
        data = await _fetch_governance_data(ticker)
        if not data:
            return {"error": "Unable to fetch governance data"}

        metrics  = _extract_metrics(data)
        flags    = _detect_red_flags(metrics, data["info"])
        gov_score = _score(metrics, flags)

        return {
            "ticker": ticker,
            "governance_score": gov_score,
            "governance_grade": _grade(gov_score),
            "metrics": metrics.__dict__,
            "red_flags": [
                {"category": f.category, "severity": f.severity, "description": f.description,
                 "metric_value": f.metric_value, "threshold": f.threshold, "impact_score": f.impact_score}
                for f in flags
            ],
            "recommendations": _recommendations(flags, gov_score),
            "analysis_date": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Governance analysis failed for {ticker}: {e}")
        return {"error": str(e)}
