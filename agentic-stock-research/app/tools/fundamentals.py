from __future__ import annotations

from typing import Any, Dict, Optional
import asyncio
import logging

import yfinance as yf
import pandas as pd

from app.tools.finance import fetch_info
from app.utils.validation import DataValidator

logger = logging.getLogger(__name__)


async def compute_fundamentals(ticker: str) -> Dict[str, Any]:
    info = await fetch_info(ticker)

    def _sf(v: Any) -> Optional[float]:
        try:
            if v is None:
                return None
            f = float(v)
            if f != f:
                return None
            return f
        except Exception:
            return None

    # Basic ratios with validation
    pe = DataValidator.validate_ratio(info.get("trailingPE") or info.get("forwardPE"), "P/E", 0, 1000)
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
    operating_cf = DataValidator.validate_financial_value(
        info.get("operatingCashflow") or info.get("operatingCashFlow"), 
        "Operating Cash Flow", allow_negative=True
    )
    capex = DataValidator.validate_financial_value(
        info.get("capitalExpenditures") or info.get("capitalExpenditure"), 
        "CapEx", allow_negative=True
    )
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

    # Backfill missing metrics using financial statements
    def _compute_from_statements() -> Dict[str, Optional[float]]:
        out: Dict[str, Optional[float]] = {}
        try:
            t = yf.Ticker(ticker)
            is_df: pd.DataFrame = getattr(t, "financials", None)
            bs_df: pd.DataFrame = getattr(t, "balance_sheet", None)
            cf_df: pd.DataFrame = getattr(t, "cashflow", None)

            def last_val(df: Optional[pd.DataFrame], keys: list[str]) -> Optional[float]:
                if df is None or getattr(df, "empty", True):
                    return None
                for k in keys:
                    if k in df.index:
                        ser = df.loc[k].dropna()
                        if len(ser) > 0:
                            try:
                                return float(ser.iloc[-1])
                            except Exception:
                                continue
                return None

            def last_two_vals(df: Optional[pd.DataFrame], keys: list[str]) -> list[float]:
                vals: list[float] = []
                if df is None or getattr(df, "empty", True):
                    return vals
                for k in keys:
                    if k in df.index:
                        ser = df.loc[k].dropna()
                        try:
                            vals = [float(v) for v in ser.iloc[-2:].tolist() if v is not None]
                            if vals:
                                return vals
                        except Exception:
                            continue
                return vals

            # ROE = Net Income / Avg Equity
            net_income = last_val(is_df, ["Net Income", "NetIncome"])
            equity_vals = last_two_vals(bs_df, ["Total Stockholder Equity", "Total Equity Gross Minority Interest", "Total Equity"])
            roe_fb: Optional[float] = None
            if net_income is not None and equity_vals:
                avg_equity = sum(equity_vals) / len(equity_vals)
                if avg_equity:
                    roe_fb = net_income / avg_equity
            out["roe"] = roe_fb

            # EBITDA margin = EBITDA / Revenue
            ebitda_fb = last_val(is_df, ["Ebitda", "EBITDA"])
            revenue_fb = last_val(is_df, ["Total Revenue", "Revenue", "TotalRevenue"])
            out["ebitda_margin"] = (ebitda_fb / revenue_fb) if ebitda_fb and revenue_fb else None

            # Interest coverage = EBIT or Operating Income / Interest Expense
            ebit_fb = last_val(is_df, ["Ebit", "EBIT", "Operating Income"]) or None
            interest_fb = last_val(is_df, ["Interest Expense", "InterestExpense"]) or None
            out["interest_coverage"] = (ebit_fb / abs(interest_fb)) if ebit_fb and interest_fb else None

            # ROIC ≈ NOPAT / Invested Capital
            operating_income = last_val(is_df, ["Operating Income"]) or ebit_fb
            income_tax = last_val(is_df, ["Income Tax Expense", "Tax Provision"])
            pretax_income = last_val(is_df, ["Income Before Tax", "Pretax Income"])
            tax_rate = None
            try:
                if income_tax and pretax_income and pretax_income != 0:
                    tax_rate = max(0.0, min(0.35, income_tax / pretax_income))
            except Exception:
                tax_rate = None
            nopat = None
            if operating_income is not None:
                nopat = operating_income * (1.0 - (tax_rate if tax_rate is not None else 0.21))

            total_debt_fb = last_val(bs_df, ["Total Debt", "Short Long Term Debt", "Long Term Debt"]) or None
            equity_last = equity_vals[-1] if equity_vals else None
            cash_fb = last_val(bs_df, ["Cash And Cash Equivalents", "Cash", "Cash And Cash Equivalents At Carrying Value"]) or None
            invested_capital = None
            if (total_debt_fb is not None) or (equity_last is not None):
                invested_capital = (total_debt_fb or 0.0) + (equity_last or 0.0) - (cash_fb or 0.0)
            out["roic"] = (nopat / invested_capital) if (nopat is not None and invested_capital and invested_capital != 0) else None

            # FCF yield fallback = (OCF + CapEx) / MarketCap
            ocf_fb = last_val(cf_df, [
                "Total Cash From Operating Activities",
                "Cash Flow From Continuing Operating Activities",
                "Operating Cash Flow",
                "Net Cash From Operating Activities",
            ])
            capex_fb = last_val(cf_df, [
                "Capital Expenditures",
                "Capital Expenditure",
                "Capex",
                "Purchase Of Property Plant Equipment",
            ])
            mc = market_cap
            out["fcf_yield"] = ((ocf_fb + capex_fb) / mc) if isinstance(ocf_fb, (int, float)) and isinstance(capex_fb, (int, float)) and isinstance(mc, (int, float)) and mc else None

            return out
        except Exception:
            return {}

    backfill: Dict[str, Optional[float]] = {}
    if any(v is None for v in [roe, ebitda_margin, interest_coverage, roic, fcf_yield]):
        backfill = await asyncio.to_thread(_compute_from_statements)
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
        "pe": _sf(pe),
        "pb": _sf(pb),
        "roe": _sf(roe),
        "revenueGrowth": _sf(revenue_growth),
        "grossMargins": _sf(gross_margins),
        "operatingMargins": _sf(operating_margins),
        "dividendYield": _sf(dividend_yield),
        # Extended
        "debtToEquity": _sf(debt_to_equity),
        "interestCoverage": _sf(interest_coverage),
        "fcfYield": _sf(fcf_yield),
        "roic": _sf(roic),
        "ebitdaMargin": _sf(ebitda_margin),
        "peg": _sf(peg),
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
        },
    }
