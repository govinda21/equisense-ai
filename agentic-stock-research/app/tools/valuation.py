from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List
import asyncio
import yfinance as yf
import pandas as pd

from app.tools.finance import fetch_info


def _safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        f = float(x)
        if f != f:
            return None
        return f
    except Exception:
        return None


def _get_latest_fcf(ticker: str, info: Dict[str, Any]) -> Optional[float]:
    # Prefer info.freeCashflow
    fcf = info.get("freeCashflow")
    fcf_val = _safe_float(fcf)
    if fcf_val is not None:
        return fcf_val
    # Fallback to cashflow table
    try:
        t = yf.Ticker(ticker)
        cf = t.cashflow  # type: ignore[attr-defined]
        if cf is None or getattr(cf, "empty", True):
            return None
        ocf_keys = [
            "Total Cash From Operating Activities",
            "Cash Flow From Continuing Operating Activities",
            "Operating Cash Flow",
            "Net Cash From Operating Activities",
        ]
        capex_keys = [
            "Capital Expenditures",
            "Capital Expenditure",
            "Capex",
            "Purchase Of Property Plant Equipment",
        ]
        ocf_series = next((cf.loc[k].dropna() for k in ocf_keys if k in cf.index), None)
        capex_series = next((cf.loc[k].dropna() for k in capex_keys if k in cf.index), None)
        if ocf_series is not None and len(ocf_series) > 0 and capex_series is not None and len(capex_series) > 0:
            ocf_latest = _safe_float(ocf_series.iloc[-1])
            capex_latest = _safe_float(capex_series.iloc[-1])
            if ocf_latest is not None and capex_latest is not None:
                return ocf_latest + capex_latest
    except Exception:
        return None
    return None


def _dcf_price_band(
    fcf0: float,
    shares_outstanding: Optional[float],
    market_cap: Optional[float],
    growth_base: float,
    discount_rate_base: float,
    terminal_growth_base: float,
) -> Dict[str, Any]:
    # Scenarios
    scenarios = {
        "low": {
            "g": max(0.0, growth_base - 0.02),
            "r": max(0.05, discount_rate_base + 0.01),
            "tg": max(0.0, terminal_growth_base - 0.005),
        },
        "base": {"g": growth_base, "r": discount_rate_base, "tg": terminal_growth_base},
        "high": {"g": growth_base + 0.02, "r": max(0.05, discount_rate_base - 0.01), "tg": terminal_growth_base + 0.005},
    }

    def _pv(g: float, r: float, tg: float) -> float:
        # 5-year DCF with terminal value as growing perpetuity on year 5 FCF
        fcf = fcf0
        pv = 0.0
        for t in range(1, 6):
            fcf *= (1.0 + g)
            pv += fcf / ((1.0 + r) ** t)
        tv = fcf * (1.0 + tg) / (r - tg) if r > tg else 0.0
        pv += tv / ((1.0 + r) ** 5)
        return pv

    band_caps: Dict[str, float] = {k: _pv(**v) for k, v in scenarios.items()}
    def _to_price(cap: float) -> Optional[float]:
        if shares_outstanding and shares_outstanding > 0:
            return cap / shares_outstanding
        return None

    prices = {k: _to_price(v) for k, v in band_caps.items()}
    out: Dict[str, Any] = {
        "market_cap": market_cap,
        "intrinsic_market_cap": band_caps,
        "intrinsic_price": prices,
    }
    return out


