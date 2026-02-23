"""
Strategic Investment Conviction Analysis Engine
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

import pandas as pd
import structlog
import yfinance as yf

logger = structlog.get_logger()


class ConvictionLevel(Enum):
    NO_INVESTMENT = "No Investment"
    LOW_CONVICTION = "Low Conviction"
    MEDIUM_CONVICTION = "Medium Conviction"
    HIGH_CONVICTION = "High Conviction"


@dataclass
class BusinessMoat:
    moat_type: str
    strength: float
    durability: float
    evidence: List[str]


@dataclass
class GrowthCatalyst:
    name: str
    timeline: str
    impact_potential: float
    probability: float
    description: str


@dataclass
class InvestmentThesis:
    business_summary: str
    key_investment_points: List[str]
    catalysts: List[GrowthCatalyst]
    risks: List[Dict[str, str]]
    valuation_summary: Dict[str, Any]
    conviction_score: float
    conviction_level: ConvictionLevel
    position_sizing: float


# ── Sector/industry reference data ──────────────────────────────────────────

_TAM_GROWTH = {
    "Technology": {"Software—Application": 12, "Software—Infrastructure": 15,
                   "Information Technology Services": 8, "Semiconductors": 6, "default": 10},
    "Healthcare": {"Biotechnology": 8, "Drug Manufacturers—General": 5,
                   "Medical Devices": 6, "default": 6},
    "Financial Services": {"Banks—Regional": 3, "Insurance": 4, "Asset Management": 5, "default": 4},
}
_SECULAR_TRENDS = {
    "Technology": {"trends": ["Digital Transformation", "Cloud Migration", "AI/ML Adoption", "Cybersecurity"],
                   "score": 85, "duration": "10+ years"},
    "Healthcare": {"trends": ["Aging Demographics", "Precision Medicine", "Digital Health"],
                   "score": 75, "duration": "15+ years"},
    "Financial Services": {"trends": ["Fintech Disruption", "Digital Banking", "Regulatory Technology"],
                           "score": 60, "duration": "5-10 years"},
}
_CYCLICALITY = {"Technology": 70, "Healthcare": 85, "Financial Services": 50,
                "Consumer Staples": 80, "Consumer Cyclical": 40, "Energy": 30, "Utilities": 85}
_RATE_SENSITIVITY = {"Financial Services": 30, "Real Estate": 25, "Utilities": 40,
                     "Technology": 70, "Healthcare": 75}
_REGULATORY_RISK = {"Financial Services": 40, "Healthcare": 50, "Utilities": 45,
                    "Technology": 70, "Consumer Staples": 80}
_SECTOR_PE = {"Technology": 25, "Healthcare": 20, "Financial Services": 12,
              "Consumer Cyclical": 18, "Industrials": 16}
_INNOVATION_BASE = {"Technology": 75, "Healthcare": 70, "Industrials": 55,
                    "Consumer Cyclical": 45, "Financial Services": 40, "Energy": 35, "Utilities": 30}
_SEGMENT_DATA: Dict[str, Any] = {
    "Technology/Software": [
        {"name": "Enterprise Software", "score": 75, "growth_rate": "12%", "description": "Core enterprise software solutions"},
        {"name": "Cloud Services", "score": 85, "growth_rate": "18%", "description": "Cloud infrastructure and platform services"},
        {"name": "Professional Services", "score": 65, "growth_rate": "8%", "description": "Implementation and consulting services"},
    ],
    "Technology/Semiconductors": [
        {"name": "Data Center Chips", "score": 80, "growth_rate": "15%", "description": "AI/ML and data center processors"},
        {"name": "Consumer Electronics", "score": 60, "growth_rate": "5%", "description": "Mobile and consumer device chips"},
        {"name": "Automotive", "score": 70, "growth_rate": "12%", "description": "Automotive semiconductor solutions"},
    ],
    "Healthcare": [
        {"name": "Pharmaceuticals", "score": 70, "growth_rate": "6%", "description": "Drug development and manufacturing"},
        {"name": "Medical Devices", "score": 75, "growth_rate": "8%", "description": "Medical device and diagnostic equipment"},
        {"name": "Healthcare Services", "score": 65, "growth_rate": "5%", "description": "Healthcare delivery and services"},
    ],
    "Financial Services": [
        {"name": "Retail Banking", "score": 60, "growth_rate": "3%", "description": "Consumer banking and lending"},
        {"name": "Investment Banking", "score": 70, "growth_rate": "8%", "description": "Corporate finance and capital markets"},
        {"name": "Asset Management", "score": 75, "growth_rate": "10%", "description": "Investment management and advisory"},
    ],
}
_INDUSTRY_RISKS: Dict[str, Any] = {
    "Technology": {"risks": ["Rapid technological obsolescence", "Cybersecurity threats",
                             "Regulatory scrutiny", "Talent competition"], "risk_score": 60},
    "Healthcare": {"risks": ["Regulatory changes", "Patent cliffs", "Pricing pressure",
                             "Clinical trial failures"], "risk_score": 55},
    "Financial Services": {"risks": ["Interest rate sensitivity", "Regulatory tightening",
                                     "Credit risk", "Fintech disruption"], "risk_score": 65},
    "Consumer Cyclical": {"risks": ["Economic sensitivity", "Consumer behavior changes",
                                    "Supply chain disruptions", "Competition intensity"], "risk_score": 70},
}
_COMPETITIVE_THREATS: Dict[str, Any] = {
    "Technology": {"threats": ["Rapid technological change", "New market entrants", "Platform competition"],
                   "risk_score": 60},
    "Healthcare": {"threats": ["Regulatory changes", "Patent expirations", "Generic competition"],
                   "risk_score": 50},
    "Financial Services": {"threats": ["Fintech disruption", "Regulatory tightening",
                                       "Digital transformation pressure"], "risk_score": 55},
}


# ── Helper functions ─────────────────────────────────────────────────────────

def _grade(score: float) -> str:
    return "A" if score >= 80 else "B" if score >= 65 else "C" if score >= 50 else "D"

def _conviction_level(score: float) -> ConvictionLevel:
    if score >= 80: return ConvictionLevel.HIGH_CONVICTION
    if score >= 65: return ConvictionLevel.MEDIUM_CONVICTION
    if score >= 45: return ConvictionLevel.LOW_CONVICTION
    return ConvictionLevel.NO_INVESTMENT

def _conviction_str(level: Any) -> str:
    if hasattr(level, "value"): return level.value
    return str(level)

def _position_size(score: float) -> float:
    if score >= 85: return 8.0
    if score >= 75: return 6.0
    if score >= 65: return 4.0
    if score >= 50: return 2.0
    return 0.0

def _strategic_rec(score: float) -> str:
    if score >= 80: return "Strong Buy - High Conviction"
    if score >= 65: return "Buy - Medium Conviction"
    if score >= 50: return "Hold - Low Conviction"
    return "Avoid - Insufficient Conviction"

def _market_cap_tier(mc: float) -> str:
    if mc > 200e9: return "Mega Cap"
    if mc > 10e9: return "Large Cap"
    if mc > 2e9: return "Mid Cap"
    return "Small Cap"

def _market_pos_desc(mc: float) -> str:
    if mc > 100e9: return "a market-leading position"
    if mc > 10e9: return "a strong competitive position"
    return "a developing market position"


# ── Analysis sub-functions ───────────────────────────────────────────────────

def _moats(sector: str, industry: str, mc: float) -> List[BusinessMoat]:
    moats = []
    if sector == "Technology":
        if "Software" in industry:
            moats.append(BusinessMoat("Switching Costs", 75, 85,
                                      ["Enterprise software integration complexity", "Training costs", "Data lock-in"]))
        if mc > 100e9:
            moats.append(BusinessMoat("Scale Advantages", 80, 70,
                                      ["R&D investment capacity", "Global infrastructure", "Talent acquisition"]))
    elif sector == "Financial Services":
        moats.append(BusinessMoat("Regulatory Barriers", 70, 90,
                                  ["Banking licenses", "Regulatory compliance", "Capital requirements"]))
    if not moats and mc > 10e9:
        moats.append(BusinessMoat("Scale Advantages", 50, 60, ["Market leadership", "Operational scale"]))
    return moats or [BusinessMoat("Limited Moats", 30, 40, ["Commodity business characteristics"])]


def _market_position(mc: float, sector: str, ticker: str, info: Dict) -> Dict[str, Any]:
    if mc > 100e9:
        score, desc = 85, "Market Leader"
    elif mc > 10e9:
        score, desc = 65, "Strong Player"
    else:
        score, desc = 45, "Smaller Player"
    advantages = []
    if mc > 50e9: advantages.append("Scale advantages")
    if info.get("grossMargins", 0) > 0.4: advantages.append("High gross margins")
    if sector == "Technology": advantages.extend(["Technology platform", "Network effects", "Data advantages"])
    if sector in ["Financial Services", "Healthcare", "Utilities"]: advantages.append("Regulatory barriers")
    return {"score": score, "description": desc, "market_cap_tier": _market_cap_tier(mc),
            "competitive_advantages": advantages}


def _management_quality(info: Dict) -> Dict[str, Any]:
    roe = info.get("returnOnEquity", 0) or 0
    roic = (info.get("returnOnAssets", 0) or 0) * 2
    de = info.get("debtToEquity", 0) or 0
    score = 50
    if roe > 0.15: score += 20
    elif roe > 0.10: score += 10
    if roic > 0.12: score += 15
    if de < 30: score += 10
    elif de > 100: score -= 15
    strengths = ([f"Strong ROE generation"] if roe > 0.15 else []) + \
                (["Efficient capital allocation"] if roic > 0.12 else []) + \
                (["Conservative debt management"] if de < 30 else [])
    concerns = ([f"Low ROE performance"] if roe and roe < 0.08 else []) + \
               (["Poor capital efficiency"] if roic < 0.06 else []) + \
               (["High leverage risk"] if de > 100 else [])
    return {"score": min(100, max(0, score)), "capital_allocation_score": score,
            "key_metrics": {"roe": roe, "roic_proxy": roic, "debt_to_equity": de},
            "strengths": strengths, "concerns": concerns}


def _financial_strength(info: Dict) -> Dict[str, Any]:
    cr = info.get("currentRatio", 1.0) or 1.0
    qr = info.get("quickRatio", 0.8) or 0.8
    de = info.get("debtToEquity", 0) or 0
    ic = info.get("interestCoverage", 0) or 0
    score = 50
    if cr > 2.0: score += 15
    elif cr > 1.5: score += 10
    elif cr < 1.0: score -= 20
    if de < 20: score += 20
    elif de < 50: score += 10
    elif de > 100: score -= 25
    if ic > 10: score += 15
    elif ic > 5: score += 10
    elif ic < 2: score -= 30
    return {"score": min(100, max(0, score)),
            "liquidity_ratios": {"current_ratio": cr, "quick_ratio": qr},
            "leverage_metrics": {"debt_to_equity": de, "interest_coverage": ic},
            "financial_grade": _grade(score),
            "key_strengths": ([f"Strong liquidity"] if cr > 2 else []) + ([f"Low debt"] if de < 30 else []) + ([f"Strong interest coverage"] if ic > 10 else []),
            "key_risks": ([f"Liquidity concerns"] if cr < 1 else []) + ([f"High debt"] if de > 100 else []) + ([f"Interest coverage risk"] if ic < 2 else [])}


def _tam_analysis(sector: str, industry: str) -> Dict[str, Any]:
    sd = _TAM_GROWTH.get(sector, {"default": 5})
    rate = sd.get(industry, sd["default"])
    score = min(100, max(0, rate * 6))
    drivers = {"Technology": ["Digital transformation", "Cloud adoption", "AI/ML integration"],
               "Healthcare": ["Aging population", "Medical innovation", "Precision medicine"],
               "Financial Services": ["Fintech adoption", "Digital banking", "Regulatory technology"]
               }.get(sector, ["Industry consolidation", "Market expansion"])
    return {"score": score, "estimated_cagr": rate,
            "market_size_trend": "Expanding" if rate > 6 else "Stable" if rate > 3 else "Declining",
            "key_drivers": drivers}


def _geographic_expansion(ticker: str, info: Dict) -> Dict[str, Any]:
    mc = info.get("marketCap", 0) or 0
    sector = (info.get("sector") or "").lower()
    if ticker.endswith((".NS", ".BO")):
        score = 40
        score += 25 if mc > 100e9 else 20 if mc > 50e9 else 10 if mc > 10e9 else 5
        if any(k in sector for k in ["bank", "financial"]):
            score -= 15; desc = "Regulatory constraints limit international expansion"
        elif any(k in sector for k in ["tech", "software"]):
            score += 20; desc = "Digital nature enables easier international expansion"
        elif "pharma" in sector:
            score -= 10; desc = "Regulatory complexity affects international expansion"
        elif any(k in sector for k in ["energy", "oil"]):
            score += 15; desc = "Energy sector typically has global operations"
        else:
            desc = "Moderate expansion potential"
    else:
        score, desc = 60, "Established global presence"
    score = min(100, max(0, score))
    return {"score": score, "description": desc,
            "expansion_potential": "High" if score > 70 else "Medium" if score > 50 else "Low"}


def _valuation_asymmetry(info: Dict) -> Dict[str, Any]:
    price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
    pe, fpe, peg, pb = (info.get(k, 0) or 0 for k in
                         ["trailingPE", "forwardPE", "pegRatio", "priceToBook"])
    sector = info.get("sector", "")
    bench_pe = _SECTOR_PE.get(sector, 18)
    score = 50
    if pe > 0:
        disc = (bench_pe - pe) / bench_pe
        score += 30 if disc > 0.3 else 15 if disc > 0.1 else -25 if disc < -0.3 else -10 if disc < -0.1 else 0
    if 0 < peg < 1: score += 20
    elif peg > 2: score -= 15
    score = min(100, max(0, score))
    disc_val = (bench_pe - pe) / bench_pe if pe else 0
    asym = ({"asymmetry": "Favorable", "upside_potential": "High", "downside_risk": "Limited"} if score > 70
            else {"asymmetry": "Neutral", "upside_potential": "Moderate", "downside_risk": "Moderate"} if score > 40
            else {"asymmetry": "Unfavorable", "upside_potential": "Limited", "downside_risk": "High"})
    return {"score": score,
            "current_metrics": {"current_price": price, "trailing_pe": pe, "forward_pe": fpe,
                                 "peg_ratio": peg, "price_to_book": pb},
            "relative_valuation": {"sector_pe_benchmark": bench_pe, "pe_discount_premium": disc_val,
                                   "valuation_tier": "Attractive" if score >= 75 else "Fair" if score >= 50 else "Expensive"},
            "asymmetry_assessment": asym, "margin_of_safety": 0.0}


def _macro_resilience(sector: str, ticker: str, info: Dict) -> Dict[str, Any]:
    cyc = _CYCLICALITY.get(sector, 60)
    rate_score = _RATE_SENSITIVITY.get(sector, 60)
    reg_score = _REGULATORY_RISK.get(sector, 65)
    fx_score = (60 if ticker.endswith((".NS", ".BO")) else 80)
    macro_score = cyc * 0.4 + rate_score * 0.3 + fx_score * 0.2 + reg_score * 0.1
    return {"score": min(100, max(0, macro_score)),
            "cyclicality_assessment": {"score": cyc,
                                       "sector_cyclicality": "Low Cyclicality" if cyc > 75 else "Moderate Cyclicality" if cyc > 50 else "High Cyclicality"},
            "interest_rate_sensitivity": {"score": rate_score, "sensitivity": "Low" if rate_score > 65 else "Moderate" if rate_score > 45 else "High"},
            "currency_exposure": {"score": fx_score, "primary_currency": "INR" if ticker.endswith((".NS", ".BO")) else "USD",
                                  "fx_risk": "Moderate" if fx_score == 60 else "Low"},
            "regulatory_risk": {"score": reg_score, "risk_level": "Low" if reg_score > 70 else "Moderate" if reg_score > 50 else "High"},
            "macro_resilience_grade": _grade(macro_score)}


def _growth_drivers(sector: str, industry: str, mc: float, info: Dict) -> Dict[str, Any]:
    drivers = []
    # Revenue
    rev_score = 50
    rev_d: List[str] = []
    if sector == "Technology":
        if "Software" in industry: rev_d = ["SaaS subscription growth", "Digital transformation adoption", "Cloud migration trends"]; rev_score = 80
        elif "Semiconductors" in industry: rev_d = ["AI/ML chip demand", "5G infrastructure buildout", "Automotive electronics growth"]; rev_score = 75
    elif sector == "Healthcare": rev_d = ["Aging population demographics", "Precision medicine adoption", "Digital health integration"]; rev_score = 70
    elif sector == "Financial Services": rev_d = ["Digital banking adoption", "Fintech integration", "Regulatory technology needs"]; rev_score = 65
    drivers.append({"type": "Revenue Growth", "score": rev_score, "drivers": rev_d,
                    "description": f"Revenue growth driven by {len(rev_d)} key factors"})

    # Market expansion
    exp_score, exp_d = 50, []
    if mc > 50e9: exp_d.append("International market expansion"); exp_score += 20
    elif mc > 10e9: exp_d.append("Regional market expansion"); exp_score += 15
    if sector == "Technology": exp_d += ["Adjacent technology markets", "Platform ecosystem expansion"]; exp_score += 25
    elif sector == "Healthcare": exp_d += ["Therapeutic area expansion", "Diagnostic market entry"]; exp_score += 20
    drivers.append({"type": "Market Expansion", "score": min(100, exp_score), "drivers": exp_d,
                    "description": f"Market expansion through {len(exp_d)} strategic initiatives"})

    # Innovation
    innov_score, innov_d = 50, []
    summary = (info.get("businessSummary") or "").lower()
    if "research" in summary or "development" in summary: innov_d.append("R&D investment"); innov_score += 15
    if "innovation" in summary or "technology" in summary: innov_d.append("Technology innovation"); innov_score += 20
    if sector == "Technology": innov_d += ["AI/ML capabilities", "Platform development", "API ecosystem"]; innov_score += 25
    elif sector == "Healthcare": innov_d += ["Drug discovery pipeline", "Medical device innovation", "Digital therapeutics"]; innov_score += 20
    drivers.append({"type": "Innovation", "score": min(100, innov_score), "drivers": innov_d,
                    "description": f"Innovation-driven growth through {len(innov_d)} key areas"})

    # Efficiency
    eff_score, eff_d = 50, []
    if mc > 100e9: eff_d.append("Economies of scale"); eff_score += 20
    if "automation" in summary: eff_d.append("Process automation"); eff_score += 15
    if "digital" in summary: eff_d.append("Digital transformation"); eff_score += 15
    if "platform" in summary: eff_d.append("Platform efficiency"); eff_score += 10
    drivers.append({"type": "Operational Efficiency", "score": min(100, eff_score), "drivers": eff_d,
                    "description": f"Efficiency gains through {len(eff_d)} improvements"})

    overall = sum(d["score"] for d in drivers) / len(drivers)
    return {"score": min(100, max(0, overall)), "drivers": drivers,
            "primary_drivers": [d for d in drivers if d["score"] > 70],
            "secondary_drivers": [d for d in drivers if 50 <= d["score"] <= 70],
            "growth_potential": "High" if overall > 70 else "Medium" if overall > 50 else "Low"}


def _segment_performance(sector: str, industry: str) -> Dict[str, Any]:
    key = f"{sector}/{industry}" if f"{sector}/{industry}" in _SEGMENT_DATA else sector
    segments = _SEGMENT_DATA.get(key, [{"name": "Core Business", "score": 60,
                                         "growth_rate": "5%", "description": "Primary business operations"}])
    scores = [s["score"] for s in segments]
    overall = sum(scores) / len(scores)
    return {"score": min(100, max(0, overall)), "segments": segments,
            "top_performing_segment": max(segments, key=lambda x: x["score"]),
            "growth_segments": [s for s in segments if s["score"] > 70],
            "declining_segments": [s for s in segments if s["score"] < 40]}


def _competitive_landscape(sector: str, industry: str, mc: float, ticker: str, info: Dict) -> Dict[str, Any]:
    pos_score = (90 if mc > 500e9 else 75 if mc > 100e9 else 60 if mc > 10e9 else 40)
    pos_desc = ("Market Leader" if mc > 500e9 else "Strong Player" if mc > 100e9
                else "Established Player" if mc > 10e9 else "Smaller Player")
    threats = _COMPETITIVE_THREATS.get(sector, {"threats": ["Competitive pressure"], "risk_score": 50})
    adv_score = 50
    advantages = []
    if mc > 100e9: advantages.append("Economies of scale"); adv_score += 20
    if mc > 50e9: advantages.append("Brand recognition"); adv_score += 15
    if sector == "Technology": advantages += ["Technology platform", "Network effects", "Data advantages"]; adv_score += 25
    if sector in ["Financial Services", "Healthcare", "Utilities"]: advantages.append("Regulatory barriers"); adv_score += 15
    comp_score = (pos_score * 0.4 + (100 - threats["risk_score"]) * 0.3 + min(100, adv_score) * 0.3)
    return {"score": min(100, max(0, comp_score)),
            "positioning": {"position": pos_desc, "score": pos_score,
                            "description": f"{pos_desc} with {'significant' if pos_score > 80 else 'moderate'} competitive advantages"},
            "threats": {**threats, "risk_level": "High" if threats["risk_score"] > 60 else "Medium" if threats["risk_score"] > 40 else "Low"},
            "advantages": {"advantages": advantages, "score": min(100, adv_score),
                           "advantage_strength": "Strong" if adv_score > 70 else "Moderate" if adv_score > 50 else "Limited"},
            "competitive_strength": "Strong" if comp_score > 70 else "Moderate" if comp_score > 50 else "Weak"}


def _industry_outlook(sector: str, industry: str) -> Dict[str, Any]:
    sd = _TAM_GROWTH.get(sector, {"default": 4})
    rate = sd.get(industry, sd.get("default", 4))
    growth = {"growth_rate": rate, "score": min(100, max(0, rate * 8)),
              "outlook": "High Growth" if rate > 8 else "Moderate Growth" if rate > 4 else "Low Growth"}
    trends_map = {
        "Technology": {"trends": ["Digital transformation", "AI/ML integration", "Cloud-first", "Cybersecurity"], "score": 85},
        "Healthcare": {"trends": ["Precision medicine", "Digital health", "Value-based care", "Telemedicine"], "score": 75},
        "Financial Services": {"trends": ["Digital banking", "Fintech integration", "Regulatory technology", "Sustainable finance"], "score": 70},
        "Consumer Cyclical": {"trends": ["E-commerce", "Sustainability", "Direct-to-consumer", "Personalization"], "score": 65},
    }
    trends = trends_map.get(sector, {"trends": ["Industry consolidation", "Digital adoption"], "score": 50})
    risks = _INDUSTRY_RISKS.get(sector, {"risks": ["Economic sensitivity", "Competitive pressure"], "risk_score": 50})
    outlook_score = growth["score"] * 0.5 + trends["score"] * 0.3 + (100 - risks["risk_score"]) * 0.2
    return {"score": min(100, max(0, outlook_score)), "growth_outlook": growth,
            "trends": {**trends, "trend_strength": "Strong" if trends["score"] > 70 else "Moderate" if trends["score"] > 50 else "Weak"},
            "risks": {**risks, "risk_level": "High" if risks["risk_score"] > 60 else "Medium" if risks["risk_score"] > 40 else "Low"},
            "overall_outlook": "Positive" if outlook_score > 70 else "Neutral" if outlook_score > 50 else "Negative"}


def _growth_catalysts(sector: str, industry: str, info: Dict) -> List[GrowthCatalyst]:
    cats = []
    if sector == "Technology":
        cats.append(GrowthCatalyst("AI/ML Product Integration", "6-18 months", 75, 80,
                                   "Integration of AI capabilities into existing products"))
        cats.append(GrowthCatalyst("Cloud Migration Acceleration", "1-3 years", 60, 85,
                                   "Continued enterprise cloud adoption"))
    if (info.get("marketCap") or 0) > 10e9:
        cats.append(GrowthCatalyst("International Expansion", "1-3 years", 50, 60,
                                   "Geographic market expansion opportunities"))
    return cats


class StrategicConvictionEngine:
    """Analyzes stocks for strategic investment conviction beyond basic metrics."""

    def __init__(self):
        self.industry_tam_data: Dict = {}
        self.competitive_landscape: Dict = {}

    async def _fetch_company_data(self, ticker: str) -> Dict[str, Any]:
        def _fetch():
            t = yf.Ticker(ticker)
            return {"info": t.info or {}, "financials": t.financials,
                    "balance_sheet": t.balance_sheet, "cashflow": t.cashflow,
                    "history": t.history(period="5y"), "recommendations": t.recommendations,
                    "institutional_holders": t.institutional_holders, "major_holders": t.major_holders}
        return await asyncio.to_thread(_fetch)

    async def _analyze_business_quality(self, ticker: str, data: Dict) -> Dict[str, Any]:
        info = data["info"]
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        mc = info.get("marketCap", 0) or 0
        moats = _moats(sector, industry, mc)
        mpos = _market_position(mc, sector, ticker, info)
        mgmt = _management_quality(info)
        fin = _financial_strength(info)
        comp = _competitive_landscape(sector, industry, mc, ticker, info)
        ind = _industry_outlook(sector, industry)
        score = (sum(m.strength for m in moats) / len(moats) * 0.25 +
                 mpos["score"] * 0.20 + mgmt["score"] * 0.15 + fin["score"] * 0.10 +
                 comp["score"] * 0.20 + ind["score"] * 0.10) if moats else 0
        strengths = (["Strong competitive moats"] if moats and max(m.strength for m in moats) > 70 else []) + \
                    (["Market leadership position"] if mpos["score"] > 70 else []) + \
                    (["High-quality management team"] if mgmt["score"] > 70 else []) + \
                    (["Strong balance sheet"] if fin["score"] > 70 else [])
        concerns = (["Limited competitive advantages"] if not moats or max(m.strength for m in moats) < 50 else []) + \
                   (["Weak market position"] if mpos["score"] < 50 else []) + \
                   (["Management execution concerns"] if mgmt["score"] < 50 else []) + \
                   (["Balance sheet weakness"] if fin["score"] < 50 else [])
        return {"score": min(100, max(0, score)),
                "competitive_moats": [{"type": m.moat_type, "strength": m.strength,
                                       "durability": m.durability, "evidence": m.evidence} for m in moats],
                "market_position": mpos, "management_quality": mgmt, "financial_strength": fin,
                "key_strengths": strengths, "key_concerns": concerns,
                "competitive_analysis": comp, "industry_outlook": ind}

    async def _analyze_growth_runway(self, ticker: str, data: Dict) -> Dict[str, Any]:
        info = data["info"]
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        mc = info.get("marketCap", 0) or 0
        tam = _tam_analysis(sector, industry)
        secular = _SECULAR_TRENDS.get(sector, {"trends": ["Industry Consolidation"], "score": 40, "duration": "Variable"})
        innov = _INNOVATION_BASE.get(sector, 50)
        if mc > 100e9: innov += 10
        elif mc > 10e9: innov += 5
        gm = info.get("grossMargins") or 0
        if gm > 0.5: innov += 10
        elif gm > 0.3: innov += 5
        innov = min(100, innov)
        geo = _geographic_expansion(ticker, info)
        drivers = _growth_drivers(sector, industry, mc, info)
        segs = _segment_performance(sector, industry)
        catalysts = _growth_catalysts(sector, industry, info)
        score = (tam["score"] * 0.25 + secular["score"] * 0.20 + innov * 0.15 +
                 geo["score"] * 0.10 + drivers["score"] * 0.20 + segs["score"] * 0.10)
        runway = ("10+ years" if tam["score"] > 70 and secular["score"] > 70
                  else "5-10 years" if tam["score"] > 50 or secular["score"] > 60 else "3-5 years")
        return {"score": min(100, max(0, score)), "tam_analysis": tam, "secular_trends": secular,
                "innovation_pipeline": innov, "geographic_expansion": geo,
                "growth_catalysts": catalysts, "growth_runway_years": runway,
                "growth_drivers": drivers, "segment_performance": segs}

    async def _analyze_valuation_asymmetry(self, ticker: str, data: Dict) -> Dict[str, Any]:
        return _valuation_asymmetry(data["info"])

    async def _analyze_macro_resilience(self, ticker: str, data: Dict) -> Dict[str, Any]:
        info = data["info"]
        return _macro_resilience(info.get("sector", ""), ticker, info)

    def _calculate_conviction_score(self, bq, gr, va, mr) -> float:
        return min(100, max(0, bq["score"] * 0.40 + gr["score"] * 0.25 +
                            va["score"] * 0.20 + mr["score"] * 0.15))

    async def analyze_conviction(self, ticker: str) -> Dict[str, Any]:
        try:
            data = await self._fetch_company_data(ticker)
            bq = await self._analyze_business_quality(ticker, data)
            gr = await self._analyze_growth_runway(ticker, data)
            va = await self._analyze_valuation_asymmetry(ticker, data)
            mr = await self._analyze_macro_resilience(ticker, data)
            score = self._calculate_conviction_score(bq, gr, va, mr)
            info = data["info"]
            company = info.get("longName", ticker)
            sector = info.get("sector", "")
            moat_types = ", ".join(m["type"] for m in bq["competitive_moats"])
            points = []
            if bq["score"] > 70: points.append(f"Strong competitive position with {moat_types}")
            if gr["score"] > 70: points.append(f"Benefiting from secular trends: {', '.join(gr['secular_trends'].get('trends', [])[:2])}")
            if va["score"] > 60: points.append("Attractive valuation with asymmetric risk/reward profile")
            risks = []
            if va["score"] < 40: risks.append({"risk": "Valuation premium to peers", "mitigation": "Monitor earnings growth and multiple compression"})
            if mr["score"] < 60: risks.append({"risk": "Economic cycle sensitivity", "mitigation": "Track leading indicators and adjust position size"})
            return {
                "ticker": ticker,
                "conviction_analysis": {
                    "business_quality": bq, "growth_runway": gr,
                    "valuation_asymmetry": va, "macro_resilience": mr,
                    "overall_conviction_score": score,
                    "conviction_level": _conviction_str(_conviction_level(score)),
                    "strategic_recommendation": _strategic_rec(score),
                    "position_sizing_pct": _position_size(score),
                    "investment_thesis": {
                        "business_summary": f"{company} is a {sector.lower()} company with {_market_pos_desc(info.get('marketCap', 0) or 0)}.",
                        "key_investment_points": points,
                        "catalysts": gr.get("growth_catalysts", []),
                        "risks": risks,
                        "valuation_summary": {"current_price": va["current_metrics"]["current_price"],
                                              "margin_of_safety": va.get("margin_of_safety", 0),
                                              "valuation_tier": va["relative_valuation"]["valuation_tier"]},
                        "conviction_score": score,
                        "position_sizing": _position_size(score),
                    }
                }
            }
        except Exception as e:
            import traceback; traceback.print_exc()
            return {"ticker": ticker, "error": f"Strategic conviction analysis failed: {e}",
                    "conviction_analysis": None}


async def analyze_strategic_conviction(ticker: str) -> Dict[str, Any]:
    return await StrategicConvictionEngine().analyze_conviction(ticker)
