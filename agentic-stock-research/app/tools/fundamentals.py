from __future__ import annotations

from typing import Any, Dict, Optional
import asyncio
import logging

import yfinance as yf
import pandas as pd

from app.tools.finance import fetch_info
from app.utils.validation import DataValidator

logger = logging.getLogger(__name__)


# ========== HELPER FUNCTIONS ==========

def _safe_float(v: Any) -> Optional[float]:
    """
    Safely convert a value to float, handling None, NaN, and exceptions
    
    Args:
        v: Value to convert (can be None, string, number, etc.)
    
    Returns:
        Float value or None if conversion fails or value is invalid
    """
    try:
        if v is None:
            return None
        f = float(v)
        if f != f:  # Check for NaN
            return None
        return f
    except Exception:
        return None


def _get_last_value(df: Optional[pd.DataFrame], keys: list[str]) -> Optional[float]:
    """Extract the most recent value from a DataFrame for given keys"""
    if df is None or getattr(df, "empty", True):
        return None
    for key in keys:
        if key in df.index:
            series = df.loc[key].dropna()
            if len(series) > 0:
                try:
                    return float(series.iloc[-1])
                except Exception:
                    continue
    return None


def _get_last_two_values(df: Optional[pd.DataFrame], keys: list[str]) -> list[float]:
    """Extract the last two values from a DataFrame for given keys"""
    vals: list[float] = []
    if df is None or getattr(df, "empty", True):
        return vals
    for key in keys:
        if key in df.index:
            series = df.loc[key].dropna()
            try:
                vals = [float(v) for v in series.iloc[-2:].tolist() if v is not None]
                if vals:
                    return vals
            except Exception:
                continue
    return vals


def _compute_from_statements(ticker: str, market_cap: Optional[float]) -> Dict[str, Optional[float]]:
    """
    Backfill missing fundamental metrics from financial statements
    
    Calculates:
    - ROE (from net income and equity)
    - EBITDA margin
    - Interest coverage
    - ROIC (Return on Invested Capital)
    - FCF yield
    """
    out: Dict[str, Optional[float]] = {}
    try:
        t = yf.Ticker(ticker)
        is_df: pd.DataFrame = getattr(t, "financials", None)
        bs_df: pd.DataFrame = getattr(t, "balance_sheet", None)
        cf_df: pd.DataFrame = getattr(t, "cashflow", None)

        # ROE = Net Income / Avg Equity
        net_income = _get_last_value(is_df, ["Net Income", "NetIncome"])
        equity_vals = _get_last_two_values(bs_df, ["Total Stockholder Equity", "Total Equity Gross Minority Interest", "Total Equity"])
        roe_fb: Optional[float] = None
        if net_income is not None and equity_vals:
            avg_equity = sum(equity_vals) / len(equity_vals)
            if avg_equity:
                roe_fb = net_income / avg_equity
        out["roe"] = roe_fb

        # EBITDA margin = EBITDA / Revenue
        ebitda_fb = _get_last_value(is_df, ["Ebitda", "EBITDA"])
        revenue_fb = _get_last_value(is_df, ["Total Revenue", "Revenue", "TotalRevenue"])
        out["ebitda_margin"] = (ebitda_fb / revenue_fb) if ebitda_fb and revenue_fb else None

        # Interest coverage = EBIT or Operating Income / Interest Expense
        ebit_fb = _get_last_value(is_df, ["Ebit", "EBIT", "Operating Income"]) or None
        interest_fb = _get_last_value(is_df, ["Interest Expense", "InterestExpense"]) or None
        out["interest_coverage"] = (ebit_fb / abs(interest_fb)) if ebit_fb and interest_fb else None

        # ROIC ≈ NOPAT / Invested Capital
        operating_income = _get_last_value(is_df, ["Operating Income"]) or ebit_fb
        income_tax = _get_last_value(is_df, ["Income Tax Expense", "Tax Provision"])
        pretax_income = _get_last_value(is_df, ["Income Before Tax", "Pretax Income"])
        tax_rate = None
        try:
            if income_tax and pretax_income and pretax_income != 0:
                tax_rate = max(0.0, min(0.35, income_tax / pretax_income))
        except Exception:
            tax_rate = None
        nopat = None
        if operating_income is not None:
            nopat = operating_income * (1.0 - (tax_rate if tax_rate is not None else 0.21))

        total_debt_fb = _get_last_value(bs_df, ["Total Debt", "Short Long Term Debt", "Long Term Debt"]) or None
        equity_last = equity_vals[-1] if equity_vals else None
        cash_fb = _get_last_value(bs_df, ["Cash And Cash Equivalents", "Cash", "Cash And Cash Equivalents At Carrying Value"]) or None
        invested_capital = None
        if (total_debt_fb is not None) or (equity_last is not None):
            invested_capital = (total_debt_fb or 0.0) + (equity_last or 0.0) - (cash_fb or 0.0)
        out["roic"] = (nopat / invested_capital) if (nopat is not None and invested_capital and invested_capital != 0) else None

        # FCF yield fallback = (OCF + CapEx) / MarketCap
        ocf_fb = _get_last_value(cf_df, [
            "Total Cash From Operating Activities",
            "Cash Flow From Continuing Operating Activities",
            "Operating Cash Flow",
            "Net Cash From Operating Activities",
        ])
        capex_fb = _get_last_value(cf_df, [
            "Capital Expenditures",
            "Capital Expenditure",
            "Capex",
            "Purchase Of Property Plant Equipment",
        ])
        out["fcf_yield"] = ((ocf_fb + capex_fb) / market_cap) if isinstance(ocf_fb, (int, float)) and isinstance(capex_fb, (int, float)) and isinstance(market_cap, (int, float)) and market_cap else None

        return out
    except Exception:
        return {}