async def compute_valuation(ticker: str) -> Dict[str, Any]:
    """
    Enhanced multi-model valuation including DCF, DDM, Comparables, and sensitivity analysis.
    """
    
    def _enhanced_valuation() -> Dict[str, Any]:
        try:
            # Get comprehensive company data
            t = yf.Ticker(ticker)
            info = t.info or {}
            
            # Extract key metrics
            market_cap = _safe_float(info.get("marketCap"))
            current_price = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
            shares_outstanding = _safe_float(info.get("sharesOutstanding"))
            dividend_yield = _safe_float(info.get("dividendYield"))
            beta = _safe_float(info.get("beta", 1.0))
            
            # Base inputs
            fcf0 = _get_latest_fcf(ticker, info)
            revenue_growth = _safe_float(info.get("revenueGrowth"))
            if revenue_growth is None:
                revenue_growth = 0.05
            revenue_growth = max(0.0, min(0.15, revenue_growth))
            
            # Risk-adjusted discount rate (WACC approximation)
            risk_free_rate = 0.045  # Approximate 10-year treasury
            market_premium = 0.065  # Equity risk premium
            discount_rate = risk_free_rate + (beta or 1.0) * market_premium
            discount_rate = max(0.08, min(0.15, discount_rate))  # Clamp between 8-15%
            
            terminal_growth = 0.025
            
            # Multi-model valuation
            valuations = {}
            
            # 1. DCF Analysis (Enhanced) - Use our updated DCF valuation
            from app.tools.dcf_valuation import perform_dcf_valuation
            import asyncio
            dcf_result = asyncio.run(perform_dcf_valuation(ticker))
            if dcf_result:
                valuations["dcf"] = {
                    "applicable": True,
                    "base_case": {
                        "intrinsic_price": {
                            "base": dcf_result.get("intrinsic_value")
                        }
                    },
                    "methodology": "Enhanced DCF with conservative assumptions for Indian stocks"
                }
            else:
                # Fallback to old DCF if new one fails
                dcf_result = _enhanced_dcf_analysis(
                    fcf0, revenue_growth, discount_rate, terminal_growth,
                    shares_outstanding, market_cap, current_price
                )
                valuations["dcf"] = dcf_result
            
            # 2. Dividend Discount Model (if applicable)
            ddm_result = _dividend_discount_model(
                info, current_price, shares_outstanding, discount_rate
            )
            if ddm_result.get("applicable"):
                valuations["ddm"] = ddm_result
            
            # 3. Comparable Company Analysis
            comps_result = _comparable_company_analysis(ticker, info, current_price)
            valuations["comparables"] = comps_result
            
            # 4. Sum-of-the-Parts (if multi-segment)
            sotp_result = _sum_of_parts_analysis(info, market_cap)
            if sotp_result.get("applicable"):
                valuations["sum_of_parts"] = sotp_result
            
            # 5. Sensitivity Analysis
            sensitivity = _sensitivity_analysis(
                fcf0, revenue_growth, discount_rate, terminal_growth, shares_outstanding
            )
            
            # Consolidate valuations
            consolidated = _consolidate_valuations(valuations, current_price)
            
            return {
                "inputs": {
                    "fcf0": fcf0,
                    "revenue_growth": revenue_growth,
                    "discount_rate": discount_rate,
                    "terminal_growth": terminal_growth,
                    "shares_outstanding": shares_outstanding,
                    "market_cap": market_cap,
                    "current_price": current_price,
                    "dividend_yield": dividend_yield,
                    "beta": beta,
                },
                "models": valuations,
                "sensitivity_analysis": sensitivity,
                "consolidated_valuation": consolidated,
                "valuation_summary": consolidated.get("summary", "Multi-model valuation completed")
            }
            
        except Exception as e:
            return {
                "inputs": {},
                "models": {},
                "sensitivity_analysis": {},
                "consolidated_valuation": {},
                "valuation_summary": f"Valuation analysis failed: {str(e)}"
            }
    
    return await asyncio.to_thread(_enhanced_valuation)


