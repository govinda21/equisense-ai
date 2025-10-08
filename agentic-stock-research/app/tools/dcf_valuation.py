"""
Comprehensive DCF Valuation Engine
Implements FCFF and FCFE models with scenario analysis and sensitivity testing
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import yfinance as yf

from app.utils.validation import DataValidator

logger = logging.getLogger(__name__)


@dataclass
class DCFInputs:
    """DCF model inputs"""
    # Revenue projections
    revenue_growth_rates: List[float]  # 5-10 year growth rates
    terminal_growth_rate: float  # Long-term growth rate (2-4%)
    
    # Profitability
    ebitda_margins: List[float]  # EBITDA margin progression
    tax_rate: float  # Effective tax rate
    
    # Working capital & capex
    working_capital_pct_revenue: float  # WC as % of revenue
    capex_pct_revenue: float  # CapEx as % of revenue
    depreciation_pct_revenue: float  # D&A as % of revenue
    
    # Cost of capital
    risk_free_rate: float  # 10-year G-Sec yield
    market_risk_premium: float  # Equity risk premium
    beta: float  # Levered beta
    cost_of_debt: float  # Pre-tax cost of debt
    tax_rate_debt: float  # Tax rate for debt shield
    debt_to_equity: float  # Target D/E ratio
    
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
    """Comprehensive DCF valuation engine"""
    
    def __init__(self):
        self.default_projection_years = 10
        self.india_risk_free_rate = 0.07  # 7% - approximate 10-year G-Sec
        self.india_market_risk_premium = 0.06  # 6% - India ERP
        
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
            
            # Validate essential data
            if not data["info"].get("marketCap"):
                logger.warning(f"Missing market cap for {ticker}")
                return None
                
            return data
            
        except Exception as e:
            logger.error(f"Failed to fetch company data for {ticker}: {e}")
            return None
    
    async def _generate_default_scenarios(self, company_data: Dict[str, Any]) -> List[DCFScenario]:
        """Generate default bull/base/bear scenarios"""
        info = company_data["info"]
        
        # Extract current metrics
        current_revenue_growth = info.get("revenueGrowth", 0.1) or 0.1
        current_ebitda_margin = info.get("operatingMargins", 0.15) or 0.15
        current_beta = info.get("beta", 1.0) or 1.0
        current_debt_equity = (info.get("debtToEquity", 50) or 50) / 100
        
        # Base scenario
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
            terminal_growth_rate=0.03,  # 3% long-term growth
            ebitda_margins=[current_ebitda_margin] * 10,  # Stable margins
            tax_rate=0.25,  # India corporate tax rate
            working_capital_pct_revenue=0.05,
            capex_pct_revenue=0.04,
            depreciation_pct_revenue=0.03,
            risk_free_rate=self.india_risk_free_rate,
            market_risk_premium=self.india_market_risk_premium,
            beta=current_beta,
            cost_of_debt=0.09,  # Typical Indian corporate debt cost
            tax_rate_debt=0.25,
            debt_to_equity=current_debt_equity
        )
        
        # Bull scenario - higher growth and margins
        bull_inputs = DCFInputs(
            revenue_growth_rates=[g * 1.5 for g in base_inputs.revenue_growth_rates],
            terminal_growth_rate=0.04,  # Higher terminal growth
            ebitda_margins=[min(m * 1.2, 0.4) for m in base_inputs.ebitda_margins],  # Cap at 40%
            tax_rate=0.25,
            working_capital_pct_revenue=0.04,  # Better WC management
            capex_pct_revenue=0.05,  # Higher investment for growth
            depreciation_pct_revenue=0.03,
            risk_free_rate=self.india_risk_free_rate,
            market_risk_premium=self.india_market_risk_premium,
            beta=current_beta * 0.9,  # Lower risk perception
            cost_of_debt=0.08,
            tax_rate_debt=0.25,
            debt_to_equity=current_debt_equity * 0.8  # Lower leverage
        )
        
        # Bear scenario - lower growth and margins
        bear_inputs = DCFInputs(
            revenue_growth_rates=[max(g * 0.5, 0.02) for g in base_inputs.revenue_growth_rates],
            terminal_growth_rate=0.02,  # Lower terminal growth
            ebitda_margins=[m * 0.8 for m in base_inputs.ebitda_margins],
            tax_rate=0.30,  # Higher effective tax rate
            working_capital_pct_revenue=0.08,  # Worse WC management
            capex_pct_revenue=0.03,  # Lower investment
            depreciation_pct_revenue=0.04,
            risk_free_rate=self.india_risk_free_rate,
            market_risk_premium=self.india_market_risk_premium * 1.2,  # Higher risk premium
            beta=current_beta * 1.2,  # Higher risk
            cost_of_debt=0.11,
            tax_rate_debt=0.30,
            debt_to_equity=current_debt_equity * 1.2  # Higher leverage
        )
        
        return [
            DCFScenario("Bull", 0.25, bull_inputs),
            DCFScenario("Base", 0.50, base_inputs),
            DCFScenario("Bear", 0.25, bear_inputs)
        ]
    
    async def _calculate_dcf(self, company_data: Dict[str, Any], inputs: DCFInputs) -> DCFOutputs:
        """Calculate DCF valuation for given inputs"""
        info = company_data["info"]
        
        # Get current financials
        current_revenue = info.get("totalRevenue", 0)
        if not current_revenue:
            raise ValueError("Unable to determine current revenue")
        
        # Calculate WACC
        cost_of_equity = inputs.risk_free_rate + inputs.beta * inputs.market_risk_premium
        after_tax_cost_of_debt = inputs.cost_of_debt * (1 - inputs.tax_rate_debt)
        
        # Weight of equity and debt
        total_capital = 1 + inputs.debt_to_equity
        weight_equity = 1 / total_capital
        weight_debt = inputs.debt_to_equity / total_capital
        
        wacc = (cost_of_equity * weight_equity) + (after_tax_cost_of_debt * weight_debt)
        
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
        
        # Per-share value
        shares_outstanding = info.get("sharesOutstanding", info.get("impliedSharesOutstanding", 0))
        if not shares_outstanding:
            raise ValueError("Unable to determine shares outstanding")
        
        intrinsic_value_per_share = equity_value / shares_outstanding
        
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
                # Adjust inputs
                adjusted_inputs = DCFInputs(
                    **{k: v for k, v in base_inputs.__dict__.items() if k != "risk_free_rate" and k != "terminal_growth_rate"}
                )
                adjusted_inputs.risk_free_rate = base_inputs.risk_free_rate + wacc_delta
                adjusted_inputs.terminal_growth_rate = base_inputs.terminal_growth_rate + tg_delta
                
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