# ========== MAIN FUNCTION ==========

async def compute_fundamentals(ticker: str) -> Dict[str, Any]:
    """
    Compute comprehensive fundamental metrics for a stock
    
    Returns a dictionary with:
    - Valuation ratios (P/E, P/B, P/S, EV/EBITDA, etc.)
    - Profitability metrics (ROE, ROIC, margins)
    - Liquidity ratios (current ratio, quick ratio)
    - Cash flow metrics (FCF yield, cash conversion rate)
    - Dividend metrics (yield, payout ratio)
    - Operational efficiency (capex intensity)
    """
    info = await fetch_info(ticker)

    # Basic ratios with validation - SEPARATE trailing and forward P/E
    trailing_pe = DataValidator.validate_ratio(info.get("trailingPE"), "Trailing P/E", 0, 1000)
    forward_pe = DataValidator.validate_ratio(info.get("forwardPE"), "Forward P/E", 0, 1000)
    
    # Fallback PE for legacy compatibility (prefer trailing, then forward)
    pe = trailing_pe or forward_pe
    
    # Calculate PE growth expectation (positive = growth expected)
    pe_ratio_change = None
    if trailing_pe and forward_pe and forward_pe > 0:
        # Positive = earnings expected to grow (forward PE lower than trailing)
        # Negative = earnings expected to decline (forward PE higher than trailing)
        pe_ratio_change = ((trailing_pe - forward_pe) / forward_pe) * 100
    
    pb = DataValidator.validate_ratio(info.get("priceToBook"), "P/B", 0, 100)
    roe_raw = info.get("returnOnEquity")  # fraction 0..1
    roe = DataValidator.validate_percentage(roe_raw, "ROE") if roe_raw else None
    revenue_growth_raw = info.get("revenueGrowth")  # fraction 0..1
    revenue_growth = DataValidator.validate_percentage(revenue_growth_raw, "Revenue Growth") if revenue_growth_raw else None
    gross_margins = DataValidator.validate_percentage(info.get("grossMargins"), "Gross Margins")
    operating_margins = DataValidator.validate_percentage(info.get("operatingMargins"), "Operating Margins")
    dividend_yield = DataValidator.validate_percentage(info.get("dividendYield"), "Dividend Yield")

    # Leverage & coverage with validation
    total_debt = DataValidator.validate_financial_value(info.get("totalDebt"), "Total Debt", allow_negative=False)
    total_cash = DataValidator.validate_financial_value(info.get("totalCash"), "Total Cash", allow_negative=False)
    ebit = DataValidator.validate_financial_value(info.get("ebitda"), "EBITDA", allow_negative=True)  # EBITDA proxy
    interest_expense = DataValidator.validate_financial_value(info.get("interestExpense"), "Interest Expense", allow_negative=False)
    debt_to_equity = DataValidator.validate_ratio(info.get("debtToEquity"), "Debt/Equity", 0, 100)

    # FCF Yield with validation
    free_cf = DataValidator.validate_financial_value(info.get("freeCashflow"), "Free Cash Flow", allow_negative=True)
    operating_cf = DataValidator.validate_financial_value(info.get("operatingCashflow"), "Operating Cash Flow", allow_negative=True)
    capex = DataValidator.validate_financial_value(info.get("capitalExpenditures"), "CapEx", allow_negative=True)
    market_cap = DataValidator.validate_financial_value(info.get("marketCap"), "Market Cap", allow_negative=False)
    fcf_calc = None
    if isinstance(free_cf, (int, float)):
        fcf_calc = free_cf
    elif isinstance(operating_cf, (int, float)) and isinstance(capex, (int, float)):
        fcf_calc = operating_cf + capex  # capex is usually negative
    fcf_yield = None
    if isinstance(fcf_calc, (int, float)) and isinstance(market_cap, (int, float)) and market_cap:
        fcf_yield = fcf_calc / market_cap

    # ROIC approximation: use returnOnAssets/returnOnEquity if available
    roic = info.get("returnOnCapital") or info.get("returnOnAssets")

    # EBITDA margin (approx)
    ebitda = info.get("ebitda")
    revenue = info.get("totalRevenue")
    ebitda_margin = None
    if isinstance(ebitda, (int, float)) and isinstance(revenue, (int, float)) and revenue:
        ebitda_margin = ebitda / revenue

    # Interest coverage (EBITDA / interest)
    interest_coverage = None
    if isinstance(ebit, (int, float)) and isinstance(interest_expense, (int, float)) and interest_expense:
        try:
            interest_coverage = ebit / abs(interest_expense)
        except Exception:
            interest_coverage = None

    # PEG ratio (prefer provided; fallback PE / growth)
    peg = info.get("pegRatio")
    if peg is None and pe and revenue_growth and revenue_growth > 0:
        try:
            peg = float(pe) / (float(revenue_growth) * 100.0)  # growth% assumption
        except Exception:
            peg = None

    # ========== CRITICAL METRICS (Phase 1) ==========
    
    # Net Profit Margin
    net_income = DataValidator.validate_financial_value(info.get("netIncome"), "Net Income", allow_negative=True)
    net_profit_margin = None
    if isinstance(net_income, (int, float)) and isinstance(revenue, (int, float)) and revenue:
        net_profit_margin = net_income / revenue
    
    # Cash Conversion Rate (OCF / Net Income) - Key earnings quality metric
    cash_conversion_rate = None
    if isinstance(operating_cf, (int, float)) and isinstance(net_income, (int, float)) and net_income and net_income > 0:
        cash_conversion_rate = operating_cf / net_income
    
    # Liquidity Ratios
    current_assets = DataValidator.validate_financial_value(info.get("currentAssets"), "Current Assets", allow_negative=False)
    current_liabilities = DataValidator.validate_financial_value(info.get("currentLiabilities"), "Current Liabilities", allow_negative=False)
    inventory = DataValidator.validate_financial_value(info.get("inventory"), "Inventory", allow_negative=False)
    
    current_ratio = None
    if isinstance(current_assets, (int, float)) and isinstance(current_liabilities, (int, float)) and current_liabilities:
        current_ratio = current_assets / current_liabilities
    
    quick_ratio = None
    if isinstance(current_assets, (int, float)) and isinstance(current_liabilities, (int, float)) and current_liabilities:
        quick_assets = current_assets - (inventory if isinstance(inventory, (int, float)) else 0)
        quick_ratio = quick_assets / current_liabilities
    
    # Additional Valuation Ratios
    price_to_sales = None
    if isinstance(market_cap, (int, float)) and isinstance(revenue, (int, float)) and revenue:
        price_to_sales = market_cap / revenue
    
    price_to_fcf = None
    if isinstance(market_cap, (int, float)) and isinstance(free_cf, (int, float)) and free_cf and free_cf > 0:
        price_to_fcf = market_cap / free_cf
    
    ev_to_ebitda = None
    enterprise_value = None
    if isinstance(market_cap, (int, float)):
        net_debt_calc = (total_debt if isinstance(total_debt, (int, float)) else 0) - (total_cash if isinstance(total_cash, (int, float)) else 0)
        enterprise_value = market_cap + net_debt_calc
        if isinstance(ebitda, (int, float)) and ebitda and ebitda > 0:
            ev_to_ebitda = enterprise_value / ebitda
    
    # Dividend Analysis
    dividend_per_share = _safe_float(info.get("dividendRate") or info.get("trailingAnnualDividendRate"))
    total_dividends = None
    shares_outstanding = DataValidator.validate_financial_value(info.get("sharesOutstanding"), "Shares Outstanding", allow_negative=False)
    if isinstance(dividend_per_share, (int, float)) and isinstance(shares_outstanding, (int, float)):
        total_dividends = dividend_per_share * shares_outstanding
    
    dividend_payout_ratio = None
    if isinstance(total_dividends, (int, float)) and isinstance(net_income, (int, float)) and net_income and net_income > 0:
        dividend_payout_ratio = total_dividends / net_income
    
    # Capex Intensity (for working capital analysis later)
    capex_intensity = None
    if isinstance(capex, (int, float)) and isinstance(revenue, (int, float)) and revenue:
        capex_intensity = abs(capex) / revenue  # capex is usually negative
    
    # FCF Margin
    fcf_margin = None
    if isinstance(free_cf, (int, float)) and isinstance(revenue, (int, float)) and revenue:
        fcf_margin = free_cf / revenue

    # Backfill missing metrics using financial statements
    backfill: Dict[str, Optional[float]] = {}
    if any(v is None for v in [roe, ebitda_margin, interest_coverage, roic, fcf_yield]):
        backfill = await asyncio.to_thread(_compute_from_statements, ticker, market_cap)
        if roe is None:
            roe = backfill.get("roe", roe)
        if ebitda_margin is None:
            ebitda_margin = backfill.get("ebitda_margin", ebitda_margin)
        if interest_coverage is None:
            interest_coverage = backfill.get("interest_coverage", interest_coverage)
        if roic is None:
            roic = backfill.get("roic", roic)
        if fcf_yield is None:
            fcf_yield = backfill.get("fcf_yield", fcf_yield)

    return {
        # Legacy PE (for backward compatibility)
        "pe": _safe_float(pe),
        
        # NEW: Separate trailing and forward P/E ratios
        "trailingPE": _safe_float(trailing_pe),
        "forwardPE": _safe_float(forward_pe),
        "peGrowthExpectation": _safe_float(pe_ratio_change),  # % change (positive = growth expected)
        
        # Profitability metrics
        "pb": _safe_float(pb),
        "roe": _safe_float(roe),
        "revenueGrowth": _safe_float(revenue_growth),
        "grossMargins": _safe_float(gross_margins),
        "operatingMargins": _safe_float(operating_margins),
        "netProfitMargin": _safe_float(net_profit_margin),  # NEW
        "dividendYield": _safe_float(dividend_yield),
        
        # Extended metrics
        "debtToEquity": _safe_float(debt_to_equity),
        "interestCoverage": _safe_float(interest_coverage),
        "fcfYield": _safe_float(fcf_yield),
        "fcfMargin": _safe_float(fcf_margin),  # NEW
        "roic": _safe_float(roic),
        "ebitdaMargin": _safe_float(ebitda_margin),
        "peg": _safe_float(peg),
        
        # NEW: Earnings Quality & Cash Flow
        "cashConversionRate": _safe_float(cash_conversion_rate),  # OCF/Net Income - CRITICAL
        
        # NEW: Liquidity Ratios
        "currentRatio": _safe_float(current_ratio),
        "quickRatio": _safe_float(quick_ratio),
        
        # NEW: Additional Valuation Metrics
        "priceToSales": _safe_float(price_to_sales),
        "priceToFCF": _safe_float(price_to_fcf),
        "evToEbitda": _safe_float(ev_to_ebitda),
        "enterpriseValue": _safe_float(enterprise_value),
        
        # NEW: Dividend Analysis
        "dividendPayoutRatio": _safe_float(dividend_payout_ratio),
        
        # NEW: Operational Efficiency
        "capexIntensity": _safe_float(capex_intensity),  # Capex / Revenue
        
        # Raw totals (may be useful downstream)
        "totals": {
            "totalDebt": total_debt,
            "totalCash": total_cash,
            "ebitda": ebitda,
            "freeCashflow": free_cf,
            "operatingCashflow": operating_cf,
            "capitalExpenditures": capex,
            "marketCap": market_cap,
            "revenue": revenue,
            "netIncome": net_income,
            "currentAssets": current_assets,
            "currentLiabilities": current_liabilities,
            "inventory": inventory,
        },
    }