def _enhanced_dcf_analysis(fcf0: Optional[float], growth: float, discount_rate: float, 
                          terminal_growth: float, shares: Optional[float], 
                          market_cap: Optional[float], current_price: Optional[float]) -> Dict[str, Any]:
    """Enhanced DCF with multiple scenarios"""
    if not fcf0 or fcf0 <= 0:
        return {"applicable": False, "reason": "Insufficient FCF data"}
    
    # Base case DCF
    base_dcf = _dcf_price_band(fcf0, shares, market_cap, growth, discount_rate, terminal_growth)
    
    # Additional scenarios
    scenarios = {
        "conservative": _dcf_price_band(fcf0, shares, market_cap, max(0.02, growth-0.03), 
                                       discount_rate+0.01, max(0.02, terminal_growth-0.005)),
        "optimistic": _dcf_price_band(fcf0, shares, market_cap, min(0.12, growth+0.03), 
                                     max(0.08, discount_rate-0.01), min(0.04, terminal_growth+0.005)),
        "recession": _dcf_price_band(fcf0, shares, market_cap, max(0.0, growth-0.05), 
                                    discount_rate+0.02, max(0.015, terminal_growth-0.01))
    }
    
    return {
        "applicable": True,
        "base_case": base_dcf,
        "scenarios": scenarios,
        "methodology": "5-year DCF with terminal value"
    }


def _dividend_discount_model(info: Dict[str, Any], current_price: Optional[float], 
                           shares: Optional[float], discount_rate: float) -> Dict[str, Any]:
    """Dividend Discount Model for dividend-paying stocks"""
    dividend_yield = _safe_float(info.get("dividendYield"))
    dividend_rate = _safe_float(info.get("dividendRate"))
    
    if not dividend_yield or dividend_yield < 0.01:  # Less than 1% yield
        return {"applicable": False, "reason": "No meaningful dividend yield"}
    
    # Estimate dividend growth from earnings growth
    earnings_growth = _safe_float(info.get("earningsGrowth")) or 0.05
    dividend_growth = min(earnings_growth * 0.8, 0.08)  # Conservative estimate
    
    if dividend_growth >= discount_rate:
        dividend_growth = discount_rate * 0.8  # Ensure growth < discount rate
    
    if dividend_rate and dividend_growth < discount_rate:
        # Gordon Growth Model
        next_dividend = dividend_rate * (1 + dividend_growth)
        ddm_value = next_dividend / (discount_rate - dividend_growth)
        
        if shares:
            ddm_price = ddm_value
        else:
            ddm_price = None
        
        return {
            "applicable": True,
            "current_dividend": dividend_rate,
            "estimated_growth": dividend_growth,
            "ddm_value_per_share": ddm_price,
            "yield_on_cost": dividend_yield,
            "methodology": "Gordon Growth Model"
        }
    
    return {"applicable": False, "reason": "Insufficient dividend data"}


def _comparable_company_analysis(ticker: str, info: Dict[str, Any], 
                                current_price: Optional[float]) -> Dict[str, Any]:
    """Comparable company multiples analysis"""
    
    # Extract key multiples
    pe_ratio = _safe_float(info.get("trailingPE"))
    pb_ratio = _safe_float(info.get("priceToBook"))
    ev_ebitda = _safe_float(info.get("enterpriseToEbitda"))
    ev_revenue = _safe_float(info.get("enterpriseToRevenue"))
    peg_ratio = _safe_float(info.get("pegRatio"))
    
    # Industry average multiples (simplified - in production would fetch real peer data)
    sector = info.get("sector", "")
    industry_multiples = _get_industry_multiples(sector)
    
    comps_analysis = {}
    
    if pe_ratio and current_price:
        earnings_per_share = current_price / pe_ratio
        implied_price_pe = earnings_per_share * industry_multiples.get("pe", pe_ratio)
        comps_analysis["pe_based"] = {
            "current_multiple": pe_ratio,
            "industry_average": industry_multiples.get("pe"),
            "implied_price": implied_price_pe
        }
    
    if pb_ratio and current_price:
        book_value_per_share = current_price / pb_ratio
        implied_price_pb = book_value_per_share * industry_multiples.get("pb", pb_ratio)
        comps_analysis["pb_based"] = {
            "current_multiple": pb_ratio,
            "industry_average": industry_multiples.get("pb"),
            "implied_price": implied_price_pb
        }
    
    if ev_ebitda:
        comps_analysis["ev_ebitda"] = {
            "current_multiple": ev_ebitda,
            "industry_average": industry_multiples.get("ev_ebitda"),
        }
    
    return {
        "applicable": bool(comps_analysis),
        "multiples_analysis": comps_analysis,
        "methodology": "Industry peer comparison"
    }


