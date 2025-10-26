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
from app.utils.rate_limiter import get_yahoo_client

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
    
    # Terminal value methods
    terminal_value_method: str = "gordon_growth"  # "gordon_growth", "exit_multiple", "perpetuity_growth"
    terminal_ebitda_multiple: float = 12.0  # Exit multiple for terminal value
    terminal_fcf_multiple: float = 15.0  # FCF multiple for terminal value


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
    
    def _validate_dcf_applicability(self, company_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate if DCF is applicable for this company
        
        Returns validation result with applicability flag and alternate methods
        """
        try:
            logger.info(f"🔍 DCF: Starting _validate_dcf_applicability")
            info = company_data["info"]
            logger.info(f"🔍 DCF: Company info keys: {list(info.keys())}")
            
            # Extract key financial metrics
            ebitda = info.get("ebitda")
            net_income = info.get("netIncome") or info.get("netIncomeCommonStockholders") or info.get("netIncomeToCommon")
            free_cash_flow = info.get("freeCashflow")
            operating_cash_flow = info.get("operatingCashflow") or info.get("totalCashFromOperatingActivities")
            revenue = info.get("totalRevenue") or info.get("revenue")
            current_price = info.get("currentPrice") or info.get("regularMarketPrice")
            market_cap = info.get("marketCap")
            
            # Calculate revenue growth if available
            revenue_growth = info.get("revenueGrowth")
            if revenue_growth is None and revenue and market_cap:
                # Estimate revenue growth from P/S ratio trends (simplified)
                ps_ratio = info.get("priceToSalesTrailing12Months", 0)
                if ps_ratio > 0:
                    revenue_growth = 0.15  # Default 15% for growth companies
            
            # Calculate P/S ratio
            price_to_sales = None
            if revenue and current_price and market_cap:
                shares_outstanding = market_cap / current_price if current_price > 0 else None
                if shares_outstanding:
                    price_to_sales = market_cap / revenue
            
            # Improved DCF Applicability Logic - Multi-factor validation
            reason_parts = []
            
            # Calculate FCF margin if data is available
            fcf_margin = 0
            if (free_cash_flow is not None and revenue is not None and 
                free_cash_flow > 0 and revenue > 0):
                fcf_margin = free_cash_flow / revenue
            
            # Handle missing data case
            if (free_cash_flow is None and operating_cash_flow is None and 
                ebitda is None and net_income is None):
                reason_parts.append("insufficient financial data")
                dcf_applicable = False
            else:
                # Multi-factor DCF applicability check
                net_income_val = net_income if net_income is not None else 0
                operating_cf_val = operating_cash_flow if operating_cash_flow is not None else 0
                
                # Only exclude DCF when both Operating Cash Flow and Net Income are negative
                if net_income_val < 0 and operating_cf_val < 0:
                    dcf_applicable = False
                    reason_parts.append("negative net income and operating cash flow")
                # Or if FCF margin is very low AND net income is negative
                elif fcf_margin < 0.005 and net_income_val < 0:  # 0.5% threshold
                    dcf_applicable = False
                    reason_parts.append(f"very low free cash flow margin ({fcf_margin:.1%}) with negative net income")
                else:
                    dcf_applicable = True
                
                # Log the DCF applicability decision
                logger.info(f"DCF Applicability Check → Net Income: {net_income_val}, OCF: {operating_cf_val}, FCF Margin: {fcf_margin:.1%}, Applicable: {dcf_applicable}")
            
            if not dcf_applicable:
                reason = f"DCF model not applicable ({', '.join(reason_parts)})"
                valuation_method = "Revenue multiples or growth-based metrics suggested"
                
                suggested_metrics = {
                    "revenue": revenue,
                    "revenue_growth_yoy": revenue_growth,
                    "price_to_sales_ratio": price_to_sales,
                    "market_cap": market_cap,
                    "current_price": current_price,
                    "ebitda": ebitda,
                    "net_income": net_income,
                    "operating_cash_flow": operating_cash_flow
                }
                
                return {
                    "dcf_applicable": False,
                    "reason": reason,
                    "valuation_method": valuation_method,
                    "suggested_metrics": suggested_metrics
                }
            else:
                return {
                    "dcf_applicable": True,
                    "reason": "Company has positive cash flows and earnings",
                    "valuation_method": "DCF model applicable",
                    "suggested_metrics": {}
                }
                
        except Exception as e:
            logger.error(f"Error validating DCF applicability: {e}")
            return {
                "dcf_applicable": False,
                "reason": f"Validation error: {str(e)}",
                "valuation_method": "Revenue multiples or growth-based metrics suggested",
                "suggested_metrics": {}
            }
        
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
            
            # Validate if DCF is applicable for this company
            logger.info(f"🔍 DCF: Starting validation for {ticker}")
            dcf_validation = self._validate_dcf_applicability(company_data)
            logger.info(f"🔍 DCF: Validation result for {ticker}: {dcf_validation}")
            if not dcf_validation["dcf_applicable"]:
                logger.warning(f"🚫 DCF skipped for loss-making company: {ticker}")
                return {
                    "ticker": ticker,
                    "dcf_applicable": False,
                    "reason": dcf_validation["reason"],
                    "valuation_method": dcf_validation["valuation_method"],
                    "suggested_metrics": dcf_validation["suggested_metrics"],
                    "current_price": current_price,
                    "warning": "⚠️ DCF analysis is unreliable for loss-making companies — using revenue-based valuation instead."
                }
            
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
            
            # Check if DCF calculation produced negative results
            if weighted_result is None:
                logger.warning(f"🚫 DCF calculation failed due to negative results for {ticker}")
                return {
                    "ticker": ticker,
                    "dcf_applicable": False,
                    "reason": "DCF calculation produced negative values - model not reliable for this company",
                    "valuation_method": "Revenue multiples or growth-based metrics suggested",
                    "suggested_metrics": {
                        "revenue": company_data["info"].get("totalRevenue"),
                        "market_cap": company_data["info"].get("marketCap"),
                        "current_price": current_price
                    },
                    "current_price": current_price,
                    "warning": "⚠️ DCF analysis produced negative values — using revenue-based valuation instead."
                }
            
            # Generate sensitivity analysis
            sensitivity = await self._sensitivity_analysis(company_data, scenarios[0].inputs)
            
            # Run sanity check on weighted result
            info = company_data.get("info", {})
            current_price = info.get("currentPrice") or info.get("regularMarketPrice") or current_price or 0
            sanity_result = self._sanity_check_dcf_result(weighted_result, current_price, info)
            
            # Calculate margin of safety and trade rules
            trade_rules = self._calculate_trade_rules(weighted_result, current_price)
            
            return {
                "ticker": ticker,
                "dcf_applicable": True,
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
                "sanity_check": sanity_result,  # Add sanity check results
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
        """Fetch comprehensive company data for DCF with rate limiting"""
        try:
            logger.info(f"DCF: Fetching company data for {ticker}")
            
            # Use rate-limited Yahoo Finance client
            yahoo_client = get_yahoo_client()
            
            # Fetch info data
            info = await yahoo_client.get_info(ticker)
            
            # Fetch financial data in parallel with controlled concurrency
            async def fetch_financials():
                loop = asyncio.get_event_loop()
                t = await loop.run_in_executor(None, lambda: yf.Ticker(ticker))
                return {
                    "financials": await loop.run_in_executor(None, lambda: t.financials),
                    "balance_sheet": await loop.run_in_executor(None, lambda: t.balance_sheet),
                    "cashflow": await loop.run_in_executor(None, lambda: t.cashflow)
                }
            
            # Use rate limiting for financial data fetching
            await yahoo_client.client.rate_limiter.acquire()
            try:
                financial_data = await fetch_financials()
            finally:
                yahoo_client.client.rate_limiter.release()
            
            data = {
                "info": info,
                **financial_data
            }
            
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
            
            # Extract actual Free Cash Flow from cashflow DataFrame
            actual_fcf = self._extract_free_cash_flow(financial_data.get("cashflow"))
            if actual_fcf is not None:
                logger.info(f"DCF: Found actual Free Cash Flow data for {ticker}: {actual_fcf}")
                # Add to info for use in scenarios
                info["freeCashflow"] = actual_fcf
            elif not info.get("freeCashflow"):
                logger.warning(f"DCF: Missing free cash flow data for {ticker} - will estimate from other metrics")
                
            logger.info(f"DCF: Successfully fetched company data for {ticker}")
            return data
            
        except Exception as e:
            logger.error(f"DCF: Failed to fetch company data for {ticker}: {e}")
            return None
    
    def _extract_free_cash_flow(self, cashflow_df: Optional[pd.DataFrame]) -> Optional[float]:
        """
        Extract the most recent Free Cash Flow from the cashflow DataFrame
        
        Args:
            cashflow_df: Pandas DataFrame with cashflow data
            
        Returns:
            Most recent Free Cash Flow value or None if not found
        """
        if cashflow_df is None or cashflow_df.empty:
            return None
        
        try:
            # Look for Free Cash Flow in the DataFrame
            fcf_row = None
            for idx in cashflow_df.index:
                if 'Free Cash Flow' in str(idx):
                    fcf_row = cashflow_df.loc[idx]
                    break
            
            if fcf_row is not None:
                # Get the most recent positive value (prefer positive FCF for DCF)
                fcf_values = []
                for col in cashflow_df.columns:
                    value = fcf_row[col]
                    if pd.notna(value) and value != 0:
                        fcf_values.append((col, float(value)))
                        logger.debug(f"DCF: Found FCF {value:,.0f} for year {col}")
                
                if fcf_values:
                    # Prefer positive FCF values, then most recent
                    positive_fcf = [(col, val) for col, val in fcf_values if val > 0]
                    if positive_fcf:
                        # Use the most recent positive FCF
                        logger.info(f"DCF: Using positive FCF {positive_fcf[0][1]:,.0f} from {positive_fcf[0][0]}")
                        return positive_fcf[0][1]
                    else:
                        # If no positive FCF, use the most recent
                        logger.warning(f"DCF: No positive FCF found, using most recent {fcf_values[0][1]:,.0f}")
                        return fcf_values[0][1]
            
            logger.debug("DCF: No Free Cash Flow found in cashflow DataFrame")
            return None
            
        except Exception as e:
            logger.error(f"DCF: Error extracting Free Cash Flow: {e}")
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
        
        # For Indian stocks, use more conservative assumptions to match Screener.in methodology
        if ticker.endswith('.NS') or ticker.endswith('.BO'):
            # Use more conservative terminal growth for Indian stocks
            terminal_growth = min(terminal_growth, 0.02)  # Cap at 2%
            logger.info(f"DCF: Using conservative terminal growth for Indian stock: {terminal_growth:.2%}")
        
        logger.info(f"DCF scenario generation for {ticker}: "
                   f"country_rfr={risk_free_rate:.2%}, "
                   f"sector={sector}, "
                   f"terminal_growth={terminal_growth:.2%}")
        
        # Extract current metrics with defensive fallbacks
        current_revenue_growth = info.get("revenueGrowth") or 0.10
        if current_revenue_growth is None or current_revenue_growth <= 0:
            current_revenue_growth = 0.10  # 10% default
        
        # Use EBITDA margin, not operating margin
        ebitda_raw = info.get("ebitda")
        revenue_raw = info.get("totalRevenue") or info.get("revenue")
        if ebitda_raw and revenue_raw and revenue_raw > 0:
            current_ebitda_margin = ebitda_raw / revenue_raw
            logger.info(f"DCF: Calculated EBITDA margin from data: {current_ebitda_margin:.2%}")
        else:
            current_ebitda_margin = info.get("operatingMargins") or 0.10
            logger.warning(f"DCF: Using operating margin as EBITDA proxy: {current_ebitda_margin:.2%}")
        
        if current_ebitda_margin is None or current_ebitda_margin <= 0:
            current_ebitda_margin = 0.10  # 10% default
        
        current_beta = info.get("beta") or 1.0
        if current_beta is None or current_beta <= 0:
            current_beta = 1.0  # Market beta
        
        # Calculate actual CapEx and Depreciation as % of revenue
        ocf_raw = info.get("operatingCashflow")
        fcf_raw = info.get("freeCashflow")
        capex_raw = info.get("capitalExpenditures")
        
        actual_capex_ratio = 0.04  # Default 4%
        actual_depreciation_ratio = 0.03  # Default 3%
        
        if revenue_raw and ocf_raw and fcf_raw:
            # CapEx = OCF - FCF (since FCF = OCF - CapEx)
            calculated_capex = ocf_raw - fcf_raw
            actual_capex_ratio = abs(calculated_capex) / revenue_raw
            logger.info(f"DCF: Calculated actual CapEx ratio: {actual_capex_ratio:.2%}")
            
            # Estimate depreciation (typically 60-80% of CapEx)
            actual_depreciation_ratio = actual_capex_ratio * 0.7
            logger.info(f"DCF: Estimated depreciation ratio: {actual_depreciation_ratio:.2%}")
        
        if capex_raw and revenue_raw:
            capex_abs = abs(capex_raw)
            actual_capex_ratio = capex_abs / revenue_raw
            logger.info(f"DCF: Using Yahoo Finance CapEx ratio: {actual_capex_ratio:.2%}")
        
        debt_to_equity_raw = info.get("debtToEquity") or 50
        if debt_to_equity_raw is None or debt_to_equity_raw < 0:
            debt_to_equity_raw = 50
        current_debt_equity = debt_to_equity_raw / 100
        
        # Get market cap for scenario generation
        market_cap = info.get("marketCap") or 0
        
        # Base scenario with intelligent defaults
        # Use more realistic growth assumptions based on company size and sector
        # Large mature companies: maintain growth near their historical average
        sector = info.get("sector", "").lower()
        is_large_mature = market_cap and market_cap > 100e9  # > $100B market cap
        
        # Adjust growth assumptions to be more realistic
        growth_multipliers = [
            1.0,   # Year 1: full growth
            0.95,  # Year 2: slight moderation
            0.95,  # Year 3: slight moderation  
            0.85,  # Year 4-5: maturing
            0.85,  # Year 4-5: maturing
            0.75,  # Year 6-7: stable growth
            0.75,  # Year 6-7: stable growth
            0.70,  # Year 8-9: mature
            0.70,  # Year 8-9: mature
            0.60   # Year 10: terminal growth
        ]
        
        base_inputs = DCFInputs(
            revenue_growth_rates=[
                current_revenue_growth * mult for mult in growth_multipliers
            ],
            ebitda_margins=[current_ebitda_margin] * 10,  # Stable margins
            terminal_growth_rate=terminal_growth,  # Sector-specific
            risk_free_rate=risk_free_rate,  # Country-specific
            market_risk_premium=market_risk_premium,  # Country-specific
            beta=current_beta,
            debt_to_equity=current_debt_equity,
            capex_pct_revenue=actual_capex_ratio,  # Use calculated CapEx ratio
            depreciation_pct_revenue=actual_depreciation_ratio  # Use calculated depreciation ratio
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
            capex_pct_revenue=actual_capex_ratio * 1.1,  # Higher investment but based on actual ratio
            depreciation_pct_revenue=actual_depreciation_ratio * 1.1,  # Proportional to CapEx
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
            capex_pct_revenue=actual_capex_ratio * 0.8,  # Lower investment but based on actual ratio
            depreciation_pct_revenue=actual_depreciation_ratio * 0.8,  # Proportional to CapEx
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
        ticker = info.get("symbol", "")
        
        # Get market cap early for later use
        market_cap = info.get("marketCap") or 0
        
        # Get current financials with multiple fallbacks
        current_revenue = info.get("totalRevenue") or info.get("revenue") or 0
        
        # If no revenue, try to estimate from market cap and multiples
        if not current_revenue or current_revenue <= 0:
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
        
        # Validate WACC is reasonable with smarter caps based on company characteristics
        # For large, stable companies like Walmart, use lower WACC
        sector = info.get("sector", "").lower()
        is_stable_defensive = any(term in sector for term in ["consumer", "defensive", "utilities", "energy"])
        
        wacc_min = 0.04 if is_stable_defensive else 0.05
        wacc_max = 0.15 if is_stable_defensive else 0.30
        
        if wacc < wacc_min:
            logger.warning(f"DCF: WACC too low ({wacc:.2%}), using {wacc_min:.0%} minimum")
            wacc = wacc_min
        elif wacc > wacc_max:
            logger.warning(f"DCF: WACC too high ({wacc:.2%}), capping at {wacc_max:.0%}")
            wacc = wacc_max
        
        # For Indian stocks, use more conservative WACC to match Screener.in methodology
        if ticker.endswith('.NS') or ticker.endswith('.BO'):
            # Increase WACC by 1-2% for Indian stocks to be more conservative
            original_wacc = wacc
            wacc = min(wacc + 0.015, 0.15)  # Add 1.5% but cap at 15%
            logger.info(f"DCF: Using conservative WACC for Indian stock: {original_wacc:.2%} -> {wacc:.2%}")
        
        # Critical: Ensure terminal growth < WACC (Gordon Growth Model requirement)
        if inputs.terminal_growth_rate >= wacc:
            logger.warning(f"DCF: Terminal growth ({inputs.terminal_growth_rate:.2%}) >= WACC ({wacc:.2%}), adjusting")
            inputs.terminal_growth_rate = wacc * 0.5  # Set to 50% of WACC
        
        # Project cash flows
        explicit_fcf = []
        
        # Get starting FCF from company data (preferred method for Walmart-like companies)
        starting_fcf = info.get("freeCashflow")
        ocf_raw = info.get("operatingCashflow")
        capex_raw = info.get("capitalExpenditures")
        
        if starting_fcf is None or starting_fcf <= 0:
            # Calculate FCF from OCF and CapEx
            if ocf_raw and capex_raw:
                # CapEx is typically negative in Yahoo Finance
                starting_fcf = ocf_raw + capex_raw
                logger.info(f"DCF: Calculated starting FCF from OCF and CapEx: ${starting_fcf:,.0f}")
            else:
                # Fallback: estimate from revenue and margins
                ebitda_start = current_revenue * inputs.ebitda_margins[0]
                depreciation_start = current_revenue * inputs.depreciation_pct_revenue
                capex_start = current_revenue * inputs.capex_pct_revenue
                starting_fcf = (ebitda_start - depreciation_start) * (1 - inputs.tax_rate) + depreciation_start - capex_start
                logger.info(f"DCF: Estimated starting FCF from revenue: ${starting_fcf:,.0f}")
        
        # Start with current year FCF and project forward
        projected_fcf = starting_fcf
        
        for i, growth_rate in enumerate(inputs.revenue_growth_rates):
            # Apply growth to FCF
            projected_fcf *= (1 + growth_rate)
            explicit_fcf.append(projected_fcf)
        
        # Track revenue for reference (not used in simplified model)
        projected_revenue = current_revenue
        for growth_rate in inputs.revenue_growth_rates:
            projected_revenue *= (1 + growth_rate)
            
        # Terminal Value - Multiple Methods
        terminal_value_methods = self._calculate_terminal_value_methods(explicit_fcf[-1], inputs, wacc)
        
        # Use the specified terminal value method
        terminal_value = terminal_value_methods[inputs.terminal_value_method]
        terminal_fcf = explicit_fcf[-1] * (1 + inputs.terminal_growth_rate)
        
        # Present Value calculations
        discount_factors = [(1 + wacc) ** -i for i in range(1, len(explicit_fcf) + 1)]
        pv_explicit_fcf = sum(fcf * df for fcf, df in zip(explicit_fcf, discount_factors))
        pv_terminal_value = terminal_value * discount_factors[-1]
        
        # Enterprise Value
        enterprise_value = pv_explicit_fcf + pv_terminal_value
        
        # Equity Value
        # Use enterprise value vs market cap if available, otherwise calculate
        enterprise_value_implied = info.get("enterpriseValue")
        if enterprise_value_implied and market_cap and market_cap > 0:
            net_debt = enterprise_value_implied - market_cap
        else:
            net_debt = (info.get("totalDebt", 0) or 0) - (info.get("totalCash", 0) or 0)
        
        equity_value = enterprise_value - net_debt
        
        # Per-share value with fallbacks
        shares_outstanding = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding") or 0
        
        # If no shares data, try to estimate from market cap and price
        if not shares_outstanding or shares_outstanding <= 0:
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
        
        # Create DCF outputs
        dcf_output = DCFOutputs(
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
        
        # Run sanity check on the result
        current_price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        sanity_result = self._sanity_check_dcf_result(dcf_output, current_price, info)
        
        # Log warnings if any
        if sanity_result["warnings"]:
            for warning in sanity_result["warnings"]:
                logger.warning(f"DCF Sanity Check: {warning}")
        
        return dcf_output
    
    def _sanity_check_dcf_result(
        self, 
        result: DCFOutputs, 
        current_price: float, 
        info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Sanity check DCF result for reasonable ranges
        
        Returns:
            Dict with 'is_reasonable', 'warnings', and 'confidence' keys
        """
        warnings = []
        
        # Check 1: Intrinsic value vs current price
        if current_price and current_price > 0:
            ratio = result.intrinsic_value_per_share / current_price
            
            if ratio < 0.3:
                warnings.append(f"Intrinsic value ratio: {ratio:.2f}x (very undervalued - value trap concern)")
            elif ratio > 3.0:
                warnings.append(f"Intrinsic value ratio: {ratio:.2f}x (very overvalued - check model assumptions)")
        
        # Check 2: Negative values
        if result.equity_value < 0:
            warnings.append(f"Negative equity value: ${result.equity_value:,.0f}")
        
        if result.intrinsic_value_per_share < 0:
            warnings.append(f"Negative intrinsic value per share: ${result.intrinsic_value_per_share:.2f}")
        
        # Check 3: WACC in reasonable range
        if result.wacc < 0.04:
            warnings.append(f"Very low WACC: {result.wacc:.2%} (expected 4-15%)")
        elif result.wacc > 0.15:
            warnings.append(f"Very high WACC: {result.wacc:.2%} (expected 4-15%)")
        
        # Check 4: Terminal value proportion
        total_value = result.pv_explicit_period + result.pv_terminal_value
        if total_value > 0:
            terminal_pct = result.pv_terminal_value / total_value
            
            if terminal_pct < 0.3:
                warnings.append(f"Terminal value only {terminal_pct:.1%} of total (explicit period dominates)")
            elif terminal_pct > 0.9:
                warnings.append(f"Terminal value is {terminal_pct:.1%} of total (terminal assumptions dominate)")
        
        # Check 5: Unusual net debt
        if result.net_debt < -1e9:  # More than -$1B cash
            warnings.append(f"Very high cash position: ${-result.net_debt/1e9:.1f}B (may indicate mismanagement)")
        
        return {
            "is_reasonable": len(warnings) == 0,
            "warnings": warnings,
            "confidence": "high" if len(warnings) == 0 else "moderate" if len(warnings) <= 2 else "low"
        }
    
    def _calculate_terminal_value_methods(
        self, 
        final_fcf: float, 
        inputs: DCFInputs, 
        wacc: float
    ) -> Dict[str, float]:
        """Calculate terminal value using multiple methods"""
        methods = {}
        
        # Gordon Growth Model
        if wacc > inputs.terminal_growth_rate:
            # Terminal Value = FCF * (1 + g) / (r - g)
            # where g is terminal growth rate and r is WACC
            methods["gordon_growth"] = (final_fcf * (1 + inputs.terminal_growth_rate)) / (wacc - inputs.terminal_growth_rate)
        else:
            methods["gordon_growth"] = final_fcf * 20  # Fallback multiple
        
        # Exit Multiple Method (FCF)
        methods["exit_multiple"] = final_fcf * inputs.terminal_fcf_multiple
        
        # Perpetuity Growth Method (FCF at terminal year growth)
        if wacc > inputs.terminal_growth_rate:
            methods["perpetuity_growth"] = (final_fcf * (1 + inputs.terminal_growth_rate)) / (wacc - inputs.terminal_growth_rate)
        else:
            methods["perpetuity_growth"] = final_fcf * 20  # Fallback
        
        return methods
    
    def _calculate_dcf_sensitivity(
        self,
        base_fcf: float,
        inputs: DCFInputs,
        wacc_base: float,
        terminal_growth_base: float
    ) -> Dict[str, Any]:
        """
        Calculate sensitivity analysis for key DCF inputs
        
        Tests sensitivity to:
        - WACC changes (±1%)
        - Terminal growth (±0.5%)
        - Revenue growth (±25%)
        
        Returns dictionary with sensitivity data
        """
        sensitivities = {}
        
        # WACC sensitivity (±1%)
        for wacc_delta in [-0.01, 0, 0.01]:
            wacc = max(0.04, min(0.25, wacc_base + wacc_delta))  # Keep in reasonable range
            sensitivity_key = f"wacc_{wacc_delta:+.0%}".replace("+", "plus").replace("-", "minus")
            
            try:
                # Recalculate DCF with modified WACC
                terminal_methods = self._calculate_terminal_value_methods(base_fcf, inputs, wacc)
                terminal_value = terminal_methods.get(inputs.terminal_value_method, base_fcf * 15)
                
                # Simplified PV calculation for sensitivity
                discount_factors = [(1 + wacc) ** -i for i in range(1, 11)]
                pv_explicit = sum(base_fcf * df for df in discount_factors)
                pv_terminal = terminal_value * discount_factors[-1]
                
                sensitivities[sensitivity_key] = {
                    "wacc": wacc,
                    "terminal_value_pv": pv_terminal,
                    "enterprise_value": pv_explicit + pv_terminal
                }
            except Exception as e:
                logger.warning(f"Sensitivity calculation failed for WACC {wacc:.2%}: {e}")
        
        # Terminal growth sensitivity (±0.5%)
        for tg_delta in [-0.005, 0, 0.005]:
            tg = max(0.01, min(0.10, terminal_growth_base + tg_delta))  # Keep in reasonable range
            sensitivity_key = f"terminal_growth_{tg_delta:+.1%}".replace("+", "plus").replace("-", "minus").replace("%", "pct")
            
            try:
                # Create modified inputs with new terminal growth
                modified_inputs = replace(inputs, terminal_growth_rate=tg)
                
                terminal_methods = self._calculate_terminal_value_methods(base_fcf, modified_inputs, wacc_base)
                terminal_value = terminal_methods.get(inputs.terminal_value_method, base_fcf * 15)
                
                discount_factors = [(1 + wacc_base) ** -i for i in range(1, 11)]
                pv_terminal = terminal_value * discount_factors[-1]
                
                sensitivities[sensitivity_key] = {
                    "terminal_growth": tg,
                    "terminal_value_pv": pv_terminal
                }
            except Exception as e:
                logger.warning(f"Sensitivity calculation failed for terminal growth {tg:.2%}: {e}")
        
        return sensitivities
    
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
        
        # Check for negative DCF results - indicates unreliable calculation
        if (weighted_enterprise_value <= 0 or weighted_equity_value <= 0 or 
            weighted_intrinsic_value <= 0):
            logger.warning(f"🚫 Negative DCF results detected - DCF calculation unreliable")
            # Return a flag indicating DCF is not applicable due to calculation issues
            return None
        
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
        """Generate comprehensive sensitivity analysis"""
        
        # WACC sensitivity (±300bps)
        wacc_range = [-0.03, -0.02, -0.01, 0, 0.01, 0.02, 0.03]
        
        # Terminal growth sensitivity (±150bps)
        terminal_growth_range = [-0.015, -0.01, -0.005, 0, 0.005, 0.01, 0.015]
        
        # Revenue growth sensitivity (±50%)
        revenue_growth_range = [0.5, 0.75, 1.0, 1.25, 1.5]
        
        sensitivity_results = {}
        
        # WACC vs Terminal Growth sensitivity
        wacc_tg_grid = []
        for wacc_delta in wacc_range:
            row = []
            for tg_delta in terminal_growth_range:
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
            
            wacc_tg_grid.append(row)
        
        # Revenue growth sensitivity
        revenue_growth_sensitivity = []
        for growth_multiplier in revenue_growth_range:
            adjusted_inputs = replace(
                base_inputs,
                revenue_growth_rates=[g * growth_multiplier for g in base_inputs.revenue_growth_rates]
            )
            
            try:
                result = await self._calculate_dcf(company_data, adjusted_inputs)
                revenue_growth_sensitivity.append({
                    "multiplier": growth_multiplier,
                    "intrinsic_value": round(result.intrinsic_value_per_share, 2)
                })
            except Exception:
                revenue_growth_sensitivity.append({
                    "multiplier": growth_multiplier,
                    "intrinsic_value": None
                })
        
        # Terminal value method comparison
        terminal_value_comparison = {}
        for method in ["gordon_growth", "exit_multiple", "perpetuity_growth"]:
            adjusted_inputs = replace(base_inputs, terminal_value_method=method)
            try:
                result = await self._calculate_dcf(company_data, adjusted_inputs)
                terminal_value_comparison[method] = round(result.intrinsic_value_per_share, 2)
            except Exception:
                terminal_value_comparison[method] = None
        
        return {
            "wacc_range": [f"{w:+.1%}" for w in wacc_range],
            "terminal_growth_range": [f"{tg:+.1%}" for tg in terminal_growth_range],
            "wacc_terminal_growth_grid": wacc_tg_grid,
            "revenue_growth_sensitivity": revenue_growth_sensitivity,
            "terminal_value_methods": terminal_value_comparison,
            "sensitivity_summary": {
                "wacc_impact": "High - 1% change in WACC typically impacts value by 10-15%",
                "terminal_growth_impact": "Very High - 0.5% change in terminal growth impacts value by 15-25%",
                "revenue_growth_impact": "Moderate - 25% change in growth rates impacts value by 5-10%",
                "terminal_method_impact": "Moderate - Different methods can vary by 5-15%"
            }
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





