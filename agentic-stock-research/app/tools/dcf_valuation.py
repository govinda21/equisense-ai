"""
Comprehensive DCF Valuation Engine
FCFF model with scenario analysis, sensitivity testing, and country/sector-specific defaults.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional
import pandas as pd
import yfinance as yf

from app.utils.validation import DataValidator
from app.utils.rate_limiter import get_yahoo_client

logger = logging.getLogger(__name__)

# --- Config tables ---

RISK_FREE_RATES = {"IN": 0.072, "US": 0.045, "GB": 0.042, "JP": 0.010, "DE": 0.028, "default": 0.070}
MARKET_RISK_PREMIUM = {"IN": 0.06, "US": 0.055, "GB": 0.055, "JP": 0.05, "DE": 0.055, "default": 0.06}
SECTOR_TERMINAL_GROWTH = {
    "Technology": 0.04, "Financial Services": 0.03, "Healthcare": 0.035,
    "Consumer Cyclical": 0.025, "Consumer Defensive": 0.02, "Industrials": 0.03,
    "Energy": 0.02, "Utilities": 0.02, "Real Estate": 0.025, "Basic Materials": 0.025,
    "Communication Services": 0.03, "default": 0.03
}

_GROWTH_MULTIPLIERS = [1.0, 0.95, 0.95, 0.85, 0.85, 0.75, 0.75, 0.70, 0.70, 0.60]
_SCORE_LABEL_MAP = {"excellent": 85, "good": 75, "fair": 65, "moderate": 60, "poor": 45, "weak": 35, "unknown": 50}


def _to_float(x: Any) -> Optional[float]:
    try:
        return float(x) if x is not None else None
    except Exception:
        return None


def _country_code(ticker: str) -> str:
    t = ticker.upper()
    if t.endswith(('.NS', '.BO')): return "IN"
    if t.endswith('.L'): return "GB"
    if t.endswith('.T'): return "JP"
    if t.endswith(('.DE', '.F')): return "DE"
    return "US"


# --- Data classes ---

@dataclass
class DCFInputs:
    revenue_growth_rates: List[float]
    ebitda_margins: List[float]
    terminal_growth_rate: float = 0.03
    risk_free_rate: float = 0.07
    tax_rate: float = 0.25
    working_capital_pct_revenue: float = 0.05
    capex_pct_revenue: float = 0.04
    depreciation_pct_revenue: float = 0.03
    market_risk_premium: float = 0.06
    beta: float = 1.0
    cost_of_debt: float = 0.09
    tax_rate_debt: float = 0.25
    debt_to_equity: float = 0.5
    terminal_value_method: str = "gordon_growth"
    terminal_ebitda_multiple: float = 12.0
    terminal_fcf_multiple: float = 15.0


@dataclass
class DCFScenario:
    name: str
    probability: float
    inputs: DCFInputs


@dataclass
class DCFOutputs:
    enterprise_value: float
    equity_value: float
    intrinsic_value_per_share: float
    pv_explicit_period: float
    pv_terminal_value: float
    net_debt: float
    shares_outstanding: float
    wacc: float
    terminal_value: float
    explicit_fcf: List[float]
    margin_of_safety: float = 0.0
    upside_potential: float = 0.0


# --- Engine ---

class DCFValuationEngine:

    def __init__(self):
        self.default_projection_years = 10

    def _rfr(self, ticker: str) -> float:
        return RISK_FREE_RATES.get(_country_code(ticker), RISK_FREE_RATES["default"])

    def _mrp(self, ticker: str) -> float:
        return MARKET_RISK_PREMIUM.get(_country_code(ticker), MARKET_RISK_PREMIUM["default"])

    def _terminal_growth(self, sector: Optional[str]) -> float:
        if not sector:
            return SECTOR_TERMINAL_GROWTH["default"]
        if sector in SECTOR_TERMINAL_GROWTH:
            return SECTOR_TERMINAL_GROWTH[sector]
        for k in SECTOR_TERMINAL_GROWTH:
            if k.lower() in sector.lower() or sector.lower() in k.lower():
                return SECTOR_TERMINAL_GROWTH[k]
        return SECTOR_TERMINAL_GROWTH["default"]

    def _validate_applicability(self, info: Dict[str, Any]) -> Dict[str, Any]:
        ebitda = info.get("ebitda")
        net_income = info.get("netIncome") or info.get("netIncomeToCommon") or 0
        ocf = info.get("operatingCashflow") or info.get("totalCashFromOperatingActivities") or 0
        fcf = info.get("freeCashflow") or 0
        revenue = info.get("totalRevenue") or info.get("revenue") or 0

        fcf_margin = fcf / revenue if fcf and revenue and fcf > 0 and revenue > 0 else 0

        if not any([ebitda, net_income, fcf, ocf]):
            applicable, reason = False, "insufficient financial data"
        elif net_income < 0 and ocf < 0:
            applicable, reason = False, "negative net income and operating cash flow"
        elif fcf_margin < 0.005 and net_income < 0:
            applicable, reason = False, f"very low FCF margin ({fcf_margin:.1%}) with negative net income"
        else:
            applicable, reason = True, "Company has positive cash flows and earnings"

        return {
            "dcf_applicable": applicable,
            "reason": reason if applicable else f"DCF model not applicable ({reason})",
            "valuation_method": "DCF model applicable" if applicable else "Revenue multiples or growth-based metrics suggested",
            "suggested_metrics": {} if applicable else {
                "revenue": revenue, "market_cap": info.get("marketCap"),
                "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "ebitda": ebitda, "net_income": net_income, "operating_cash_flow": ocf
            }
        }

    async def _fetch_company_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        try:
            yahoo_client = get_yahoo_client()
            info = await yahoo_client.get_info(ticker)

            async def _fetch_financials():
                loop = asyncio.get_event_loop()
                t = await loop.run_in_executor(None, lambda: yf.Ticker(ticker))
                return {
                    "financials": await loop.run_in_executor(None, lambda: t.financials),
                    "balance_sheet": await loop.run_in_executor(None, lambda: t.balance_sheet),
                    "cashflow": await loop.run_in_executor(None, lambda: t.cashflow)
                }

            await yahoo_client.client.rate_limiter.acquire()
            try:
                financials = await _fetch_financials()
            finally:
                yahoo_client.client.rate_limiter.release()

            if not info.get("marketCap"):
                logger.warning(f"DCF: Missing market cap for {ticker}")
                return None

            # Extract actual FCF from cashflow DataFrame
            cf_df = financials.get("cashflow")
            if isinstance(cf_df, pd.DataFrame) and not cf_df.empty:
                for idx in cf_df.index:
                    if "Free Cash Flow" in str(idx):
                        fcf_vals = [(c, float(v)) for c, v in cf_df.loc[idx].items() if pd.notna(v) and v != 0]
                        positive = [(c, v) for c, v in fcf_vals if v > 0]
                        actual_fcf = (positive or fcf_vals)[0][1] if (positive or fcf_vals) else None
                        if actual_fcf:
                            info["freeCashflow"] = actual_fcf
                        break

            return {"info": info, **financials}
        except Exception as e:
            logger.error(f"DCF: Failed to fetch company data for {ticker}: {e}")
            return None

    async def _generate_scenarios(self, company_data: Dict[str, Any]) -> List[DCFScenario]:
        info = company_data["info"]
        ticker = info.get("symbol", "")
        rfr = self._rfr(ticker)
        mrp = self._mrp(ticker)
        sector = info.get("sector")
        tg = self._terminal_growth(sector)

        # Conservative terminal growth for Indian stocks
        if ticker.endswith(('.NS', '.BO')):
            tg = min(tg, 0.02)

        rg = max(info.get("revenueGrowth") or 0.10, 0.10)
        revenue = info.get("totalRevenue") or info.get("revenue") or 0
        ebitda = info.get("ebitda")
        em = (ebitda / revenue) if ebitda and revenue and revenue > 0 else (info.get("operatingMargins") or 0.10)
        em = max(em or 0.10, 0.10)
        beta = max(info.get("beta") or 1.0, 0)
        d_e = max((info.get("debtToEquity") or 50) / 100, 0)

        # CapEx and depreciation ratios
        ocf = info.get("operatingCashflow") or 0
        fcf = info.get("freeCashflow") or 0
        capex_r = abs(ocf - fcf) / revenue if revenue and ocf and fcf else 0.04
        capex_r = abs(info.get("capitalExpenditures") or 0) / revenue if revenue and info.get("capitalExpenditures") else capex_r
        depr_r = capex_r * 0.7

        base = DCFInputs(
            revenue_growth_rates=[rg * m for m in _GROWTH_MULTIPLIERS],
            ebitda_margins=[em] * 10, terminal_growth_rate=tg,
            risk_free_rate=rfr, market_risk_premium=mrp, beta=beta,
            debt_to_equity=d_e, capex_pct_revenue=capex_r, depreciation_pct_revenue=depr_r
        )
        bull = replace(base,
            revenue_growth_rates=[g * 1.5 for g in base.revenue_growth_rates],
            ebitda_margins=[min(m * 1.2, 0.4) for m in base.ebitda_margins],
            terminal_growth_rate=min(tg * 1.33, 0.045),
            beta=beta * 0.9, capex_pct_revenue=capex_r * 1.1,
            depreciation_pct_revenue=depr_r * 1.1, cost_of_debt=0.08,
            debt_to_equity=d_e * 0.8, working_capital_pct_revenue=0.04
        )
        bear = replace(base,
            revenue_growth_rates=[max(g * 0.5, 0.02) for g in base.revenue_growth_rates],
            ebitda_margins=[m * 0.8 for m in base.ebitda_margins],
            terminal_growth_rate=max(tg * 0.67, 0.015),
            market_risk_premium=mrp * 1.2, beta=beta * 1.2, tax_rate=0.30,
            capex_pct_revenue=capex_r * 0.8, depreciation_pct_revenue=depr_r * 0.8,
            cost_of_debt=0.11, debt_to_equity=d_e * 1.2, working_capital_pct_revenue=0.08
        )
        return [DCFScenario("Bull", 0.25, bull), DCFScenario("Base", 0.50, base), DCFScenario("Bear", 0.25, bear)]

    def _terminal_value_methods(self, final_fcf: float, inputs: DCFInputs, wacc: float) -> Dict[str, float]:
        if wacc > inputs.terminal_growth_rate:
            tv_gg = (final_fcf * (1 + inputs.terminal_growth_rate)) / (wacc - inputs.terminal_growth_rate)
        else:
            tv_gg = final_fcf * 20
        return {
            "gordon_growth": tv_gg,
            "exit_multiple": final_fcf * inputs.terminal_fcf_multiple,
            "perpetuity_growth": tv_gg,
        }

    async def _calculate_dcf(self, company_data: Dict[str, Any], inputs: DCFInputs) -> DCFOutputs:
        info = company_data["info"]
        ticker = info.get("symbol", "")
        market_cap = _to_float(info.get("marketCap")) or 0
        current_revenue = _to_float(info.get("totalRevenue") or info.get("revenue")) or 0

        if not current_revenue:
            ps = info.get("priceToSalesTrailing12Months", 2.0)
            if market_cap and ps and ps > 0:
                current_revenue = market_cap / ps
                logger.warning(f"DCF: Estimated revenue from market cap for {ticker}: ${current_revenue:,.0f}")
            else:
                raise ValueError(f"Unable to determine revenue for {ticker}")

        # WACC
        cost_equity = inputs.risk_free_rate + inputs.beta * inputs.market_risk_premium
        after_tax_debt = inputs.cost_of_debt * (1 - inputs.tax_rate_debt)
        total_cap = 1 + inputs.debt_to_equity
        wacc = cost_equity / total_cap + after_tax_debt * inputs.debt_to_equity / total_cap

        sector = info.get("sector", "").lower()
        is_stable = any(t in sector for t in ["consumer", "defensive", "utilities", "energy"])
        wacc = max(0.04 if is_stable else 0.05, min(0.15 if is_stable else 0.30, wacc))
        if ticker.endswith(('.NS', '.BO')):
            wacc = min(wacc + 0.015, 0.15)
        if inputs.terminal_growth_rate >= wacc:
            inputs = replace(inputs, terminal_growth_rate=wacc * 0.5)

        # Starting FCF
        fcf_raw = _to_float(info.get("freeCashflow"))
        ocf_raw = _to_float(info.get("operatingCashflow"))
        capex_raw = _to_float(info.get("capitalExpenditures"))
        if capex_raw and capex_raw > 0 and ocf_raw and ocf_raw > 0:
            capex_raw = -abs(capex_raw)

        if fcf_raw and abs(fcf_raw) > 0:
            starting_fcf = fcf_raw
        elif ocf_raw is not None and capex_raw is not None:
            starting_fcf = ocf_raw + capex_raw
        else:
            em = inputs.ebitda_margins[0]
            starting_fcf = (current_revenue * em - current_revenue * inputs.depreciation_pct_revenue) * \
                           (1 - inputs.tax_rate) + current_revenue * inputs.depreciation_pct_revenue - \
                           current_revenue * inputs.capex_pct_revenue

        if starting_fcf is None:
            raise ValueError(f"Unable to determine starting FCF for {ticker}")

        # Project FCFs using revenue-driven model
        explicit_fcf = []
        projected_revenue = current_revenue

        for year, growth in enumerate(inputs.revenue_growth_rates):
            projected_revenue *= (1 + growth)

            ebitda = projected_revenue * inputs.ebitda_margins[min(year, len(inputs.ebitda_margins) - 1)]
            depreciation = projected_revenue * inputs.depreciation_pct_revenue
            ebit = ebitda - depreciation
            nopat = ebit * (1 - inputs.tax_rate)

            capex = projected_revenue * inputs.capex_pct_revenue
            change_wc = projected_revenue * inputs.working_capital_pct_revenue * growth

            fcf = nopat + depreciation - capex - change_wc
            explicit_fcf.append(fcf)

        tv_methods = self._terminal_value_methods(explicit_fcf[-1], inputs, wacc)
        terminal_value = tv_methods[inputs.terminal_value_method]
        discount_factors = [(1 + wacc) ** -i for i in range(1, len(explicit_fcf) + 1)]
        pv_explicit = sum(f * d for f, d in zip(explicit_fcf, discount_factors))
        pv_terminal = terminal_value * discount_factors[-1]
        enterprise_value = pv_explicit + pv_terminal

        # Net debt & equity value
        ev_implied = info.get("enterpriseValue")
        if ev_implied and market_cap:
            net_debt = ev_implied - market_cap
        else:
            net_debt = (info.get("totalDebt") or 0) - (info.get("totalCash") or 0)
        equity_value = enterprise_value - net_debt

        # Shares outstanding
        current_price = _to_float(info.get("currentPrice") or info.get("regularMarketPrice"))
        shares = _to_float(info.get("sharesOutstanding") or info.get("impliedSharesOutstanding"))
        market_cap_f = _to_float(info.get("marketCap") or market_cap)

        if not shares or shares <= 0:
            if market_cap_f and current_price and current_price > 0:
                est = market_cap_f / current_price
                shares = est if 1e3 <= est <= 1e13 else None
            if not shares:
                logger.warning(f"[{ticker}] DCF: Missing shares outstanding; per-share value unreliable")
                shares = 1.0

        intrinsic = equity_value / shares if shares and shares > 0 else 0.0
        if intrinsic < 0:
            logger.warning(f"[{ticker}] DCF: Negative intrinsic value: {intrinsic:.2f}")

        return DCFOutputs(
            enterprise_value=enterprise_value, equity_value=equity_value,
            intrinsic_value_per_share=intrinsic, pv_explicit_period=pv_explicit,
            pv_terminal_value=pv_terminal, net_debt=net_debt, shares_outstanding=shares,
            wacc=wacc, terminal_value=terminal_value, explicit_fcf=explicit_fcf
        )

    def _sanity_check(self, result: DCFOutputs, current_price: float, info: Dict) -> Dict[str, Any]:
        warnings = []
        if current_price and current_price > 0:
            ratio = result.intrinsic_value_per_share / current_price
            if ratio < 0.3: warnings.append(f"Intrinsic value ratio: {ratio:.2f}x (very undervalued)")
            elif ratio > 3.0: warnings.append(f"Intrinsic value ratio: {ratio:.2f}x (very overvalued)")
        if result.equity_value < 0: warnings.append(f"Negative equity value: ${result.equity_value:,.0f}")
        if result.intrinsic_value_per_share < 0: warnings.append(f"Negative intrinsic value per share")
        if result.wacc < 0.04: warnings.append(f"Very low WACC: {result.wacc:.2%}")
        elif result.wacc > 0.15: warnings.append(f"Very high WACC: {result.wacc:.2%}")
        total = result.pv_explicit_period + result.pv_terminal_value
        if total > 0:
            tv_pct = result.pv_terminal_value / total
            if tv_pct < 0.3: warnings.append(f"Terminal value only {tv_pct:.1%} of total")
            elif tv_pct > 0.9: warnings.append(f"Terminal value is {tv_pct:.1%} of total")
        if result.net_debt < -1e9:
            warnings.append(f"Very high cash position: ${-result.net_debt/1e9:.1f}B")
        return {"is_reasonable": not warnings, "warnings": warnings,
                "confidence": "high" if not warnings else "moderate" if len(warnings) <= 2 else "low"}

    def _weighted_dcf(self, scenario_results: List[Dict]) -> Optional[DCFOutputs]:
        wev = weq = wiv = wwacc = 0.0
        for s in scenario_results:
            p, r = s["probability"], s["result"]
            wev += r.enterprise_value * p
            weq += r.equity_value * p
            wiv += r.intrinsic_value_per_share * p
            wwacc += r.wacc * p
        if wev <= 0 or weq <= 0:
            logger.warning("DCF produced negative enterprise/equity value")
        base_r = next(s["result"] for s in scenario_results if "Base" in s["scenario"])
        return DCFOutputs(enterprise_value=wev, equity_value=weq, intrinsic_value_per_share=wiv,
                          pv_explicit_period=base_r.pv_explicit_period, pv_terminal_value=base_r.pv_terminal_value,
                          net_debt=base_r.net_debt, shares_outstanding=base_r.shares_outstanding,
                          wacc=wwacc, terminal_value=base_r.terminal_value, explicit_fcf=base_r.explicit_fcf)

    async def _sensitivity_analysis(self, company_data: Dict, base: DCFScenario) -> List[DCFOutputs]:
        """
        Perform sensitivity analysis based on the base scenario.
        """
        results = []

        for wacc_delta, tg_delta, growth_mult in [(-0.01, -0.01, 0.9), (0.01, 0.01, 1.1)]:
            # Adjust inputs safely
            adjusted_inputs = replace(
                base.inputs,
                revenue_growth_rates=[g * growth_mult for g in base.inputs.revenue_growth_rates],
                risk_free_rate=base.inputs.risk_free_rate + wacc_delta,
                terminal_growth_rate=base.inputs.terminal_growth_rate + tg_delta
            )

            try:
                r = await self._calculate_dcf(company_data, adjusted_inputs)
                results.append(r)
            except Exception as e:
                logger.error(f"Sensitivity scenario failed: {e}")

        return results

    def _trade_rules(self, result: DCFOutputs, current_price: Optional[float]) -> Dict[str, Any]:
        iv = result.intrinsic_value_per_share
        buy_zone = iv * 0.75
        target_price = iv * 1.20
        if current_price:
            mos = (iv - current_price) / iv
            upside = (iv - current_price) / current_price
            stop_loss = current_price * 0.85
            rec = ("Strong Buy" if current_price <= buy_zone else "Buy" if current_price <= iv else
                   "Hold" if current_price <= iv * 1.1 else "Weak Hold" if current_price <= iv * 1.2 else "Sell")
        else:
            mos = upside = 0
            stop_loss = buy_zone * 0.85
            rec = "Insufficient Data"
        return {"margin_of_safety": mos, "upside_potential": upside, "recommendation": rec,
                "buy_zone": buy_zone, "target_price": target_price, "stop_loss": stop_loss}

    async def value_company(self, ticker: str, scenarios: Optional[List[DCFScenario]] = None,
                            current_price: Optional[float] = None) -> Dict[str, Any]:
        company_data = await self._fetch_company_data(ticker)
        if not company_data:
            return {"error": "Unable to fetch company data"}

        info = company_data["info"]
        validation = self._validate_applicability(info)
        if not validation["dcf_applicable"]:
            logger.warning(f"DCF skipped for {ticker}: {validation['reason']}")
            return {
                "ticker": ticker, "dcf_applicable": False, **validation,
                "current_price": current_price,
                "warning": "DCF analysis is unreliable for loss-making companies."
            }

        if scenarios is None:
            scenarios = await self._generate_scenarios(company_data)

        scenario_results = []
        for scenario in scenarios:
            try:
                r = await self._calculate_dcf(company_data, scenario.inputs)
                scenario_results.append({"scenario": scenario.name, "probability": scenario.probability, "result": r})
            except Exception as e:
                logger.error(f"DCF scenario {scenario.name} failed for {ticker}: {e}")

        if not scenario_results:
            return {"error": "All DCF scenarios failed"}

        weighted = self._weighted_dcf(scenario_results)
        if weighted is None:
            return {
                "ticker": ticker, "dcf_applicable": False,
                "reason": "DCF calculation produced negative values",
                "valuation_method": "Revenue multiples or growth-based metrics suggested",
                "current_price": current_price,
                "warning": "DCF produced negative values — using revenue-based valuation instead."
            }

        cp = _to_float(info.get("currentPrice") or info.get("regularMarketPrice")) or current_price or 0
        sensitivity = await self._sensitivity_analysis(company_data, scenarios[0])
        sanity = self._sanity_check(weighted, cp, info)
        trade = self._trade_rules(weighted, cp)

        return {
            "ticker": ticker, "dcf_applicable": True,
            "intrinsic_value": weighted.intrinsic_value_per_share,
            "fair_value_range": {
                "low": weighted.intrinsic_value_per_share * 0.8,
                "high": weighted.intrinsic_value_per_share * 1.25
            },
            "current_price": cp, **trade,
            "scenario_results": scenario_results,
            "sensitivity_analysis": sensitivity,
            "sanity_check": sanity,
            "key_assumptions": {
                "wacc": weighted.wacc,
                "terminal_growth": scenarios[0].inputs.terminal_growth_rate,
                "projection_years": self.default_projection_years
            }
        }


async def perform_dcf_valuation(ticker: str, current_price: Optional[float] = None) -> Dict[str, Any]:
    return await DCFValuationEngine().value_company(ticker, current_price=current_price)


def calculate_wacc(cost_of_equity: float, cost_of_debt: float, tax_rate: float, market_value_equity: float, market_value_debt: float) -> float:
    """
    Calculate the Weighted Average Cost of Capital (WACC).

    WACC = (E / (E + D)) * Ke + (D / (E + D)) * Kd * (1 - Tax)

    :param cost_of_equity: Cost of equity (Ke)
    :param cost_of_debt: Cost of debt (Kd)
    :param tax_rate: Corporate tax rate
    :param market_value_equity: Market value of equity (E)
    :param market_value_debt: Market value of debt (D)
    :return: Weighted Average Cost of Capital (WACC)
    """
    total_value = market_value_equity + market_value_debt
    if total_value == 0:
        raise ValueError("Total market value of equity and debt cannot be zero.")

    equity_weight = market_value_equity / total_value
    debt_weight = market_value_debt / total_value

    wacc = (equity_weight * cost_of_equity) + (debt_weight * cost_of_debt * (1 - tax_rate))
    return wacc


def estimate_terminal_value(final_fcf: float, growth_rate: float, discount_rate: float) -> float:
    """
    Estimate the terminal value using the Gordon Growth Model.

    TV = FCF * (1 + g) / (r - g)

    :param final_fcf: Final year free cash flow (FCF)
    :param growth_rate: Perpetual growth rate (g)
    :param discount_rate: Discount rate (r)
    :return: Terminal value (TV)
    """
    if discount_rate <= growth_rate:
        raise ValueError("Discount rate must be greater than growth rate to avoid division by zero.")

    terminal_value = final_fcf * (1 + growth_rate) / (discount_rate - growth_rate)
    return terminal_value


def calculate_intrinsic_value_per_share(fcf_projections: List[float], terminal_value: float, wacc: float, net_debt: float, shares_outstanding: float) -> float:
    """
    Calculate the intrinsic value per share.

    :param fcf_projections: List of projected free cash flows (FCFs).
    :param terminal_value: Terminal value of the company.
    :param wacc: Weighted Average Cost of Capital (WACC).
    :param net_debt: Net debt of the company.
    :param shares_outstanding: Number of shares outstanding.
    :return: Intrinsic value per share.
    """
    if shares_outstanding <= 0:
        raise ValueError("Shares outstanding must be greater than zero.")

    # Discount FCFs to present value
    discount_factors = [(1 + wacc) ** i for i in range(1, len(fcf_projections) + 1)]
    pv_fcf = sum(fcf / df for fcf, df in zip(fcf_projections, discount_factors))

    # Discount terminal value to present value
    pv_terminal = terminal_value / discount_factors[-1]

    # Calculate equity value
    equity_value = pv_fcf + pv_terminal - net_debt

    # Calculate intrinsic value per share
    intrinsic_value = equity_value / shares_outstanding
    return intrinsic_value