def _sum_of_parts_analysis(info: Dict[str, Any], market_cap: Optional[float]) -> Dict[str, Any]:
    """Sum-of-the-Parts analysis for diversified companies"""
    # This is a simplified implementation
    # In practice, would require detailed segment financial data
    
    business_summary = info.get("businessSummary", "")
    if not business_summary or len(business_summary) < 200:
        return {"applicable": False, "reason": "Insufficient business segment data"}
    
    # Very basic heuristic - look for multiple business mentions
    business_indicators = ["segment", "division", "subsidiary", "unit", "business", "operation"]
    segment_count = sum(1 for indicator in business_indicators if indicator in business_summary.lower())
    
    if segment_count < 3:
        return {"applicable": False, "reason": "Appears to be single-business company"}
    
    return {
        "applicable": True,
        "note": "Multi-segment company identified",
        "recommendation": "Detailed segment analysis recommended",
        "methodology": "Sum-of-the-Parts approach suggested"
    }


def _sensitivity_analysis(fcf0: Optional[float], growth: float, discount_rate: float, 
                         terminal_growth: float, shares: Optional[float]) -> Dict[str, Any]:
    """Perform sensitivity analysis on key variables"""
    if not fcf0 or fcf0 <= 0 or not shares:
        return {"applicable": False, "reason": "Insufficient data for sensitivity analysis"}
    
    # Sensitivity ranges
    growth_range = [growth - 0.02, growth, growth + 0.02]
    discount_range = [discount_rate - 0.01, discount_rate, discount_rate + 0.01]
    terminal_range = [max(0.015, terminal_growth - 0.005), terminal_growth, terminal_growth + 0.005]
    
    sensitivity_matrix = {}
    
    # Growth vs Discount Rate sensitivity
    growth_discount_matrix = []
    for g in growth_range:
        row = []
        for d in discount_range:
            if g < d:  # Ensure growth < discount rate
                dcf_result = _dcf_price_band(fcf0, shares, None, g, d, terminal_growth)
                price = dcf_result.get("intrinsic_price", {}).get("base")
                row.append(price)
            else:
                row.append(None)
        growth_discount_matrix.append(row)
    
    sensitivity_matrix["growth_vs_discount"] = {
        "growth_rates": growth_range,
        "discount_rates": discount_range,
        "price_matrix": growth_discount_matrix
    }
    
    # Terminal growth sensitivity
    terminal_sensitivity = []
    for tg in terminal_range:
        if growth > tg and discount_rate > tg:
            dcf_result = _dcf_price_band(fcf0, shares, None, growth, discount_rate, tg)
            price = dcf_result.get("intrinsic_price", {}).get("base")
            terminal_sensitivity.append(price)
        else:
            terminal_sensitivity.append(None)
    
    sensitivity_matrix["terminal_growth"] = {
        "terminal_rates": terminal_range,
        "prices": terminal_sensitivity
    }
    
    return {
        "applicable": True,
        "sensitivity_matrix": sensitivity_matrix,
        "methodology": "Monte Carlo-style sensitivity analysis"
    }


