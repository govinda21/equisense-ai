"""
Fundamental metrics computation for a stock ticker.
Fetches valuation, profitability, liquidity, and cash flow metrics from yfinance,
with automatic fallback to financial statements for missing values.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import pandas as pd
import yfinance as yf

from app.tools.finance import fetch_info
from app.utils.validation import DataValidator

logger = logging.getLogger(__name__)


# ---------- helpers ----------

def _safe(v: Any) -> Optional[float]:
    """Convert to float, return None on failure or NaN."""
    try:
        f = float(v)
        return None if f != f else f
    except Exception:
        return None


def _df_last(df: Optional[pd.DataFrame], keys: List[str]) -> Optional[float]:
    """Return the most recent non-null value for any of the given row keys."""
    if df is None or df.empty:
        return None
    for k in keys:
        if k in df.index:
            s = df.loc[k].dropna()
            if len(s):
                return _safe(s.iloc[-1])
    return None


def _df_last2(df: Optional[pd.DataFrame], keys: List[str]) -> List[float]:
    """Return up to the last two non-null values for the first matching key."""
    if df is None or df.empty:
        return []
    for k in keys:
        if k in df.index:
            vals = [_safe(v) for v in df.loc[k].dropna().iloc[-2:] if _safe(v) is not None]
            if vals:
                return vals
    return []


def _statements_backfill(ticker: str, market_cap: Optional[float]) -> Dict[str, Optional[float]]:
    """
    Compute ROE, EBITDA margin, interest coverage, ROIC, FCF yield, and D/E
    directly from yfinance financial statements when info fields are missing.
    """
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        is_df = getattr(t, "financials", None)
        bs_df = getattr(t, "balance_sheet", None)
        cf_df = getattr(t, "cashflow", None)

        # --- ROE ---
        net_income = _df_last(is_df, ["Net Income", "NetIncome"])
        equity_vals = _df_last2(bs_df, ["Total Stockholder Equity",
                                         "Total Equity Gross Minority Interest", "Total Equity"])
        roe = None
        if net_income and equity_vals:
            avg_eq = sum(equity_vals) / len(equity_vals)
            roe = net_income / avg_eq if avg_eq else None

        # --- EBITDA margin ---
        ebitda = _df_last(is_df, ["Ebitda", "EBITDA"])
        revenue = _df_last(is_df, ["Total Revenue", "Revenue", "TotalRevenue"])
        ebitda_margin = (ebitda / revenue) if ebitda and revenue else None

        # --- Interest coverage (EBIT / |interest expense|) ---
        ebit = _df_last(is_df, ["Ebit", "EBIT", "Operating Income"])
        interest = _df_last(is_df, ["Interest Expense", "InterestExpense"])
        interest_coverage = None
        if ebit and interest and interest != 0:
            interest_coverage = ebit / abs(interest)

        # --- ROIC ---
        op_income = _df_last(is_df, ["Operating Income"]) or ebit
        income_tax = _df_last(is_df, ["Income Tax Expense", "Tax Provision"])
        pretax = _df_last(is_df, ["Income Before Tax", "Pretax Income"])
        tax_rate = min(0.35, max(0.0, income_tax / pretax)) if income_tax and pretax else 0.21
        nopat = op_income * (1 - tax_rate) if op_income else None

        equity_last = equity_vals[-1] if equity_vals else None
        total_debt = _df_last(bs_df, ["Total Debt", "Short Long Term Debt", "Long Term Debt"])
        cash = _df_last(bs_df, ["Cash And Cash Equivalents", "Cash",
                                  "Cash And Cash Equivalents At Carrying Value"])
        inv_cap = (total_debt or 0) + (equity_last or 0) - (cash or 0)
        roic = (nopat / inv_cap) if nopat and inv_cap else None

        # --- FCF yield ---
        ocf = _df_last(cf_df, ["Total Cash From Operating Activities",
                                 "Cash Flow From Continuing Operating Activities",
                                 "Operating Cash Flow", "Net Cash From Operating Activities"])
        capex = _df_last(cf_df, ["Capital Expenditures", "Capital Expenditure",
                                   "Capex", "Purchase Of Property Plant Equipment"])
        mktcap = market_cap or _safe(info.get("marketCap"))
        fcf_yield = ((ocf + capex) / mktcap) if ocf and capex and mktcap else None

        # --- D/E (bank-aware) ---
        debt_to_equity = None
        if equity_last:
            total_liab = _df_last(bs_df, ["Total Liabilities Net Minority Interest",
                                            "Total Liabilities", "TotalLiabilitiesNetMinorityInterest"])
            if total_liab and total_debt and (total_liab / equity_last) > 5:
                debt_to_equity = (total_liab / equity_last) * 100  # bank logic
            elif total_debt:
                debt_to_equity = (total_debt / equity_last) * 100
            elif total_liab:
                debt_to_equity = (total_liab / equity_last) * 100

        return dict(roe=roe, ebitda_margin=ebitda_margin, interest_coverage=interest_coverage,
                    roic=roic, fcf_yield=fcf_yield, debt_to_equity=debt_to_equity)
    except Exception as e:
        logger.error(f"statements backfill failed for {ticker}: {e}")
        return {}


# ---------- main ----------

async def compute_fundamentals(ticker: str) -> Dict[str, Any]:
    """
    Compute comprehensive fundamental metrics for a stock.

    Data priority:
    1. yfinance .info  (instant, good coverage)
    2. Indian market data + Screener.in  (for .NS / .BO tickers)
    3. Raw financial statements backfill  (when fields are None)
    """
    info = await fetch_info(ticker)

    # --- Indian data enrichment ---
    indian = {}
    if ticker.endswith((".NS", ".BO")):
        clean = ticker.split(".")[0]
        for fn_name, module in [("get_indian_market_data", "app.tools.indian_market_data"),
                                 ("get_screener_fundamentals", "app.tools.screener_scraper")]:
            try:
                mod = __import__(module, fromlist=[fn_name])
                data = await getattr(mod, fn_name)(clean if fn_name == "get_indian_market_data" else ticker)
                if data:
                    indian.update(data)
            except Exception as e:
                logger.warning(f"{fn_name} failed for {ticker}: {e}")

    # --- Validated fields from info ---
    vr = DataValidator.validate_ratio
    vp = DataValidator.validate_percentage
    vf = DataValidator.validate_financial_value

    trailing_pe = vr(info.get("trailingPE"), "Trailing P/E", 0, 1000)
    forward_pe  = vr(info.get("forwardPE"), "Forward P/E", 0, 1000)
    pe = trailing_pe or forward_pe
    pe_growth = ((trailing_pe - forward_pe) / forward_pe * 100) if trailing_pe and forward_pe else None

    pb            = vr(info.get("priceToBook"), "P/B", 0, 100)
    roe           = vp(info.get("returnOnEquity"), "ROE") or indian.get("roe") or indian.get("return_on_equity")
    revenue_growth = vp(info.get("revenueGrowth"), "Revenue Growth")
    gross_margins  = vp(info.get("grossMargins"), "Gross Margins")
    op_margins     = vp(info.get("operatingMargins"), "Operating Margins")
    div_yield      = vp(info.get("dividendYield"), "Dividend Yield")
    beta           = vr(info.get("beta"), "Beta", 0, 10)
    current_price  = vf(info.get("currentPrice"), "Current Price", allow_negative=False)
    volume         = vf(info.get("volume"), "Volume", allow_negative=False)
    avg_volume     = vf(info.get("averageVolume"), "Avg Volume", allow_negative=False)
    eps            = vf(info.get("trailingEps"), "EPS", allow_negative=True)
    target_price   = vf(info.get("targetMeanPrice"), "Target Price", allow_negative=False)
    total_debt     = vf(info.get("totalDebt"), "Total Debt", allow_negative=False)
    total_cash     = vf(info.get("totalCash"), "Total Cash", allow_negative=False)
    ebitda         = info.get("ebitda")
    revenue        = info.get("totalRevenue")
    market_cap     = vf(info.get("marketCap"), "Market Cap", allow_negative=False)
    free_cf        = vf(info.get("freeCashflow"), "FCF", allow_negative=True)
    op_cf          = vf(info.get("operatingCashflow"), "OCF", allow_negative=True)
    capex          = vf(info.get("capitalExpenditures"), "CapEx", allow_negative=True)
    net_income     = vf(info.get("netIncome") or info.get("netIncomeToCommon"), "Net Income", allow_negative=True)
    shares         = vf(info.get("sharesOutstanding"), "Shares", allow_negative=False)
    inventory      = vf(info.get("inventory"), "Inventory", allow_negative=False)
    curr_assets    = vf(info.get("currentAssets"), "Current Assets", allow_negative=False)
    curr_liab      = vf(info.get("currentLiabilities"), "Current Liabilities", allow_negative=False)
    debt_to_equity = vr(info.get("debtToEquity"), "D/E", 0, 100)
    interest_exp   = vf(info.get("interestExpense"), "Interest Exp", allow_negative=False)
    peg            = info.get("pegRatio")
    roic           = _safe(info.get("returnOnCapital") or info.get("returnOnAssets"))
    current_ratio  = vr(info.get("currentRatio"), "Current Ratio", 0, 100)
    quick_ratio    = vr(info.get("quickRatio"), "Quick Ratio", 0, 100)

    # --- Derived metrics ---
    ebitda_margin     = (_safe(ebitda) / _safe(revenue)) if ebitda and revenue else None
    interest_coverage = (_safe(ebitda) / abs(interest_exp)) if ebitda and interest_exp else None
    if interest_coverage is None and indian:
        interest_coverage = _safe(indian.get("interest_coverage") or indian.get("interestCoverage"))

    fcf_calc = _safe(free_cf) or ((_safe(op_cf) + _safe(capex)) if op_cf and capex else None)
    fcf_yield = (fcf_calc / _safe(market_cap)) if fcf_calc and market_cap else None

    net_profit_margin = (_safe(net_income) / _safe(revenue)) if net_income and revenue else None
    cash_conversion   = (_safe(op_cf) / _safe(net_income)) if op_cf and net_income and net_income > 0 else None
    fcf_margin        = (fcf_calc / _safe(revenue)) if fcf_calc and revenue else None
    price_to_sales    = (_safe(market_cap) / _safe(revenue)) if market_cap and revenue else None
    price_to_fcf      = (_safe(market_cap) / fcf_calc) if market_cap and fcf_calc and fcf_calc > 0 else None
    net_debt          = (_safe(total_debt) or 0) - (_safe(total_cash) or 0)
    ev                = (_safe(market_cap) + net_debt) if market_cap else None
    ev_to_ebitda      = (ev / _safe(ebitda)) if ev and ebitda and _safe(ebitda) > 0 else None
    div_per_share     = _safe(info.get("dividendRate") or info.get("trailingAnnualDividendRate"))
    total_div         = (div_per_share * _safe(shares)) if div_per_share and shares else None
    div_payout_ratio  = (total_div / _safe(net_income)) if total_div and net_income and net_income > 0 else None
    capex_intensity   = (abs(_safe(capex)) / _safe(revenue)) if capex and revenue else None

    if curr_assets and curr_liab:
        current_ratio = _safe(curr_assets) / _safe(curr_liab)
        quick_ratio   = (_safe(curr_assets) - (_safe(inventory) or 0)) / _safe(curr_liab)

    if not peg and pe and revenue_growth and revenue_growth > 0:
        peg = _safe(pe) / (_safe(revenue_growth) * 100)

    # --- Backfill missing derived metrics from statements ---
    missing = any(v is None for v in [roe, ebitda_margin, interest_coverage, roic, fcf_yield, debt_to_equity])
    if missing:
        bf = await asyncio.to_thread(_statements_backfill, ticker, _safe(market_cap))
        roe               = roe or bf.get("roe")
        ebitda_margin     = ebitda_margin or bf.get("ebitda_margin")
        interest_coverage = interest_coverage or bf.get("interest_coverage")
        roic              = roic or bf.get("roic")
        fcf_yield         = fcf_yield or bf.get("fcf_yield")
        debt_to_equity    = debt_to_equity or bf.get("debt_to_equity")

    # --- Trailing P/E growth expectation ---
    pe_growth = ((trailing_pe - forward_pe) / forward_pe * 100) if trailing_pe and forward_pe else None

    return {
        # Identification
        "ticker": ticker, "sector": info.get("sector", ""), "industry": info.get("industry", ""),

        # Raw financials (needed by DCF)
        "revenue": _safe(revenue), "net_income": _safe(net_income),
        "free_cash_flow": fcf_calc, "operating_cash_flow": _safe(op_cf),

        # Valuation
        "pe": _safe(pe), "pe_ratio": _safe(pe),
        "trailingPE": _safe(trailing_pe), "forwardPE": _safe(forward_pe),
        "peGrowthExpectation": _safe(pe_growth),
        "pb": _safe(pb), "pb_ratio": _safe(pb),
        "peg": _safe(peg), "priceToSales": _safe(price_to_sales),
        "priceToFCF": _safe(price_to_fcf), "evToEbitda": _safe(ev_to_ebitda),
        "enterpriseValue": _safe(ev),

        # Profitability
        "roe": _safe(roe), "roic": _safe(roic),
        "grossMargins": _safe(gross_margins), "operatingMargins": _safe(op_margins),
        "netProfitMargin": _safe(net_profit_margin), "ebitdaMargin": _safe(ebitda_margin),
        "revenueGrowth": _safe(revenue_growth),

        # Cash flow
        "fcfYield": _safe(fcf_yield), "fcfMargin": _safe(fcf_margin),
        "cashConversionRate": _safe(cash_conversion),

        # Leverage & coverage
        "debtToEquity": _safe(debt_to_equity), "debt_to_equity": _safe(debt_to_equity),
        "interestCoverage": _safe(interest_coverage),

        # Liquidity
        "currentRatio": _safe(current_ratio), "current_ratio": _safe(current_ratio),
        "quickRatio": _safe(quick_ratio),

        # Dividends
        "dividendYield": _safe(div_yield), "dividend_yield": _safe(div_yield),
        "dividendPayoutRatio": _safe(div_payout_ratio),

        # Market data
        "beta": _safe(beta), "market_cap": _safe(market_cap),
        "current_price": _safe(current_price), "eps": _safe(eps),
        "volume": _safe(volume), "avg_volume": _safe(avg_volume),
        "target_price": _safe(target_price),

        # Operational efficiency
        "capexIntensity": _safe(capex_intensity),

        # Raw totals for downstream modules
        "totals": {
            "totalDebt": total_debt, "totalCash": total_cash, "ebitda": ebitda,
            "freeCashflow": free_cf, "operatingCashflow": op_cf,
            "capitalExpenditures": capex, "marketCap": market_cap,
            "revenue": revenue, "netIncome": net_income,
            "currentAssets": curr_assets, "currentLiabilities": curr_liab,
            "inventory": inventory,
        },
    }
