"""
Comprehensive DCF Valuation Engine
Implements FCFF and FCFE models with scenario analysis and sensitivity testing
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import yfinance as yf

from app.utils.validation import DataValidator

logger = logging.getLogger(__name__)


# Country-specific risk-free rates (10Y treasury yields, Oct 2025)
RISK_FREE_RATES = {
    "IN": 0.072,  # India 10Y G-Sec: 7.2%
    "US": 0.045,  # US 10Y Treasury: 4.5%
    "GB": 0.042,  # UK 10Y Gilt: 4.2%
    "JP": 0.010,  # Japan 10Y JGB: 1.0%
    "DE": 0.028,  # Germany 10Y Bund: 2.8%
    "default": 0.070  # Conservative default
}

# Sector-specific terminal growth rates (research-based)
SECTOR_TERMINAL_GROWTH = {
    "Technology": 0.04,  # 4% - higher long-term growth
    "Financial Services": 0.03,  # 3% - GDP+ growth
    "Healthcare": 0.035,  # 3.5% - demographic tailwinds
    "Consumer Cyclical": 0.025,  # 2.5% - GDP-aligned
    "Consumer Defensive": 0.02,  # 2% - mature, stable
    "Industrials": 0.03,  # 3% - infrastructure growth
    "Energy": 0.02,  # 2% - mature sector
    "Utilities": 0.02,  # 2% - regulated, stable
    "Real Estate": 0.025,  # 2.5% - population growth
    "Basic Materials": 0.025,  # 2.5% - commodity cycle
    "Communication Services": 0.03,  # 3% - moderate growth
    "default": 0.03  # 3% - conservative baseline
}

# Market risk premiums by country
MARKET_RISK_PREMIUM = {
    "IN": 0.06,  # India: 6% - emerging market premium
    "US": 0.055,  # US: 5.5% - developed market
    "GB": 0.055,  # UK: 5.5%
    "JP": 0.05,  # Japan: 5%
    "DE": 0.055,  # Germany: 5.5%
    "default": 0.06  # Conservative default
}


@dataclass
class DCFInputs:
    """
    DCF model inputs with intelligent defaults
    
    Research-backed defaults based on:
    - Terminal growth: 2-4% (long-term GDP growth proxy)
    - Risk-free rates: Country-specific 10Y treasury yields (2025)
    - Market risk premium: 5-7% (historical equity premium)
    """
    # Revenue projections
    revenue_growth_rates: List[float]  # 5-10 year growth rates
    ebitda_margins: List[float]  # EBITDA margin progression
    
    # Required parameters with research-backed defaults
    terminal_growth_rate: float = 0.03  # 3% - conservative long-term GDP growth
    risk_free_rate: float = 0.07  # 7% - India 10Y G-Sec default
    
    # Profitability
    tax_rate: float = 0.25  # Effective tax rate (India corporate: 25%)
    
    # Working capital & capex
    working_capital_pct_revenue: float = 0.05  # 5% - typical working capital need
    capex_pct_revenue: float = 0.04  # 4% - maintenance capex
    depreciation_pct_revenue: float = 0.03  # 3% - typical D&A
    
    # Cost of capital with defaults
    market_risk_premium: float = 0.06  # 6% - India equity risk premium
    beta: float = 1.0  # Market beta default
    cost_of_debt: float = 0.09  # 9% - typical Indian corporate debt cost
    tax_rate_debt: float = 0.25  # Tax shield
    debt_to_equity: float = 0.5  # 50% D/E ratio default
    
    # Terminal value
    terminal_fcf_multiple: Optional[float] = None  # Alternative to Gordon Growth


@dataclass
class DCFScenario:
    """DCF scenario with probability weighting"""
    name: str
    probability: float
    inputs: DCFInputs
    

@dataclass
class DCFOutputs:
    """DCF valuation results"""
    # Core results
    enterprise_value: float
    equity_value: float
    intrinsic_value_per_share: float
    
    # Components
    pv_explicit_period: float
    pv_terminal_value: float
    net_debt: float
    shares_outstanding: float
    
    # Intermediate calculations
    wacc: float
    terminal_value: float
    explicit_fcf: List[float]
    
    # Risk metrics
    margin_of_safety: float  # vs current price
    upside_potential: float  # % upside to intrinsic value


class DCFValuationEngine:
    """
    Comprehensive DCF valuation engine with intelligent defaults
    
    Features:
    - Country-specific risk-free rates
    - Sector-specific terminal growth rates
    - Automatic data validation and fallbacks
    - 90%+ success rate target through defensive programming
    """
    
    def __init__(self):
        self.default_projection_years = 10
        # Legacy defaults kept for backward compatibility
        self.india_risk_free_rate = RISK_FREE_RATES["IN"]
        self.india_market_risk_premium = MARKET_RISK_PREMIUM["IN"]
    
    def _get_country_code(self, ticker: str) -> str:
        """
        Determine country code from ticker
        
        Returns country code (IN, US, GB, etc.) based on ticker suffix
        """
        ticker_upper = ticker.upper()
        
        # Indian exchanges
        if ticker_upper.endswith(('.NS', '.BO')):
            return "IN"
        # US exchanges (default)
        elif any(ticker_upper.endswith(suffix) for suffix in ['.US', '']):
            return "US"
        # UK exchanges
        elif ticker_upper.endswith('.L'):
            return "GB"
        # Japanese exchanges
        elif ticker_upper.endswith('.T'):
            return "JP"
        # German exchanges
        elif ticker_upper.endswith(('.DE', '.F')):
            return "DE"
        else:
            return "default"
    
    def _get_risk_free_rate(self, ticker: str) -> float:
        """Get country-specific risk-free rate"""
        country_code = self._get_country_code(ticker)
        return RISK_FREE_RATES.get(country_code, RISK_FREE_RATES["default"])
    
    def _get_market_risk_premium(self, ticker: str) -> float:
        """Get country-specific market risk premium"""
        country_code = self._get_country_code(ticker)
        return MARKET_RISK_PREMIUM.get(country_code, MARKET_RISK_PREMIUM["default"])
    
    def _get_terminal_growth_rate(self, sector: Optional[str]) -> float:
        """Get sector-specific terminal growth rate"""
        if not sector:
            return SECTOR_TERMINAL_GROWTH["default"]
        
        # Try exact match first
        if sector in SECTOR_TERMINAL_GROWTH:
            return SECTOR_TERMINAL_GROWTH[sector]
        
        # Try partial match
        for key in SECTOR_TERMINAL_GROWTH:
            if key.lower() in sector.lower() or sector.lower() in key.lower():
                return SECTOR_TERMINAL_GROWTH[key]
        
        return SECTOR_TERMINAL_GROWTH["default"]
        
    async def value_company(
        self, 
        ticker: str,
        scenarios: Optional[List[DCFScenario]] = None,
        current_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive DCF valuation with scenario analysis
        """
        try:
            # Get company data
            company_data = await self._fetch_company_data(ticker)
            if not company_data:
                return {"error": "Unable to fetch company data"}
            
            # Generate scenarios if not provided
            if scenarios is None:
                scenarios = await self._generate_default_scenarios(company_data)
            
            # Calculate DCF for each scenario
            scenario_results = []
            for scenario in scenarios:
                try:
                    dcf_result = await self._calculate_dcf(company_data, scenario.inputs)
                    scenario_results.append({
                        "scenario": scenario.name,
                        "probability": scenario.probability,
                        "result": dcf_result
                    })
                except Exception as e:
                    logger.error(f"DCF calculation failed for scenario {scenario.name}: {e}")
                    continue
            
            if not scenario_results:
                return {"error": "All DCF scenarios failed"}
            
            # Calculate probability-weighted results
            weighted_result = self._calculate_weighted_dcf(scenario_results)
            
            # Generate sensitivity analysis
            sensitivity = await self._sensitivity_analysis(company_data, scenarios[0].inputs)
            
            # Calculate margin of safety and trade rules
            trade_rules = self._calculate_trade_rules(weighted_result, current_price)
            
            return {
                "ticker": ticker,
                "intrinsic_value": weighted_result.intrinsic_value_per_share,
                "fair_value_range": {
                    "low": weighted_result.intrinsic_value_per_share * 0.8,
                    "high": weighted_result.intrinsic_value_per_share * 1.25
                },
                "current_price": current_price,
                "margin_of_safety": trade_rules["margin_of_safety"],
                "upside_potential": trade_rules["upside_potential"],
                "recommendation": trade_rules["recommendation"],
                "buy_zone": trade_rules["buy_zone"],
                "target_price": trade_rules["target_price"],
                "stop_loss": trade_rules["stop_loss"],
                "scenario_results": scenario_results,
                "sensitivity_analysis": sensitivity,
                "key_assumptions": {
                    "wacc": weighted_result.wacc,
                    "terminal_growth": scenarios[0].inputs.terminal_growth_rate,
                    "projection_years": self.default_projection_years
                }
            }
            
        except Exception as e:
            logger.error(f"DCF valuation failed for {ticker}: {e}")
            return {"error": str(e)}
    
    async def _fetch_company_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch comprehensive company data for DCF"""
        try:
            logger.info(f"DCF: Fetching company data for {ticker}")
            
            def _fetch():
                t = yf.Ticker(ticker)
                info = t.info or {}
                financials = t.financials
                balance_sheet = t.balance_sheet
                cashflow = t.cashflow
                
                return {
                    "info": info,
                    "financials": financials,
                    "balance_sheet": balance_sheet,
                    "cashflow": cashflow
                }
            
            data = await asyncio.to_thread(_fetch)
            info = data["info"]
            
            # Enhanced logging for debugging
            logger.info(f"DCF data availability for {ticker}: "
                       f"marketCap={info.get('marketCap')}, "
                       f"totalRevenue={info.get('totalRevenue')}, "
                       f"freeCashflow={info.get('freeCashflow')}, "
                       f"beta={info.get('beta')}, "
                       f"sharesOutstanding={info.get('sharesOutstanding')}, "
                       f"currentPrice={info.get('currentPrice') or info.get('regularMarketPrice')}")
            
            # Validate essential data
            if not info.get("marketCap"):
                logger.warning(f"DCF: Missing market cap for {ticker} - cannot perform DCF")
                return None
            
            if not info.get("totalRevenue"):
                logger.warning(f"DCF: Missing revenue data for {ticker} - will use estimates")
            
            if not info.get("freeCashflow"):
                logger.warning(f"DCF: Missing free cash flow data for {ticker} - will estimate from other metrics")
                
            logger.info(f"DCF: Successfully fetched company data for {ticker}")
            return data
            
        except Exception as e:
            logger.error(f"DCF: Failed to fetch company data for {ticker}: {e}")
            return None
    
    async def _generate_default_scenarios(self, company_data: Dict[str, Any]) -> List[DCFScenario]:
        """
        Generate default bull/base/bear scenarios with intelligent defaults
        
        Uses country-specific and sector-specific parameters for accuracy
        """
        info = company_data["info"]
        ticker = info.get("symbol", "")
        
        # Get country-specific parameters
        risk_free_rate = self._get_risk_free_rate(ticker)
        market_risk_premium = self._get_market_risk_premium(ticker)
        
        # Get sector-specific terminal growth
        sector = info.get("sector")
        terminal_growth = self._get_terminal_growth_rate(sector)
        
        logger.info(f"DCF scenario generation for {ticker}: "
                   f"country_rfr={risk_free_rate:.2%}, "
                   f"sector={sector}, "
                   f"terminal_growth={terminal_growth:.2%}")
        
        # Extract current metrics with defensive fallbacks
        current_revenue_growth = info.get("revenueGrowth") or 0.10
        if current_revenue_growth is None or current_revenue_growth <= 0:
            current_revenue_growth = 0.10  # 10% default
        
        current_ebitda_margin = info.get("operatingMargins") or 0.15
        if current_ebitda_margin is None or current_ebitda_margin <= 0:
            current_ebitda_margin = 0.15  # 15% default
        
        current_beta = info.get("beta") or 1.0
        if current_beta is None or current_beta <= 0:
            current_beta = 1.0  # Market beta
        
        debt_to_equity_raw = info.get("debtToEquity") or 50
        if debt_to_equity_raw is None or debt_to_equity_raw < 0:
            debt_to_equity_raw = 50
        current_debt_equity = debt_to_equity_raw / 100
        
        # Base scenario with intelligent defaults
        base_inputs = DCFInputs(
            revenue_growth_rates=[
                current_revenue_growth * 0.9,  # Year 1: slight moderation
                current_revenue_growth * 0.8,  # Year 2-3: further moderation
                current_revenue_growth * 0.8,
                current_revenue_growth * 0.6,  # Year 4-5: mature growth
                current_revenue_growth * 0.6,
                current_revenue_growth * 0.4,  # Year 6-10: stable growth
                current_revenue_growth * 0.4,
                current_revenue_growth * 0.3,
                current_revenue_growth * 0.3,
                current_revenue_growth * 0.2
            ],
            ebitda_margins=[current_ebitda_margin] * 10,  # Stable margins
            terminal_growth_rate=terminal_growth,  # Sector-specific
            risk_free_rate=risk_free_rate,  # Country-specific
            market_risk_premium=market_risk_premium,  # Country-specific
            beta=current_beta,
            debt_to_equity=current_debt_equity
            # All other parameters use defaults from DCFInputs dataclass
        )
        
        # Bull scenario - higher growth and margins
        bull_inputs = DCFInputs(
            revenue_growth_rates=[g * 1.5 for g in base_inputs.revenue_growth_rates],
            ebitda_margins=[min(m * 1.2, 0.4) for m in base_inputs.ebitda_margins],  # Cap at 40%
            terminal_growth_rate=min(terminal_growth * 1.33, 0.045),  # Higher, capped at 4.5%
            risk_free_rate=risk_free_rate,
            market_risk_premium=market_risk_premium,
            beta=current_beta * 0.9,  # Lower risk perception
            working_capital_pct_revenue=0.04,  # Better WC management
            capex_pct_revenue=0.05,  # Higher investment for growth
            cost_of_debt=0.08,
            debt_to_equity=current_debt_equity * 0.8  # Lower leverage
        )
        
        # Bear scenario - lower growth and margins
        bear_inputs = DCFInputs(
            revenue_growth_rates=[max(g * 0.5, 0.02) for g in base_inputs.revenue_growth_rates],
            ebitda_margins=[m * 0.8 for m in base_inputs.ebitda_margins],
            terminal_growth_rate=max(terminal_growth * 0.67, 0.015),  # Lower, floored at 1.5%
            risk_free_rate=risk_free_rate,
            market_risk_premium=market_risk_premium * 1.2,  # Higher risk premium
            beta=current_beta * 1.2,  # Higher risk
            tax_rate=0.30,  # Higher effective tax rate
            working_capital_pct_revenue=0.08,  # Worse WC management
            capex_pct_revenue=0.03,  # Lower investment
            cost_of_debt=0.11,
            debt_to_equity=current_debt_equity * 1.2  # Higher leverage
        )
        
        return [
            DCFScenario("Bull", 0.25, bull_inputs),
            DCFScenario("Base", 0.50, base_inputs),
            DCFScenario("Bear", 0.25, bear_inputs)
        ]
    
    async def _calculate_dcf(self, company_data: Dict[str, Any], inputs: DCFInputs) -> DCFOutputs:
        """
        Calculate DCF valuation for given inputs with defensive validation
        
        Returns DCFOutputs with enterprise value, equity value, and per-share intrinsic value
        Raises ValueError only for truly unrecoverable situations
        """
        info = company_data["info"]
        
        # Get current financials with multiple fallbacks
        current_revenue = info.get("totalRevenue") or info.get("revenue") or 0
        
        # If no revenue, try to estimate from market cap and multiples
        if not current_revenue or current_revenue <= 0:
            market_cap = info.get("marketCap", 0)
            ps_ratio = info.get("priceToSalesTrailing12Months", 2.0)
            
            if market_cap and ps_ratio and ps_ratio > 0:
                current_revenue = market_cap / ps_ratio
                logger.warning(f"DCF: Estimated revenue from market cap for {info.get('symbol', 'unknown')}: ${current_revenue:,.0f}")
            else:
                raise ValueError(f"Unable to determine current revenue for {info.get('symbol', 'unknown')}")
        
        # Calculate WACC with validation
        cost_of_equity = inputs.risk_free_rate + inputs.beta * inputs.market_risk_premium
        after_tax_cost_of_debt = inputs.cost_of_debt * (1 - inputs.tax_rate_debt)
        
        # Weight of equity and debt
        total_capital = 1 + inputs.debt_to_equity
        weight_equity = 1 / total_capital
        weight_debt = inputs.debt_to_equity / total_capital
        
        wacc = (cost_of_equity * weight_equity) + (after_tax_cost_of_debt * weight_debt)
        
        # Validate WACC is reasonable (5% to 30%)
        if wacc < 0.05:
            logger.warning(f"DCF: WACC too low ({wacc:.2%}), using 5% minimum")
            wacc = 0.05
        elif wacc > 0.30:
            logger.warning(f"DCF: WACC too high ({wacc:.2%}), capping at 30%")
            wacc = 0.30
        
        # Critical: Ensure terminal growth < WACC (Gordon Growth Model requirement)
        if inputs.terminal_growth_rate >= wacc:
            logger.warning(f"DCF: Terminal growth ({inputs.terminal_growth_rate:.2%}) >= WACC ({wacc:.2%}), adjusting")
            inputs.terminal_growth_rate = wacc * 0.5  # Set to 50% of WACC
        
        # Project cash flows
        explicit_fcf = []
        projected_revenue = current_revenue
        
        for i, growth_rate in enumerate(inputs.revenue_growth_rates):
            # Revenue projection
            projected_revenue *= (1 + growth_rate)
            
            # EBITDA
            ebitda = projected_revenue * inputs.ebitda_margins[i]
            
            # EBIT (EBITDA - Depreciation)
            depreciation = projected_revenue * inputs.depreciation_pct_revenue
            ebit = ebitda - depreciation
            
            # NOPAT (Net Operating Profit After Tax)
            nopat = ebit * (1 - inputs.tax_rate)
            
            # Change in Working Capital
            if i == 0:
                delta_wc = projected_revenue * inputs.working_capital_pct_revenue
            else:
                delta_wc = (projected_revenue - prev_revenue) * inputs.working_capital_pct_revenue
            
            # CapEx
            capex = projected_revenue * inputs.capex_pct_revenue
            
            # Free Cash Flow to Firm (FCFF)
            fcff = nopat + depreciation - capex - delta_wc
            explicit_fcf.append(fcff)
            
            prev_revenue = projected_revenue
        
        # Terminal Value
        terminal_fcf = explicit_fcf[-1] * (1 + inputs.terminal_growth_rate)
        if inputs.terminal_fcf_multiple:
            terminal_value = terminal_fcf * inputs.terminal_fcf_multiple
        else:
            terminal_value = terminal_fcf / (wacc - inputs.terminal_growth_rate)
        
        # Present Value calculations
        discount_factors = [(1 + wacc) ** -i for i in range(1, len(explicit_fcf) + 1)]
        pv_explicit_fcf = sum(fcf * df for fcf, df in zip(explicit_fcf, discount_factors))
        pv_terminal_value = terminal_value * discount_factors[-1]
        
        # Enterprise Value
        enterprise_value = pv_explicit_fcf + pv_terminal_value
        
        # Equity Value
        net_debt = (info.get("totalDebt", 0) or 0) - (info.get("totalCash", 0) or 0)
        equity_value = enterprise_value - net_debt
        
        # Per-share value with fallbacks
        shares_outstanding = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding") or 0
        
        # If no shares data, try to estimate from market cap and price
        if not shares_outstanding or shares_outstanding <= 0:
            market_cap = info.get("marketCap", 0)
            current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
            
            if market_cap and current_price and current_price > 0:
                shares_outstanding = market_cap / current_price
                logger.warning(f"DCF: Estimated shares outstanding from market cap: {shares_outstanding:,.0f}")
            else:
                raise ValueError(f"Unable to determine shares outstanding for {info.get('symbol', 'unknown')}")
        
        intrinsic_value_per_share = equity_value / shares_outstanding
        
        # Sanity check: intrinsic value should be positive and reasonable
        if intrinsic_value_per_share < 0:
            logger.warning(f"DCF: Negative intrinsic value ({intrinsic_value_per_share:.2f}), likely high net debt")
        elif intrinsic_value_per_share > 1e6:
            logger.warning(f"DCF: Unreasonably high intrinsic value ({intrinsic_value_per_share:.2f}), check inputs")
        
        return DCFOutputs(
            enterprise_value=enterprise_value,
            equity_value=equity_value,
            intrinsic_value_per_share=intrinsic_value_per_share,
            pv_explicit_period=pv_explicit_fcf,
            pv_terminal_value=pv_terminal_value,
            net_debt=net_debt,
            shares_outstanding=shares_outstanding,
            wacc=wacc,
            terminal_value=terminal_value,
            explicit_fcf=explicit_fcf,
            margin_of_safety=0.0,  # Will be calculated later
            upside_potential=0.0   # Will be calculated later
        )
    
    def _calculate_weighted_dcf(self, scenario_results: List[Dict[str, Any]]) -> DCFOutputs:
        """Calculate probability-weighted DCF results"""
        weighted_enterprise_value = 0
        weighted_equity_value = 0
        weighted_intrinsic_value = 0
        weighted_wacc = 0
        
        for scenario in scenario_results:
            prob = scenario["probability"]
            result = scenario["result"]
            
            weighted_enterprise_value += result.enterprise_value * prob
            weighted_equity_value += result.equity_value * prob
            weighted_intrinsic_value += result.intrinsic_value_per_share * prob
            weighted_wacc += result.wacc * prob
        
        # Use the base scenario's other values
        base_result = next(s["result"] for s in scenario_results if "Base" in s["scenario"])
        
        return DCFOutputs(
            enterprise_value=weighted_enterprise_value,
            equity_value=weighted_equity_value,
            intrinsic_value_per_share=weighted_intrinsic_value,
            pv_explicit_period=base_result.pv_explicit_period,
            pv_terminal_value=base_result.pv_terminal_value,
            net_debt=base_result.net_debt,
            shares_outstanding=base_result.shares_outstanding,
            wacc=weighted_wacc,
            terminal_value=base_result.terminal_value,
            explicit_fcf=base_result.explicit_fcf,
            margin_of_safety=0.0,
            upside_potential=0.0
        )
    
    async def _sensitivity_analysis(
        self, 
        company_data: Dict[str, Any], 
        base_inputs: DCFInputs
    ) -> Dict[str, Any]:
        """Generate sensitivity analysis grid"""
        
        # WACC sensitivity (±200bps)
        wacc_range = [-0.02, -0.01, 0, 0.01, 0.02]
        
        # Terminal growth sensitivity (±100bps)
        terminal_growth_range = [-0.01, -0.005, 0, 0.005, 0.01]
        
        sensitivity_grid = []
        
        for wacc_delta in wacc_range:
            row = []
            for tg_delta in terminal_growth_range:
                # Adjust inputs - create a proper copy with modified values
                adjusted_inputs = replace(
                    base_inputs,
                    risk_free_rate=base_inputs.risk_free_rate + wacc_delta,
                    terminal_growth_rate=base_inputs.terminal_growth_rate + tg_delta
                )
                
                try:
                    result = await self._calculate_dcf(company_data, adjusted_inputs)
                    row.append(round(result.intrinsic_value_per_share, 2))
                except Exception:
                    row.append(None)
            
            sensitivity_grid.append(row)
        
        return {
            "wacc_range": [f"{w:+.1%}" for w in wacc_range],
            "terminal_growth_range": [f"{tg:+.1%}" for tg in terminal_growth_range],
            "sensitivity_grid": sensitivity_grid
        }
    
    def _calculate_trade_rules(
        self, 
        dcf_result: DCFOutputs, 
        current_price: Optional[float]
    ) -> Dict[str, Any]:
        """Calculate trading rules and margin of safety"""
        
        intrinsic_value = dcf_result.intrinsic_value_per_share
        
        # Define trading zones
        conservative_mos = 0.25  # 25% margin of safety for buy
        target_premium = 0.20    # 20% premium for target
        stop_loss_threshold = 0.15  # 15% stop loss
        
        buy_zone = intrinsic_value * (1 - conservative_mos)
        target_price = intrinsic_value * (1 + target_premium)
        
        if current_price:
            margin_of_safety = (intrinsic_value - current_price) / intrinsic_value
            upside_potential = (intrinsic_value - current_price) / current_price
            stop_loss = current_price * (1 - stop_loss_threshold)
            
            # Generate recommendation
            if current_price <= buy_zone:
                recommendation = "Strong Buy"
            elif current_price <= intrinsic_value:
                recommendation = "Buy"
            elif current_price <= intrinsic_value * 1.1:
                recommendation = "Hold"
            elif current_price <= intrinsic_value * 1.2:
                recommendation = "Weak Hold"
            else:
                recommendation = "Sell"
        else:
            margin_of_safety = 0
            upside_potential = 0
            stop_loss = buy_zone * (1 - stop_loss_threshold)
            recommendation = "Insufficient Data"
        
        return {
            "margin_of_safety": margin_of_safety,
            "upside_potential": upside_potential,
            "recommendation": recommendation,
            "buy_zone": buy_zone,
            "target_price": target_price,
            "stop_loss": stop_loss
        }


# Convenience function for integration
async def perform_dcf_valuation(ticker: str, current_price: Optional[float] = None) -> Dict[str, Any]:
    """Perform comprehensive DCF valuation"""
    engine = DCFValuationEngine()
    return await engine.value_company(ticker, current_price=current_price)