def _consolidate_valuations(valuations: Dict[str, Any], current_price: Optional[float]) -> Dict[str, Any]:
    """Consolidate multiple valuation models into summary"""
    
    valid_prices = []
    model_weights = {}
    
    # Extract prices from different models
    if valuations.get("dcf", {}).get("applicable"):
        dcf_price = valuations["dcf"].get("base_case", {}).get("intrinsic_price", {}).get("base")
        if dcf_price:
            valid_prices.append(dcf_price)
            model_weights["dcf"] = 0.4  # Higher weight for DCF
    
    if valuations.get("ddm", {}).get("applicable"):
        ddm_price = valuations["ddm"].get("ddm_value_per_share")
        if ddm_price:
            valid_prices.append(ddm_price)
            model_weights["ddm"] = 0.3
    
    if valuations.get("comparables", {}).get("applicable"):
        comps = valuations["comparables"].get("multiples_analysis", {})
        pe_price = comps.get("pe_based", {}).get("implied_price")
        pb_price = comps.get("pb_based", {}).get("implied_price")
        
        comp_prices = [p for p in [pe_price, pb_price] if p]
        if comp_prices:
            avg_comp_price = sum(comp_prices) / len(comp_prices)
            valid_prices.append(avg_comp_price)
            model_weights["comparables"] = 0.3
    
    if not valid_prices:
        return {
            "target_price": None,
            "valuation_range": {},
            "confidence": "Low",
            "summary": "Insufficient data for consolidated valuation"
        }
    
    # Calculate weighted average
    if len(valid_prices) == 1:
        target_price = valid_prices[0]
    else:
        total_weight = sum(model_weights.values())
        if total_weight > 0:
            # Normalize weights
            normalized_weights = {k: v/total_weight for k, v in model_weights.items()}
            target_price = sum(price * weight for price, weight in zip(valid_prices, normalized_weights.values()))
        else:
            target_price = sum(valid_prices) / len(valid_prices)
    
    # Calculate valuation range
    price_min = min(valid_prices)
    price_max = max(valid_prices)
    
    # Determine confidence based on model agreement
    if len(valid_prices) >= 2:
        price_std = (max(valid_prices) - min(valid_prices)) / target_price if target_price else 0
        if price_std < 0.15:  # Less than 15% difference
            confidence = "High"
        elif price_std < 0.30:
            confidence = "Medium"
        else:
            confidence = "Low"
    else:
        confidence = "Medium"
    
    # Calculate upside/downside
    upside_downside = None
    if current_price and target_price:
        upside_downside = ((target_price - current_price) / current_price) * 100
    
    return {
        "target_price": target_price,
        "valuation_range": {"low": price_min, "high": price_max},
        "upside_downside_pct": upside_downside,
        "models_used": list(model_weights.keys()),
        "confidence": confidence,
        "summary": f"Consolidated target: ${target_price:.2f} ({upside_downside:+.1f}% vs current)" if target_price and upside_downside else "Valuation analysis completed"
    }


def _get_industry_multiples(sector: str) -> Dict[str, float]:
    """Get approximate industry average multiples by sector"""
    # Simplified industry multiples - in production would fetch from financial data providers
    industry_averages = {
        "Technology": {"pe": 22.0, "pb": 4.5, "ev_ebitda": 15.0},
        "Healthcare": {"pe": 18.0, "pb": 3.2, "ev_ebitda": 12.0},
        "Financial Services": {"pe": 12.0, "pb": 1.2, "ev_ebitda": 8.0},
        "Consumer Cyclical": {"pe": 16.0, "pb": 2.8, "ev_ebitda": 10.0},
        "Consumer Defensive": {"pe": 15.0, "pb": 2.5, "ev_ebitda": 9.0},
        "Energy": {"pe": 12.0, "pb": 1.8, "ev_ebitda": 6.0},
        "Utilities": {"pe": 14.0, "pb": 1.5, "ev_ebitda": 8.0},
        "Real Estate": {"pe": 16.0, "pb": 1.4, "ev_ebitda": 12.0},
        "Basic Materials": {"pe": 13.0, "pb": 1.9, "ev_ebitda": 7.0},
        "Communication Services": {"pe": 20.0, "pb": 3.0, "ev_ebitda": 11.0},
    }
    
    return industry_averages.get(sector, {"pe": 16.0, "pb": 2.5, "ev_ebitda": 10.0})  # Market average fallback
