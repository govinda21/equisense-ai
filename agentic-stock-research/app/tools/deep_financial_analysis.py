"""
Deep Financial Analysis Engine - Phase 2
Provides comprehensive 5-10 year financial analysis with margins, ratios, and CAGR calculations
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf

from app.utils.validation import DataValidator
from app.utils.rate_limiter import get_yahoo_client

logger = logging.getLogger(__name__)


class DeepFinancialAnalyzer:
    """
    Deep financial analysis engine for institutional-grade research
    
    Provides:
    - 5-10 year financial statement analysis
    - Margin analysis and trends
    - Key financial ratios and trends
    - CAGR calculations
    - Quality of earnings analysis
    - Balance sheet strength assessment
    """
    
    def __init__(self):
        self.validator = DataValidator()
        self.yahoo_client = get_yahoo_client()
    
    async def analyze_financial_history(
        self, 
        ticker: str, 
        years_back: int = 10
    ) -> Dict[str, Any]:
        """
        Perform comprehensive financial history analysis
        
        Args:
            ticker: Stock ticker symbol
            years_back: Number of years to analyze (default 10)
            
        Returns:
            Comprehensive financial analysis results
        """
        try:
            logger.info(f"Starting deep financial analysis for {ticker} ({years_back} years)")
            
            # Fetch financial data
            financial_data = await self._fetch_financial_statements(ticker, years_back)
            
            if not financial_data:
                logger.warning(f"No financial data available for {ticker}")
                return self._create_empty_analysis()
            
            # Perform comprehensive analysis
            analysis_results = await asyncio.gather(
                self._analyze_income_statement_trends(financial_data),
                self._analyze_balance_sheet_trends(financial_data),
                self._analyze_cash_flow_trends(financial_data),
                self._calculate_financial_ratios(financial_data),
                self._calculate_margins_and_efficiency(financial_data),
                self._calculate_growth_metrics(financial_data),
                self._assess_earnings_quality(financial_data),
                self._assess_balance_sheet_strength(financial_data),
                return_exceptions=True
            )
            
            # Compile results
            result = {
                "ticker": ticker,
                "analysis_period_years": years_back,
                "analysis_date": datetime.now().isoformat(),
                "income_statement_trends": analysis_results[0] if not isinstance(analysis_results[0], Exception) else {},
                "balance_sheet_trends": analysis_results[1] if not isinstance(analysis_results[1], Exception) else {},
                "cash_flow_trends": analysis_results[2] if not isinstance(analysis_results[2], Exception) else {},
                "financial_ratios": analysis_results[3] if not isinstance(analysis_results[3], Exception) else {},
                "margins_and_efficiency": analysis_results[4] if not isinstance(analysis_results[4], Exception) else {},
                "growth_metrics": analysis_results[5] if not isinstance(analysis_results[5], Exception) else {},
                "earnings_quality": analysis_results[6] if not isinstance(analysis_results[6], Exception) else {},
                "balance_sheet_strength": analysis_results[7] if not isinstance(analysis_results[7], Exception) else {},
                "summary": self._generate_financial_summary(analysis_results)
            }
            
            logger.info(f"Deep financial analysis completed for {ticker}")
            return result
            
        except Exception as e:
            logger.error(f"Error in deep financial analysis for {ticker}: {str(e)}")
            return self._create_empty_analysis()
    
    async def _fetch_financial_statements(
        self, 
        ticker: str, 
        years_back: int
    ) -> Optional[Dict[str, pd.DataFrame]]:
        """Fetch financial statements from Yahoo Finance"""
        try:
            t = yf.Ticker(ticker)
            
            # Fetch financial statements
            financials = t.financials
            balance_sheet = t.balance_sheet
            cashflow = t.cashflow
            
            # Validate data availability
            if financials.empty and balance_sheet.empty and cashflow.empty:
                logger.warning(f"No financial statements available for {ticker}")
                return None
            
            # Filter to requested years
            cutoff_date = datetime.now() - timedelta(days=years_back * 365)
            
            financial_data = {
                "income_statement": financials,
                "balance_sheet": balance_sheet,
                "cash_flow": cashflow,
                "quarters": t.quarterly_financials,
                "quarters_balance": t.quarterly_balance_sheet,
                "quarters_cashflow": t.quarterly_cashflow
            }
            
            logger.info(f"Fetched financial data for {ticker}: {len(financials.columns)} years")
            return financial_data
            
        except Exception as e:
            logger.error(f"Error fetching financial statements for {ticker}: {str(e)}")
            return None
    
    async def _analyze_income_statement_trends(
        self, 
        financial_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """Analyze income statement trends over time"""
        try:
            is_df = financial_data.get("income_statement")
            if is_df.empty:
                return {}
            
            # Key income statement metrics
            metrics = {
                "total_revenue": ["Total Revenue", "Operating Revenue"],
                "gross_profit": ["Gross Profit"],
                "operating_income": ["Operating Income", "EBIT"],
                "net_income": ["Net Income", "Net Income Common Stockholders"],
                "ebitda": ["EBITDA", "Normalized EBITDA"],
                "research_development": ["Research Development"],
                "selling_general_admin": ["Selling General And Administration"]
            }
            
            trends = {}
            for metric_name, possible_keys in metrics.items():
                values = self._extract_metric_values(is_df, possible_keys)
                if values:
                    trends[metric_name] = {
                        "values": values,
                        "latest": values[-1] if values else None,
                        "previous": values[-2] if len(values) > 1 else None,
                        "yoy_growth": self._calculate_yoy_growth(values),
                        "cagr_5y": self._calculate_cagr(values, min(5, len(values))),
                        "cagr_10y": self._calculate_cagr(values, min(10, len(values))),
                        "volatility": self._calculate_volatility(values)
                    }
            
            return trends
            
        except Exception as e:
            logger.error(f"Error analyzing income statement trends: {str(e)}")
            return {}
    
    async def _analyze_balance_sheet_trends(
        self, 
        financial_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """Analyze balance sheet trends over time"""
        try:
            bs_df = financial_data.get("balance_sheet")
            if bs_df.empty:
                return {}
            
            # Key balance sheet metrics
            metrics = {
                "total_assets": ["Total Assets"],
                "total_liabilities": ["Total Liabilities Net Minority Interest"],
                "total_equity": ["Stockholders Equity", "Common Stock Equity"],
                "cash_and_equivalents": ["Cash And Cash Equivalents", "Cash Financial"],
                "total_debt": ["Total Debt", "Long Term Debt"],
                "current_assets": ["Current Assets"],
                "current_liabilities": ["Current Liabilities"],
                "working_capital": ["Working Capital"],
                "retained_earnings": ["Retained Earnings"]
            }
            
            trends = {}
            for metric_name, possible_keys in metrics.items():
                values = self._extract_metric_values(bs_df, possible_keys)
                if values:
                    trends[metric_name] = {
                        "values": values,
                        "latest": values[-1] if values else None,
                        "previous": values[-2] if len(values) > 1 else None,
                        "yoy_growth": self._calculate_yoy_growth(values),
                        "cagr_5y": self._calculate_cagr(values, min(5, len(values))),
                        "cagr_10y": self._calculate_cagr(values, min(10, len(values))),
                        "volatility": self._calculate_volatility(values)
                    }
            
            return trends
            
        except Exception as e:
            logger.error(f"Error analyzing balance sheet trends: {str(e)}")
            return {}
    
    async def _analyze_cash_flow_trends(
        self, 
        financial_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """Analyze cash flow trends over time"""
        try:
            cf_df = financial_data.get("cash_flow")
            if cf_df.empty:
                return {}
            
            # Key cash flow metrics
            metrics = {
                "operating_cash_flow": ["Total Cash From Operating Activities", "Operating Cash Flow"],
                "investing_cash_flow": ["Total Cash From Investing Activities", "Investing Cash Flow"],
                "financing_cash_flow": ["Total Cash From Financing Activities", "Financing Cash Flow"],
                "free_cash_flow": ["Free Cash Flow"],
                "capital_expenditures": ["Capital Expenditures", "CapEx"],
                "dividends_paid": ["Dividends Paid"]
            }
            
            trends = {}
            for metric_name, possible_keys in metrics.items():
                values = self._extract_metric_values(cf_df, possible_keys)
                if values:
                    trends[metric_name] = {
                        "values": values,
                        "latest": values[-1] if values else None,
                        "previous": values[-2] if len(values) > 1 else None,
                        "yoy_growth": self._calculate_yoy_growth(values),
                        "cagr_5y": self._calculate_cagr(values, min(5, len(values))),
                        "cagr_10y": self._calculate_cagr(values, min(10, len(values))),
                        "volatility": self._calculate_volatility(values)
                    }
            
            return trends
            
        except Exception as e:
            logger.error(f"Error analyzing cash flow trends: {str(e)}")
            return {}
    
    async def _calculate_financial_ratios(
        self, 
        financial_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """Calculate key financial ratios and their trends"""
        try:
            is_df = financial_data.get("income_statement")
            bs_df = financial_data.get("balance_sheet")
            cf_df = financial_data.get("cash_flow")
            
            if is_df.empty or bs_df.empty:
                return {}
            
            ratios = {}
            
            # Profitability ratios
            ratios["roe"] = self._calculate_roe_trend(is_df, bs_df)
            ratios["roa"] = self._calculate_roa_trend(is_df, bs_df)
            ratios["roic"] = self._calculate_roic_trend(is_df, bs_df)
            ratios["gross_margin"] = self._calculate_gross_margin_trend(is_df)
            ratios["operating_margin"] = self._calculate_operating_margin_trend(is_df)
            ratios["net_margin"] = self._calculate_net_margin_trend(is_df)
            
            # Efficiency ratios
            ratios["asset_turnover"] = self._calculate_asset_turnover_trend(is_df, bs_df)
            ratios["inventory_turnover"] = self._calculate_inventory_turnover_trend(is_df, bs_df)
            ratios["receivables_turnover"] = self._calculate_receivables_turnover_trend(is_df, bs_df)
            
            # Leverage ratios
            ratios["debt_to_equity"] = self._calculate_debt_to_equity_trend(bs_df)
            ratios["debt_to_assets"] = self._calculate_debt_to_assets_trend(bs_df)
            ratios["interest_coverage"] = self._calculate_interest_coverage_trend(is_df)
            
            # Liquidity ratios
            ratios["current_ratio"] = self._calculate_current_ratio_trend(bs_df)
            ratios["quick_ratio"] = self._calculate_quick_ratio_trend(bs_df)
            ratios["cash_ratio"] = self._calculate_cash_ratio_trend(bs_df)
            
            # Cash flow ratios
            if not cf_df.empty:
                ratios["fcf_yield"] = self._calculate_fcf_yield_trend(cf_df, bs_df)
                ratios["fcf_margin"] = self._calculate_fcf_margin_trend(cf_df, is_df)
            
            return ratios
            
        except Exception as e:
            logger.error(f"Error calculating financial ratios: {str(e)}")
            return {}
    
    async def _calculate_margins_and_efficiency(
        self, 
        financial_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """Calculate detailed margin and efficiency analysis"""
        try:
            is_df = financial_data.get("income_statement")
            bs_df = financial_data.get("balance_sheet")
            
            if is_df.empty:
                return {}
            
            margins = {}
            
            # Revenue analysis
            revenue_values = self._extract_metric_values(is_df, ["Total Revenue", "Revenue"])
            if revenue_values:
                margins["revenue"] = {
                    "values": revenue_values,
                    "cagr_5y": self._calculate_cagr(revenue_values, min(5, len(revenue_values))),
                    "cagr_10y": self._calculate_cagr(revenue_values, min(10, len(revenue_values))),
                    "volatility": self._calculate_volatility(revenue_values)
                }
            
            # Margin analysis
            gross_profit = self._extract_metric_values(is_df, ["Gross Profit"])
            operating_income = self._extract_metric_values(is_df, ["Operating Income", "EBIT"])
            net_income = self._extract_metric_values(is_df, ["Net Income"])
            
            if revenue_values and gross_profit:
                gross_margin_values = [gp/rv if rv != 0 else 0 for gp, rv in zip(gross_profit, revenue_values)]
                margins["gross_margin"] = {
                    "values": gross_margin_values,
                    "latest": gross_margin_values[-1] if gross_margin_values else None,
                    "average": float(np.mean(gross_margin_values)) if gross_margin_values else None,
                    "trend": self._calculate_trend_direction(gross_margin_values)
                }
            
            if revenue_values and operating_income:
                operating_margin_values = [oi/rv if rv != 0 else 0 for oi, rv in zip(operating_income, revenue_values)]
                margins["operating_margin"] = {
                    "values": operating_margin_values,
                    "latest": operating_margin_values[-1] if operating_margin_values else None,
                    "average": float(np.mean(operating_margin_values)) if operating_margin_values else None,
                    "trend": self._calculate_trend_direction(operating_margin_values)
                }
            
            if revenue_values and net_income:
                net_margin_values = [ni/rv if rv != 0 else 0 for ni, rv in zip(net_income, revenue_values)]
                margins["net_margin"] = {
                    "values": net_margin_values,
                    "latest": net_margin_values[-1] if net_margin_values else None,
                    "average": float(np.mean(net_margin_values)) if net_margin_values else None,
                    "trend": self._calculate_trend_direction(net_margin_values)
                }
            
            return margins
            
        except Exception as e:
            logger.error(f"Error calculating margins and efficiency: {str(e)}")
            return {}
    
    async def _calculate_growth_metrics(
        self, 
        financial_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """Calculate comprehensive growth metrics"""
        try:
            is_df = financial_data.get("income_statement")
            bs_df = financial_data.get("balance_sheet")
            
            if is_df.empty:
                return {}
            
            growth_metrics = {}
            
            # Revenue growth
            revenue_values = self._extract_metric_values(is_df, ["Total Revenue", "Revenue"])
            if revenue_values and len(revenue_values) > 1:
                growth_metrics["revenue_growth"] = {
                    "yoy_growth": self._calculate_yoy_growth(revenue_values),
                    "cagr_3y": self._calculate_cagr(revenue_values, min(3, len(revenue_values))),
                    "cagr_5y": self._calculate_cagr(revenue_values, min(5, len(revenue_values))),
                    "cagr_10y": self._calculate_cagr(revenue_values, min(10, len(revenue_values))),
                    "volatility": self._calculate_volatility(revenue_values)
                }
            
            # Earnings growth
            net_income_values = self._extract_metric_values(is_df, ["Net Income"])
            if net_income_values and len(net_income_values) > 1:
                growth_metrics["earnings_growth"] = {
                    "yoy_growth": self._calculate_yoy_growth(net_income_values),
                    "cagr_3y": self._calculate_cagr(net_income_values, min(3, len(net_income_values))),
                    "cagr_5y": self._calculate_cagr(net_income_values, min(5, len(net_income_values))),
                    "cagr_10y": self._calculate_cagr(net_income_values, min(10, len(net_income_values))),
                    "volatility": self._calculate_volatility(net_income_values)
                }
            
            # Asset growth
            if not bs_df.empty:
                asset_values = self._extract_metric_values(bs_df, ["Total Assets"])
                if asset_values and len(asset_values) > 1:
                    growth_metrics["asset_growth"] = {
                        "yoy_growth": self._calculate_yoy_growth(asset_values),
                        "cagr_5y": self._calculate_cagr(asset_values, min(5, len(asset_values))),
                        "cagr_10y": self._calculate_cagr(asset_values, min(10, len(asset_values)))
                    }
            
            return growth_metrics
            
        except Exception as e:
            logger.error(f"Error calculating growth metrics: {str(e)}")
            return {}
    
    async def _assess_earnings_quality(
        self, 
        financial_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """Enhanced earnings quality and financial reporting forensics"""
        try:
            is_df = financial_data.get("income_statement")
            cf_df = financial_data.get("cash_flow")
            bs_df = financial_data.get("balance_sheet")
            
            if is_df.empty or cf_df.empty:
                return {}
            
            quality_metrics = {}
            
            # 1. Enhanced CFO vs Net Income Analysis
            net_income_values = self._extract_metric_values(is_df, ["Net Income", "Net Income Common Stockholders"])
            cfo_values = self._extract_metric_values(cf_df, ["Total Cash From Operating Activities", "Operating Cash Flow"])
            
            if net_income_values and cfo_values and len(net_income_values) >= 3:
                cfo_ni_ratios = []
                for i in range(min(len(net_income_values), len(cfo_values))):
                    if net_income_values[i] != 0:
                        ratio = cfo_values[i] / net_income_values[i]
                        cfo_ni_ratios.append(ratio)
                
                if cfo_ni_ratios:
                    quality_metrics["cfo_to_net_income"] = {
                        "latest_ratio": float(cfo_ni_ratios[-1]),
                        "average_ratio": float(np.mean(cfo_ni_ratios)),
                        "median_ratio": float(np.median(cfo_ni_ratios)),
                        "trend": self._calculate_trend_direction(cfo_ni_ratios),
                        "volatility": float(self._calculate_volatility(cfo_ni_ratios)),
                        "quality_score": self._assess_cfo_quality_score(cfo_ni_ratios),
                        "consistency_score": self._assess_cfo_consistency_score(cfo_ni_ratios)
                    }
            
            # 2. Accrual Quality Analysis
            accrual_quality = await self._analyze_accrual_quality(is_df, cf_df)
            if accrual_quality:
                quality_metrics["accrual_quality"] = accrual_quality
            
            # 3. Revenue Recognition Quality
            revenue_quality = await self._analyze_revenue_quality(is_df, cf_df)
            if revenue_quality:
                quality_metrics["revenue_quality"] = revenue_quality
            
            # 4. Non-Recurring Items Detection
            non_recurring = await self._detect_non_recurring_items(is_df)
            if non_recurring:
                quality_metrics["non_recurring_items"] = non_recurring
            
            # 5. Enhanced Working Capital Analysis
            if not bs_df.empty:
                working_capital_analysis = await self._analyze_working_capital_quality(bs_df, cf_df)
                if working_capital_analysis:
                    quality_metrics["working_capital"] = working_capital_analysis
            
            # 6. Cash Flow Quality Score
            cash_flow_quality = await self._calculate_cash_flow_quality_score(cf_df, is_df)
            if cash_flow_quality:
                quality_metrics["cash_flow_quality"] = cash_flow_quality
            
            # 7. Earnings Manipulation Indicators
            manipulation_indicators = await self._detect_earnings_manipulation_indicators(is_df, cf_df, bs_df)
            if manipulation_indicators:
                quality_metrics["manipulation_indicators"] = manipulation_indicators
            
            # 8. Overall Earnings Quality Score
            quality_metrics["overall_quality_score"] = self._calculate_overall_earnings_quality_score(quality_metrics)
            
            return quality_metrics
            
        except Exception as e:
            logger.error(f"Error assessing earnings quality: {str(e)}")
            return {}
    
    async def _assess_balance_sheet_strength(
        self, 
        financial_data: Dict[str, pd.DataFrame]
    ) -> Dict[str, Any]:
        """Enhanced balance sheet forensics and strength assessment"""
        try:
            bs_df = financial_data.get("balance_sheet")
            is_df = financial_data.get("income_statement")
            cf_df = financial_data.get("cash_flow")
            
            if bs_df.empty:
                return {}
            
            strength_metrics = {}
            
            # 1. Enhanced Debt Analysis
            debt_analysis = await self._analyze_debt_structure(bs_df, is_df)
            if debt_analysis:
                strength_metrics["debt_analysis"] = debt_analysis
            
            # 2. Interest Coverage Analysis
            interest_coverage = await self._analyze_interest_coverage(is_df, bs_df)
            if interest_coverage:
                strength_metrics["interest_coverage"] = interest_coverage
            
            # 3. Asset Quality Assessment
            asset_quality = await self._assess_asset_quality(bs_df, is_df)
            if asset_quality:
                strength_metrics["asset_quality"] = asset_quality
            
            # 4. Liquidity Analysis
            liquidity_analysis = await self._analyze_liquidity_strength(bs_df, cf_df)
            if liquidity_analysis:
                strength_metrics["liquidity"] = liquidity_analysis
            
            # 5. Cash Position Analysis
            cash_analysis = await self._analyze_cash_position(bs_df, is_df)
            if cash_analysis:
                strength_metrics["cash_position"] = cash_analysis
            
            # 6. Off-Balance Sheet Risk Assessment
            off_balance_sheet = await self._assess_off_balance_sheet_risks(bs_df, is_df)
            if off_balance_sheet:
                strength_metrics["off_balance_sheet"] = off_balance_sheet
            
            # 7. Financial Flexibility Score
            flexibility_score = await self._calculate_financial_flexibility_score(strength_metrics)
            if flexibility_score:
                strength_metrics["financial_flexibility"] = flexibility_score
            
            # 8. Overall Balance Sheet Strength Score
            strength_metrics["overall_strength_score"] = self._calculate_overall_balance_sheet_score(strength_metrics)
            
            return strength_metrics
            
        except Exception as e:
            logger.error(f"Error assessing balance sheet strength: {str(e)}")
            return {}
    
    def _extract_metric_values(
        self, 
        df: pd.DataFrame, 
        possible_keys: List[str]
    ) -> List[float]:
        """Extract values for a metric from DataFrame"""
        if df.empty:
            return []
        
        for key in possible_keys:
            if key in df.index:
                series = df.loc[key].dropna()
                if len(series) > 0:
                    try:
                        return [float(v) for v in series.tolist() if v is not None and not pd.isna(v)]
                    except Exception:
                        continue
        return []
    
    def _calculate_yoy_growth(self, values: List[float]) -> Optional[float]:
        """Calculate year-over-year growth rate"""
        if len(values) < 2:
            return None
        
        try:
            # values are in reverse chronological order (most recent first)
            # So the most recent is at index 0, previous year is at index 1
            current = values[0]  # Most recent year
            previous = values[1]  # Previous year
            
            if previous == 0:
                return None
            
            # Calculate YoY growth: (Current - Previous) / Previous
            return (current - previous) / previous
        except Exception:
            return None
    
    def _calculate_cagr(self, values: List[float], years: int) -> Optional[float]:
        """Calculate Compound Annual Growth Rate"""
        if len(values) < 2 or years < 2:
            return None
        
        try:
            # values are in reverse chronological order (most recent first)
            # So the most recent is at index 0, oldest is at the end
            end_value = values[0]      # Most recent value
            start_value = values[-1]  # Oldest value
            
            if start_value == 0 or start_value < 0:
                return None
            
            # Calculate CAGR: (End/Start)^(1/years) - 1
            return (end_value / start_value) ** (1 / (len(values) - 1)) - 1
        except Exception:
            return None
    
    def _calculate_volatility(self, values: List[float]) -> Optional[float]:
        """Calculate volatility (standard deviation) of values"""
        if len(values) < 2:
            return None
        
        try:
            return float(np.std(values))
        except Exception:
            return None
    
    def _calculate_trend_direction(self, values: List[float]) -> str:
        """Determine trend direction (increasing, decreasing, stable)"""
        if len(values) < 3:
            return "insufficient_data"
        
        try:
            # Calculate slope using linear regression
            x = list(range(len(values)))
            slope = float(np.polyfit(x, values, 1)[0])
            
            if slope > 0.05:  # 5% threshold
                return "increasing"
            elif slope < -0.05:
                return "decreasing"
            else:
                return "stable"
        except Exception:
            return "unknown"
    
    def _assess_cfo_quality_score(self, ratios: List[float]) -> str:
        """Assess CFO quality based on CFO/Net Income ratios"""
        if not ratios:
            return "unknown"
        
        avg_ratio = float(np.mean(ratios))
        latest_ratio = ratios[-1]
        
        if avg_ratio > 1.2 and latest_ratio > 1.0:
            return "excellent"
        elif avg_ratio > 1.0 and latest_ratio > 0.8:
            return "good"
        elif avg_ratio > 0.8 and latest_ratio > 0.6:
            return "fair"
        else:
            return "poor"
    
    def _assess_debt_strength_score(self, ratios: List[float]) -> str:
        """Assess debt strength based on debt-to-equity ratios"""
        if not ratios:
            return "unknown"
        
        avg_ratio = float(np.mean(ratios))
        latest_ratio = ratios[-1]
        
        if avg_ratio < 0.3 and latest_ratio < 0.4:
            return "excellent"
        elif avg_ratio < 0.5 and latest_ratio < 0.6:
            return "good"
        elif avg_ratio < 0.8 and latest_ratio < 1.0:
            return "fair"
        else:
            return "poor"
    
    def _assess_liquidity_strength_score(self, ratios: List[float]) -> str:
        """Assess liquidity strength based on current ratios"""
        if not ratios:
            return "unknown"
        
        avg_ratio = float(np.mean(ratios))
        latest_ratio = ratios[-1]
        
        if avg_ratio > 2.0 and latest_ratio > 1.5:
            return "excellent"
        elif avg_ratio > 1.5 and latest_ratio > 1.2:
            return "good"
        elif avg_ratio > 1.2 and latest_ratio > 1.0:
            return "fair"
        else:
            return "poor"
    
    # Ratio calculation methods
    def _calculate_roe_trend(self, is_df: pd.DataFrame, bs_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate ROE trend"""
        net_income = self._extract_metric_values(is_df, ["Net Income", "Net Income Common Stockholders"])
        equity = self._extract_metric_values(bs_df, ["Stockholders Equity", "Common Stock Equity"])
        
        if net_income and equity and len(net_income) >= 2:
            roe_values = [ni/eq if eq != 0 else 0 for ni, eq in zip(net_income, equity)]
            return {
                "values": roe_values,
                "latest": roe_values[-1] if roe_values else None,
                "average": float(np.mean(roe_values)) if roe_values else None,
                "trend": self._calculate_trend_direction(roe_values)
            }
        return {}
    
    def _calculate_roa_trend(self, is_df: pd.DataFrame, bs_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate ROA trend"""
        net_income = self._extract_metric_values(is_df, ["Net Income"])
        assets = self._extract_metric_values(bs_df, ["Total Assets"])
        
        if net_income and assets and len(net_income) >= 2:
            roa_values = [ni/ta if ta != 0 else 0 for ni, ta in zip(net_income, assets)]
            return {
                "values": roa_values,
                "latest": roa_values[-1] if roa_values else None,
                "average": float(np.mean(roa_values)) if roa_values else None,
                "trend": self._calculate_trend_direction(roa_values)
            }
        return {}
    
    def _calculate_roic_trend(self, is_df: pd.DataFrame, bs_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate ROIC trend"""
        operating_income = self._extract_metric_values(is_df, ["Operating Income", "EBIT"])
        total_assets = self._extract_metric_values(bs_df, ["Total Assets"])
        current_liabilities = self._extract_metric_values(bs_df, ["Current Liabilities"])
        
        if operating_income and total_assets and current_liabilities and len(operating_income) >= 2:
            invested_capital = [ta - cl for ta, cl in zip(total_assets, current_liabilities)]
            roic_values = [oi/ic if ic != 0 else 0 for oi, ic in zip(operating_income, invested_capital)]
            return {
                "values": roic_values,
                "latest": roic_values[-1] if roic_values else None,
                "average": float(np.mean(roic_values)) if roic_values else None,
                "trend": self._calculate_trend_direction(roic_values)
            }
        return {}
    
    def _calculate_gross_margin_trend(self, is_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate gross margin trend"""
        revenue = self._extract_metric_values(is_df, ["Total Revenue", "Revenue"])
        gross_profit = self._extract_metric_values(is_df, ["Gross Profit"])
        
        if revenue and gross_profit and len(revenue) >= 2:
            margin_values = [gp/rev if rev != 0 else 0 for gp, rev in zip(gross_profit, revenue)]
            return {
                "values": margin_values,
                "latest": margin_values[-1] if margin_values else None,
                "average": float(np.mean(margin_values)) if margin_values else None,
                "trend": self._calculate_trend_direction(margin_values)
            }
        return {}
    
    def _calculate_operating_margin_trend(self, is_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate operating margin trend"""
        revenue = self._extract_metric_values(is_df, ["Total Revenue", "Revenue"])
        operating_income = self._extract_metric_values(is_df, ["Operating Income", "EBIT"])
        
        if revenue and operating_income and len(revenue) >= 2:
            margin_values = [oi/rev if rev != 0 else 0 for oi, rev in zip(operating_income, revenue)]
            return {
                "values": margin_values,
                "latest": margin_values[-1] if margin_values else None,
                "average": float(np.mean(margin_values)) if margin_values else None,
                "trend": self._calculate_trend_direction(margin_values)
            }
        return {}
    
    def _calculate_net_margin_trend(self, is_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate net margin trend"""
        revenue = self._extract_metric_values(is_df, ["Total Revenue", "Revenue"])
        net_income = self._extract_metric_values(is_df, ["Net Income"])
        
        if revenue and net_income and len(revenue) >= 2:
            margin_values = [ni/rev if rev != 0 else 0 for ni, rev in zip(net_income, revenue)]
            return {
                "values": margin_values,
                "latest": margin_values[-1] if margin_values else None,
                "average": float(np.mean(margin_values)) if margin_values else None,
                "trend": self._calculate_trend_direction(margin_values)
            }
        return {}
    
    def _calculate_asset_turnover_trend(self, is_df: pd.DataFrame, bs_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate asset turnover trend"""
        revenue = self._extract_metric_values(is_df, ["Total Revenue", "Revenue"])
        assets = self._extract_metric_values(bs_df, ["Total Assets"])
        
        if revenue and assets and len(revenue) >= 2:
            turnover_values = [rev/ta if ta != 0 else 0 for rev, ta in zip(revenue, assets)]
            return {
                "values": turnover_values,
                "latest": turnover_values[-1] if turnover_values else None,
                "average": float(np.mean(turnover_values)) if turnover_values else None,
                "trend": self._calculate_trend_direction(turnover_values)
            }
        return {}
    
    def _calculate_inventory_turnover_trend(self, is_df: pd.DataFrame, bs_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate inventory turnover trend"""
        cogs = self._extract_metric_values(is_df, ["Cost Of Revenue", "Cost of Goods Sold"])
        inventory = self._extract_metric_values(bs_df, ["Inventory"])
        
        if cogs and inventory and len(cogs) >= 2:
            turnover_values = [cogs/inv if inv != 0 else 0 for cogs, inv in zip(cogs, inventory)]
            return {
                "values": turnover_values,
                "latest": turnover_values[-1] if turnover_values else None,
                "average": float(np.mean(turnover_values)) if turnover_values else None,
                "trend": self._calculate_trend_direction(turnover_values)
            }
        return {}
    
    def _calculate_receivables_turnover_trend(self, is_df: pd.DataFrame, bs_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate receivables turnover trend"""
        revenue = self._extract_metric_values(is_df, ["Total Revenue", "Revenue"])
        receivables = self._extract_metric_values(bs_df, ["Net Receivables", "Accounts Receivable"])
        
        if revenue and receivables and len(revenue) >= 2:
            turnover_values = [rev/rec if rec != 0 else 0 for rev, rec in zip(revenue, receivables)]
            return {
                "values": turnover_values,
                "latest": turnover_values[-1] if turnover_values else None,
                "average": float(np.mean(turnover_values)) if turnover_values else None,
                "trend": self._calculate_trend_direction(turnover_values)
            }
        return {}
    
    def _calculate_debt_to_equity_trend(self, bs_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate debt-to-equity trend"""
        debt = self._extract_metric_values(bs_df, ["Total Debt", "Long Term Debt"])
        equity = self._extract_metric_values(bs_df, ["Stockholders Equity", "Common Stock Equity"])
        
        if debt and equity and len(debt) >= 2:
            ratio_values = [d/e if e != 0 else 0 for d, e in zip(debt, equity)]
            return {
                "values": ratio_values,
                "latest": ratio_values[-1] if ratio_values else None,
                "average": float(np.mean(ratio_values)) if ratio_values else None,
                "trend": self._calculate_trend_direction(ratio_values)
            }
        return {}
    
    def _calculate_debt_to_assets_trend(self, bs_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate debt-to-assets trend"""
        debt = self._extract_metric_values(bs_df, ["Total Debt", "Long Term Debt"])
        assets = self._extract_metric_values(bs_df, ["Total Assets"])
        
        if debt and assets and len(debt) >= 2:
            ratio_values = [d/a if a != 0 else 0 for d, a in zip(debt, assets)]
            return {
                "values": ratio_values,
                "latest": ratio_values[-1] if ratio_values else None,
                "average": float(np.mean(ratio_values)) if ratio_values else None,
                "trend": self._calculate_trend_direction(ratio_values)
            }
        return {}
    
    def _calculate_interest_coverage_trend(self, is_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate interest coverage trend"""
        operating_income = self._extract_metric_values(is_df, ["Operating Income", "EBIT"])
        interest_expense = self._extract_metric_values(is_df, ["Interest Expense"])
        
        if operating_income and interest_expense and len(operating_income) >= 2:
            coverage_values = [oi/ie if ie != 0 else float('inf') for oi, ie in zip(operating_income, interest_expense)]
            return {
                "values": coverage_values,
                "latest": coverage_values[-1] if coverage_values else None,
                "average": float(np.mean([v for v in coverage_values if v != float('inf')])) if coverage_values else None,
                "trend": self._calculate_trend_direction([v for v in coverage_values if v != float('inf')])
            }
        return {}
    
    def _calculate_current_ratio_trend(self, bs_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate current ratio trend"""
        current_assets = self._extract_metric_values(bs_df, ["Current Assets"])
        current_liabilities = self._extract_metric_values(bs_df, ["Current Liabilities"])
        
        if current_assets and current_liabilities and len(current_assets) >= 2:
            ratio_values = [ca/cl if cl != 0 else 0 for ca, cl in zip(current_assets, current_liabilities)]
            return {
                "values": ratio_values,
                "latest": ratio_values[-1] if ratio_values else None,
                "average": float(np.mean(ratio_values)) if ratio_values else None,
                "trend": self._calculate_trend_direction(ratio_values)
            }
        return {}
    
    def _calculate_quick_ratio_trend(self, bs_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate quick ratio trend"""
        current_assets = self._extract_metric_values(bs_df, ["Current Assets"])
        inventory = self._extract_metric_values(bs_df, ["Inventory"])
        current_liabilities = self._extract_metric_values(bs_df, ["Current Liabilities"])
        
        if current_assets and current_liabilities and len(current_assets) >= 2:
            quick_assets = [ca - (inv if inv else 0) for ca, inv in zip(current_assets, inventory)]
            ratio_values = [qa/cl if cl != 0 else 0 for qa, cl in zip(quick_assets, current_liabilities)]
            return {
                "values": ratio_values,
                "latest": ratio_values[-1] if ratio_values else None,
                "average": float(np.mean(ratio_values)) if ratio_values else None,
                "trend": self._calculate_trend_direction(ratio_values)
            }
        return {}
    
    def _calculate_cash_ratio_trend(self, bs_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate cash ratio trend"""
        cash = self._extract_metric_values(bs_df, ["Cash And Cash Equivalents", "Cash Financial"])
        current_liabilities = self._extract_metric_values(bs_df, ["Current Liabilities"])
        
        if cash and current_liabilities and len(cash) >= 2:
            ratio_values = [c/cl if cl != 0 else 0 for c, cl in zip(cash, current_liabilities)]
            return {
                "values": ratio_values,
                "latest": ratio_values[-1] if ratio_values else None,
                "average": float(np.mean(ratio_values)) if ratio_values else None,
                "trend": self._calculate_trend_direction(ratio_values)
            }
        return {}
    
    def _calculate_fcf_yield_trend(self, cf_df: pd.DataFrame, bs_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate FCF yield trend"""
        fcf = self._extract_metric_values(cf_df, ["Free Cash Flow"])
        market_cap = self._extract_metric_values(bs_df, ["Market Cap"])  # This might not be available in balance sheet
        
        if fcf and len(fcf) >= 2:
            # For now, return FCF trend without yield calculation
            return {
                "values": fcf,
                "latest": fcf[-1] if fcf else None,
                "average": float(np.mean(fcf)) if fcf else None,
                "trend": self._calculate_trend_direction(fcf)
            }
        return {}
    
    def _calculate_fcf_margin_trend(self, cf_df: pd.DataFrame, is_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate FCF margin trend"""
        fcf = self._extract_metric_values(cf_df, ["Free Cash Flow"])
        revenue = self._extract_metric_values(is_df, ["Total Revenue", "Revenue"])
        
        if fcf and revenue and len(fcf) >= 2:
            margin_values = [f/r if r != 0 else 0 for f, r in zip(fcf, revenue)]
            return {
                "values": margin_values,
                "latest": margin_values[-1] if margin_values else None,
                "average": float(np.mean(margin_values)) if margin_values else None,
                "trend": self._calculate_trend_direction(margin_values)
            }
        return {}
    
    async def _analyze_accrual_quality(self, is_df: pd.DataFrame, cf_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze accrual quality and earnings persistence"""
        try:
            # Calculate accruals (Net Income - CFO)
            net_income_values = self._extract_metric_values(is_df, ["Net Income", "Net Income Common Stockholders"])
            cfo_values = self._extract_metric_values(cf_df, ["Total Cash From Operating Activities", "Operating Cash Flow"])
            
            if not net_income_values or not cfo_values:
                return {}
            
            accruals = []
            for i in range(min(len(net_income_values), len(cfo_values))):
                accrual = net_income_values[i] - cfo_values[i]
                accruals.append(accrual)
            
            if len(accruals) >= 3:
                # Calculate accrual quality metrics
                accrual_volatility = self._calculate_volatility(accruals)
                accrual_trend = self._calculate_trend_direction(accruals)
                
                # Normalize accruals by total assets if available
                total_assets = self._extract_metric_values(is_df, ["Total Assets"])
                normalized_accruals = []
                if total_assets and len(total_assets) >= len(accruals):
                    for i in range(len(accruals)):
                        if total_assets[i] != 0:
                            normalized_accruals.append(accruals[i] / total_assets[i])
                
                return {
                    "accrual_values": accruals,
                    "normalized_accruals": normalized_accruals,
                    "volatility": accrual_volatility,
                    "trend": accrual_trend,
                    "quality_score": self._assess_accrual_quality_score(accruals, normalized_accruals)
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error analyzing accrual quality: {str(e)}")
            return {}
    
    async def _analyze_revenue_quality(self, is_df: pd.DataFrame, cf_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze revenue recognition quality and consistency"""
        try:
            revenue_values = self._extract_metric_values(is_df, ["Total Revenue", "Operating Revenue", "Revenue"])
            
            if not revenue_values or len(revenue_values) < 3:
                return {}
            
            # Calculate revenue growth consistency
            revenue_growth = []
            for i in range(1, len(revenue_values)):
                if revenue_values[i-1] != 0:
                    growth = (revenue_values[i] - revenue_values[i-1]) / abs(revenue_values[i-1])
                    revenue_growth.append(growth)
            
            if revenue_growth:
                growth_volatility = self._calculate_volatility(revenue_growth)
                growth_trend = self._calculate_trend_direction(revenue_growth)
                
                return {
                    "revenue_values": revenue_values,
                    "growth_rates": revenue_growth,
                    "growth_volatility": growth_volatility,
                    "growth_trend": growth_trend,
                    "consistency_score": self._assess_revenue_consistency_score(revenue_growth),
                    "quality_score": self._assess_revenue_quality_score(revenue_values, revenue_growth)
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error analyzing revenue quality: {str(e)}")
            return {}
    
    async def _detect_non_recurring_items(self, is_df: pd.DataFrame) -> Dict[str, Any]:
        """Detect potential non-recurring items in income statement"""
        try:
            non_recurring_indicators = {}
            
            # Look for common non-recurring item patterns
            non_recurring_keywords = [
                "restructuring", "impairment", "gain", "loss", "discontinued", 
                "extraordinary", "one-time", "special", "unusual"
            ]
            
            # Check for large variations in specific line items
            line_items_to_check = [
                "Total Revenue", "Operating Income", "Net Income", 
                "Other Income", "Interest Expense", "Depreciation"
            ]
            
            for item in line_items_to_check:
                values = self._extract_metric_values(is_df, [item])
                if values and len(values) >= 3:
                    # Calculate coefficient of variation
                    if float(np.mean(values)) != 0:
                        cv = float(np.std(values)) / abs(float(np.mean(values)))
                        if cv > 0.5:  # High variation threshold
                            non_recurring_indicators[item] = {
                                "coefficient_of_variation": cv,
                                "values": values,
                                "potential_non_recurring": cv > 0.8
                            }
            
            return non_recurring_indicators
            
        except Exception as e:
            logger.error(f"Error detecting non-recurring items: {str(e)}")
            return {}
    
    async def _analyze_working_capital_quality(self, bs_df: pd.DataFrame, cf_df: pd.DataFrame) -> Dict[str, Any]:
        """Enhanced working capital analysis"""
        try:
            current_assets = self._extract_metric_values(bs_df, ["Total Current Assets"])
            current_liabilities = self._extract_metric_values(bs_df, ["Total Current Liabilities"])
            
            if not current_assets or not current_liabilities:
                return {}
            
            working_capital = [ca - cl for ca, cl in zip(current_assets, current_liabilities)]
            
            # Calculate working capital efficiency
            revenue_values = self._extract_metric_values(bs_df, ["Total Revenue", "Operating Revenue"])
            wc_turnover = []
            
            if revenue_values and len(revenue_values) >= len(working_capital):
                for i in range(len(working_capital)):
                    if working_capital[i] != 0:
                        turnover = revenue_values[i] / abs(working_capital[i])
                        wc_turnover.append(turnover)
            
            return {
                "working_capital_values": working_capital,
                "latest": working_capital[-1] if working_capital else None,
                "trend": self._calculate_trend_direction(working_capital),
                "volatility": self._calculate_volatility(working_capital),
                "turnover_ratios": wc_turnover,
                "efficiency_score": self._assess_working_capital_efficiency(wc_turnover)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing working capital quality: {str(e)}")
            return {}
    
    async def _calculate_cash_flow_quality_score(self, cf_df: pd.DataFrame, is_df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate comprehensive cash flow quality score"""
        try:
            operating_cf = self._extract_metric_values(cf_df, ["Total Cash From Operating Activities", "Operating Cash Flow"])
            investing_cf = self._extract_metric_values(cf_df, ["Total Cash From Investing Activities", "Investing Cash Flow"])
            financing_cf = self._extract_metric_values(cf_df, ["Total Cash From Financing Activities", "Financing Cash Flow"])
            net_income = self._extract_metric_values(is_df, ["Net Income", "Net Income Common Stockholders"])
            
            if not operating_cf or not net_income:
                return {}
            
            # Calculate cash flow quality metrics
            cf_quality_metrics = {}
            
            # Operating cash flow consistency
            if len(operating_cf) >= 3:
                cf_quality_metrics["operating_cf_consistency"] = self._assess_cash_flow_consistency(operating_cf)
                cf_quality_metrics["operating_cf_trend"] = self._calculate_trend_direction(operating_cf)
            
            # Cash flow from operations vs net income
            if len(operating_cf) >= len(net_income):
                cf_ni_ratios = []
                for i in range(len(net_income)):
                    if net_income[i] != 0:
                        ratio = operating_cf[i] / net_income[i]
                        cf_ni_ratios.append(ratio)
                
                if cf_ni_ratios:
                    cf_quality_metrics["cf_to_ni_ratio"] = {
                        "latest": cf_ni_ratios[-1],
                        "average": float(np.mean(cf_ni_ratios)),
                        "consistency": self._assess_cash_flow_consistency(cf_ni_ratios)
                    }
            
            # Overall cash flow quality score
            cf_quality_metrics["overall_score"] = self._calculate_cash_flow_quality_overall(cf_quality_metrics)
            
            return cf_quality_metrics
            
        except Exception as e:
            logger.error(f"Error calculating cash flow quality score: {str(e)}")
            return {}
    
    async def _detect_earnings_manipulation_indicators(self, is_df: pd.DataFrame, cf_df: pd.DataFrame, bs_df: pd.DataFrame) -> Dict[str, Any]:
        """Detect potential earnings manipulation indicators"""
        try:
            indicators = {}
            
            # 1. CFO vs Net Income divergence
            net_income = self._extract_metric_values(is_df, ["Net Income", "Net Income Common Stockholders"])
            cfo = self._extract_metric_values(cf_df, ["Total Cash From Operating Activities", "Operating Cash Flow"])
            
            if net_income and cfo and len(net_income) >= 3:
                cfo_ni_ratios = []
                for i in range(min(len(net_income), len(cfo))):
                    if net_income[i] != 0:
                        ratio = cfo[i] / net_income[i]
                        cfo_ni_ratios.append(ratio)
                
                if cfo_ni_ratios:
                    # Flag if CFO consistently lower than Net Income
                    avg_ratio = float(np.mean(cfo_ni_ratios))
                    indicators["cfo_ni_divergence"] = {
                        "average_ratio": avg_ratio,
                        "red_flag": avg_ratio < 0.5,  # CFO significantly lower than NI (more realistic threshold)
                        "severity": "high" if avg_ratio < 0.3 else "medium" if avg_ratio < 0.5 else "low"
                    }
            
            # 2. Revenue vs Cash Collection divergence
            revenue = self._extract_metric_values(is_df, ["Total Revenue", "Operating Revenue"])
            if revenue and cfo and len(revenue) >= 3:
                revenue_cf_ratios = []
                for i in range(min(len(revenue), len(cfo))):
                    if revenue[i] != 0:
                        ratio = cfo[i] / revenue[i]
                        revenue_cf_ratios.append(ratio)
                
                if revenue_cf_ratios:
                    avg_ratio = float(np.mean(revenue_cf_ratios))
                    indicators["revenue_cf_divergence"] = {
                        "average_ratio": avg_ratio,
                        "red_flag": avg_ratio < 0.05,  # Very low cash collection (more realistic threshold)
                        "severity": "high" if avg_ratio < 0.02 else "medium" if avg_ratio < 0.05 else "low"
                    }
            
            # 3. Working capital manipulation indicators
            if not bs_df.empty:
                current_assets = self._extract_metric_values(bs_df, ["Total Current Assets"])
                if current_assets and len(current_assets) >= 3:
                    wc_growth = []
                    for i in range(1, len(current_assets)):
                        if current_assets[i-1] != 0:
                            growth = (current_assets[i] - current_assets[i-1]) / abs(current_assets[i-1])
                            wc_growth.append(growth)
                    
                    if wc_growth:
                        wc_volatility = self._calculate_volatility(wc_growth)
                        indicators["working_capital_manipulation"] = {
                            "volatility": wc_volatility,
                            "red_flag": wc_volatility > 0.5,  # High working capital volatility
                            "severity": "high" if wc_volatility > 0.8 else "medium" if wc_volatility > 0.5 else "low"
                        }
            
            # Overall manipulation risk score
            indicators["overall_risk_score"] = self._calculate_manipulation_risk_score(indicators)
            
            return indicators
            
        except Exception as e:
            logger.error(f"Error detecting earnings manipulation indicators: {str(e)}")
            return {}
    
    def _calculate_overall_earnings_quality_score(self, quality_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall earnings quality score"""
        try:
            scores = []
            weights = []
            
            # CFO quality (40% weight)
            if "cfo_to_net_income" in quality_metrics:
                cfo_score = self._convert_quality_score_to_numeric(quality_metrics["cfo_to_net_income"].get("quality_score", "unknown"))
                scores.append(cfo_score)
                weights.append(0.4)
            
            # Accrual quality (25% weight)
            if "accrual_quality" in quality_metrics:
                accrual_score = self._convert_quality_score_to_numeric(quality_metrics["accrual_quality"].get("quality_score", "unknown"))
                scores.append(accrual_score)
                weights.append(0.25)
            
            # Revenue quality (20% weight)
            if "revenue_quality" in quality_metrics:
                revenue_score = self._convert_quality_score_to_numeric(quality_metrics["revenue_quality"].get("quality_score", "unknown"))
                scores.append(revenue_score)
                weights.append(0.20)
            
            # Cash flow quality (15% weight)
            if "cash_flow_quality" in quality_metrics:
                cf_score = quality_metrics["cash_flow_quality"].get("overall_score", 50)
                scores.append(cf_score)
                weights.append(0.15)
            
            if scores and weights:
                weighted_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
                
                return {
                    "score": float(weighted_score),
                    "grade": self._convert_score_to_grade(weighted_score),
                    "components": {
                        "cfo_quality": quality_metrics.get("cfo_to_net_income", {}).get("quality_score", "unknown"),
                        "accrual_quality": quality_metrics.get("accrual_quality", {}).get("quality_score", "unknown"),
                        "revenue_quality": quality_metrics.get("revenue_quality", {}).get("quality_score", "unknown"),
                        "cash_flow_quality": float(quality_metrics.get("cash_flow_quality", {}).get("overall_score", 50))
                    }
                }
            
            return {"score": 50, "grade": "C", "components": {}}
            
        except Exception as e:
            logger.error(f"Error calculating overall earnings quality score: {str(e)}")
            return {"score": 50, "grade": "C", "components": {}}
    
    # Helper methods for balance sheet forensics
    async def _analyze_debt_structure(self, bs_df: pd.DataFrame, is_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze debt structure and maturity profile"""
        try:
            total_debt = self._extract_metric_values(bs_df, ["Total Debt", "Long Term Debt"])
            total_equity = self._extract_metric_values(bs_df, ["Total Stockholder Equity", "Total Equity"])
            total_assets = self._extract_metric_values(bs_df, ["Total Assets"])
            
            if not total_debt or not total_equity:
                return {}
            
            # Calculate debt ratios
            debt_equity_ratios = [td/te if te != 0 else 0 for td, te in zip(total_debt, total_equity)]
            debt_asset_ratios = []
            if total_assets:
                debt_asset_ratios = [td/ta if ta != 0 else 0 for td, ta in zip(total_debt, total_assets)]
            
            return {
                "debt_equity_ratio": {
                    "latest": debt_equity_ratios[-1] if debt_equity_ratios else None,
                    "average": float(np.mean(debt_equity_ratios)) if debt_equity_ratios else None,
                    "trend": self._calculate_trend_direction(debt_equity_ratios),
                    "strength_score": self._assess_debt_strength_score(debt_equity_ratios)
                },
                "debt_asset_ratio": {
                    "latest": debt_asset_ratios[-1] if debt_asset_ratios else None,
                    "average": float(np.mean(debt_asset_ratios)) if debt_asset_ratios else None,
                    "trend": self._calculate_trend_direction(debt_asset_ratios)
                },
                "debt_trend": self._calculate_trend_direction(total_debt),
                "equity_trend": self._calculate_trend_direction(total_equity)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing debt structure: {str(e)}")
            return {}
    
    async def _analyze_interest_coverage(self, is_df: pd.DataFrame, bs_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze interest coverage trends and adequacy"""
        try:
            ebit_values = self._extract_metric_values(is_df, ["EBIT", "Operating Income", "Income Before Tax"])
            interest_expense = self._extract_metric_values(is_df, ["Interest Expense", "Total Interest Expense"])
            
            if not ebit_values or not interest_expense:
                return {}
            
            # Calculate interest coverage ratios
            coverage_ratios = []
            for i in range(min(len(ebit_values), len(interest_expense))):
                if interest_expense[i] != 0:
                    coverage = ebit_values[i] / abs(interest_expense[i])
                    coverage_ratios.append(coverage)
            
            if coverage_ratios:
                return {
                    "coverage_ratios": coverage_ratios,
                    "latest": coverage_ratios[-1],
                    "average": float(np.mean(coverage_ratios)),
                    "minimum": min(coverage_ratios),
                    "trend": self._calculate_trend_direction(coverage_ratios),
                    "adequacy_score": self._assess_interest_coverage_adequacy(coverage_ratios)
                }
            
            return {}
            
        except Exception as e:
            logger.error(f"Error analyzing interest coverage: {str(e)}")
            return {}
    
    async def _assess_asset_quality(self, bs_df: pd.DataFrame, is_df: pd.DataFrame) -> Dict[str, Any]:
        """Assess asset quality and composition"""
        try:
            total_assets = self._extract_metric_values(bs_df, ["Total Assets"])
            current_assets = self._extract_metric_values(bs_df, ["Total Current Assets"])
            fixed_assets = self._extract_metric_values(bs_df, ["Net PPE", "Property Plant And Equipment"])
            
            if not total_assets:
                return {}
            
            # Calculate asset composition ratios
            current_asset_ratios = []
            fixed_asset_ratios = []
            
            if current_assets:
                current_asset_ratios = [ca/ta if ta != 0 else 0 for ca, ta in zip(current_assets, total_assets)]
            
            if fixed_assets:
                fixed_asset_ratios = [fa/ta if ta != 0 else 0 for fa, ta in zip(fixed_assets, total_assets)]
            
            return {
                "asset_composition": {
                    "current_assets_ratio": {
                        "latest": current_asset_ratios[-1] if current_asset_ratios else None,
                        "average": float(np.mean(current_asset_ratios)) if current_asset_ratios else None,
                        "trend": self._calculate_trend_direction(current_asset_ratios)
                    },
                    "fixed_assets_ratio": {
                        "latest": fixed_asset_ratios[-1] if fixed_asset_ratios else None,
                        "average": float(np.mean(fixed_asset_ratios)) if fixed_asset_ratios else None,
                        "trend": self._calculate_trend_direction(fixed_asset_ratios)
                    }
                },
                "asset_growth": {
                    "total_assets_trend": self._calculate_trend_direction(total_assets),
                    "current_assets_trend": self._calculate_trend_direction(current_assets) if current_assets else "unknown",
                    "fixed_assets_trend": self._calculate_trend_direction(fixed_assets) if fixed_assets else "unknown"
                },
                "quality_score": self._assess_asset_quality_score(current_asset_ratios, fixed_asset_ratios)
            }
            
        except Exception as e:
            logger.error(f"Error assessing asset quality: {str(e)}")
            return {}
    
    async def _analyze_liquidity_strength(self, bs_df: pd.DataFrame, cf_df: pd.DataFrame) -> Dict[str, Any]:
        """Enhanced liquidity analysis"""
        try:
            current_assets = self._extract_metric_values(bs_df, ["Total Current Assets"])
            current_liabilities = self._extract_metric_values(bs_df, ["Total Current Liabilities"])
            cash_values = self._extract_metric_values(bs_df, ["Cash And Cash Equivalents", "Cash"])
            
            if not current_assets or not current_liabilities:
                return {}
            
            # Calculate liquidity ratios
            current_ratios = [ca/cl if cl != 0 else 0 for ca, cl in zip(current_assets, current_liabilities)]
            quick_ratios = []
            cash_ratios = []
            
            # Quick ratio (assuming inventory is current assets - cash)
            if cash_values and len(cash_values) >= len(current_assets):
                for i in range(len(current_assets)):
                    if current_liabilities[i] != 0:
                        quick_asset = current_assets[i] - (current_assets[i] - cash_values[i])  # Simplified
                        quick_ratios.append(quick_asset / current_liabilities[i])
            
            # Cash ratio
            if cash_values:
                cash_ratios = [cash/cl if cl != 0 else 0 for cash, cl in zip(cash_values, current_liabilities)]
            
            return {
                "current_ratio": {
                    "latest": current_ratios[-1] if current_ratios else None,
                    "average": float(np.mean(current_ratios)) if current_ratios else None,
                    "trend": self._calculate_trend_direction(current_ratios),
                    "strength_score": self._assess_liquidity_strength_score(current_ratios)
                },
                "quick_ratio": {
                    "latest": quick_ratios[-1] if quick_ratios else None,
                    "average": float(np.mean(quick_ratios)) if quick_ratios else None,
                    "trend": self._calculate_trend_direction(quick_ratios)
                },
                "cash_ratio": {
                    "latest": cash_ratios[-1] if cash_ratios else None,
                    "average": float(np.mean(cash_ratios)) if cash_ratios else None,
                    "trend": self._calculate_trend_direction(cash_ratios)
                }
            }
            
        except Exception as e:
            logger.error(f"Error analyzing liquidity strength: {str(e)}")
            return {}
    
    async def _analyze_cash_position(self, bs_df: pd.DataFrame, is_df: pd.DataFrame) -> Dict[str, Any]:
        """Analyze cash position and adequacy"""
        try:
            cash_values = self._extract_metric_values(bs_df, ["Cash And Cash Equivalents", "Cash"])
            total_assets = self._extract_metric_values(bs_df, ["Total Assets"])
            revenue_values = self._extract_metric_values(is_df, ["Total Revenue", "Operating Revenue"])
            
            if not cash_values:
                return {}
            
            # Calculate cash ratios
            cash_asset_ratios = []
            cash_revenue_ratios = []
            
            if total_assets:
                cash_asset_ratios = [cash/ta if ta != 0 else 0 for cash, ta in zip(cash_values, total_assets)]
            
            if revenue_values and len(revenue_values) >= len(cash_values):
                cash_revenue_ratios = [cash/rev if rev != 0 else 0 for cash, rev in zip(cash_values, revenue_values)]
            
            return {
                "cash_asset_ratio": {
                    "latest": cash_asset_ratios[-1] if cash_asset_ratios else None,
                    "average": float(np.mean(cash_asset_ratios)) if cash_asset_ratios else None,
                    "trend": self._calculate_trend_direction(cash_asset_ratios)
                },
                "cash_revenue_ratio": {
                    "latest": cash_revenue_ratios[-1] if cash_revenue_ratios else None,
                    "average": float(np.mean(cash_revenue_ratios)) if cash_revenue_ratios else None,
                    "trend": self._calculate_trend_direction(cash_revenue_ratios)
                },
                "cash_trend": self._calculate_trend_direction(cash_values),
                "adequacy_score": self._assess_cash_adequacy_score(cash_asset_ratios, cash_revenue_ratios)
            }
            
        except Exception as e:
            logger.error(f"Error analyzing cash position: {str(e)}")
            return {}
    
    async def _assess_off_balance_sheet_risks(self, bs_df: pd.DataFrame, is_df: pd.DataFrame) -> Dict[str, Any]:
        """Assess potential off-balance sheet risks"""
        try:
            # This is a simplified assessment - in practice, you'd look for specific off-balance sheet items
            # For now, we'll analyze patterns that might indicate off-balance sheet activities
            
            total_assets = self._extract_metric_values(bs_df, ["Total Assets"])
            total_liabilities = self._extract_metric_values(bs_df, ["Total Liabilities"])
            
            if not total_assets or not total_liabilities:
                return {}
            
            # Calculate leverage ratios
            leverage_ratios = [tl/ta if ta != 0 else 0 for tl, ta in zip(total_liabilities, total_assets)]
            
            # Look for unusual patterns that might indicate off-balance sheet activities
            risk_indicators = {
                "leverage_trend": self._calculate_trend_direction(leverage_ratios),
                "leverage_volatility": self._calculate_volatility(leverage_ratios),
                "risk_level": self._assess_off_balance_sheet_risk_level(leverage_ratios)
            }
            
            return risk_indicators
            
        except Exception as e:
            logger.error(f"Error assessing off-balance sheet risks: {str(e)}")
            return {}
    
    async def _calculate_financial_flexibility_score(self, strength_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate financial flexibility score"""
        try:
            score = 50  # Base score
            
            # Debt analysis (30% weight)
            if "debt_analysis" in strength_metrics:
                debt_score = strength_metrics["debt_analysis"].get("debt_equity_ratio", {}).get("strength_score", "fair")
                score += self._convert_quality_score_to_numeric(debt_score) * 0.15
            
            # Interest coverage (25% weight)
            if "interest_coverage" in strength_metrics:
                coverage_score = strength_metrics["interest_coverage"].get("adequacy_score", "fair")
                score += self._convert_quality_score_to_numeric(coverage_score) * 0.125
            
            # Liquidity (25% weight)
            if "liquidity" in strength_metrics:
                liquidity_score = strength_metrics["liquidity"].get("current_ratio", {}).get("strength_score", "fair")
                score += self._convert_quality_score_to_numeric(liquidity_score) * 0.125
            
            # Cash position (20% weight)
            if "cash_position" in strength_metrics:
                cash_score = strength_metrics["cash_position"].get("adequacy_score", "fair")
                score += self._convert_quality_score_to_numeric(cash_score) * 0.1
            
            return {
                "score": max(0, min(100, score)),
                "grade": self._convert_score_to_grade(score),
                "flexibility_level": "high" if score >= 80 else "medium" if score >= 60 else "low"
            }
            
        except Exception as e:
            logger.error(f"Error calculating financial flexibility score: {str(e)}")
            return {"score": 50, "grade": "C", "flexibility_level": "medium"}
    
    def _calculate_overall_balance_sheet_score(self, strength_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall balance sheet strength score"""
        try:
            scores = []
            weights = []
            
            # Debt analysis (25% weight)
            if "debt_analysis" in strength_metrics:
                debt_score = self._convert_quality_score_to_numeric(
                    strength_metrics["debt_analysis"].get("debt_equity_ratio", {}).get("strength_score", "fair")
                )
                scores.append(debt_score)
                weights.append(0.25)
            
            # Interest coverage (20% weight)
            if "interest_coverage" in strength_metrics:
                coverage_score = self._convert_quality_score_to_numeric(
                    strength_metrics["interest_coverage"].get("adequacy_score", "fair")
                )
                scores.append(coverage_score)
                weights.append(0.20)
            
            # Liquidity (25% weight)
            if "liquidity" in strength_metrics:
                liquidity_score = self._convert_quality_score_to_numeric(
                    strength_metrics["liquidity"].get("current_ratio", {}).get("strength_score", "fair")
                )
                scores.append(liquidity_score)
                weights.append(0.25)
            
            # Cash position (20% weight)
            if "cash_position" in strength_metrics:
                cash_score = self._convert_quality_score_to_numeric(
                    strength_metrics["cash_position"].get("adequacy_score", "fair")
                )
                scores.append(cash_score)
                weights.append(0.20)
            
            # Asset quality (10% weight)
            if "asset_quality" in strength_metrics:
                asset_score = self._convert_quality_score_to_numeric(
                    strength_metrics["asset_quality"].get("quality_score", "fair")
                )
                scores.append(asset_score)
                weights.append(0.10)
            
            if scores and weights:
                weighted_score = sum(s * w for s, w in zip(scores, weights)) / sum(weights)
                
                return {
                    "score": float(weighted_score),
                    "grade": self._convert_score_to_grade(weighted_score),
                    "strength_level": "strong" if weighted_score >= 75 else "moderate" if weighted_score >= 55 else "weak",
                    "grade_explanation": self._generate_grade_explanation(weighted_score, strength_metrics),
                    "components": {
                        "debt_strength": strength_metrics.get("debt_analysis", {}).get("debt_equity_ratio", {}).get("strength_score", "unknown"),
                        "interest_coverage": strength_metrics.get("interest_coverage", {}).get("adequacy_score", "unknown"),
                        "liquidity": strength_metrics.get("liquidity", {}).get("current_ratio", {}).get("strength_score", "unknown"),
                        "cash_position": strength_metrics.get("cash_position", {}).get("adequacy_score", "unknown"),
                        "asset_quality": strength_metrics.get("asset_quality", {}).get("quality_score", "unknown")
                    }
                }
            
            return {"score": 50, "grade": "C", "strength_level": "moderate", "components": {}}
            
        except Exception as e:
            logger.error(f"Error calculating overall balance sheet score: {str(e)}")
            return {"score": 50, "grade": "C", "strength_level": "moderate", "components": {}}

    # Helper methods for balance sheet forensics
    def _assess_debt_strength_score(self, debt_ratios: List[float]) -> str:
        """Assess debt strength score - Institutional Grade Thresholds"""
        if not debt_ratios:
            return "unknown"
        
        avg_ratio = float(np.mean(debt_ratios))
        # More realistic thresholds for capital-intensive conglomerates
        if avg_ratio < 0.2:
            return "excellent"  # Very conservative
        elif avg_ratio < 0.4:
            return "good"       # Conservative (Reliance ~0.41x)
        elif avg_ratio < 0.6:
            return "fair"       # Moderate leverage
        elif avg_ratio < 0.8:
            return "moderate"   # Higher leverage but manageable
        else:
            return "poor"       # High leverage risk
    
    def _assess_interest_coverage_adequacy(self, coverage_ratios: List[float]) -> str:
        """Assess interest coverage adequacy"""
        if not coverage_ratios:
            return "unknown"
        
        min_coverage = min(coverage_ratios)
        avg_coverage = float(np.mean(coverage_ratios))
        
        if min_coverage >= 5 and avg_coverage >= 8:
            return "excellent"
        elif min_coverage >= 3 and avg_coverage >= 5:
            return "good"
        elif min_coverage >= 2 and avg_coverage >= 3:
            return "fair"
        else:
            return "poor"
    
    def _assess_asset_quality_score(self, current_ratios: List[float], fixed_ratios: List[float]) -> str:
        """Assess asset quality score"""
        if not current_ratios and not fixed_ratios:
            return "unknown"
        
        # Higher current asset ratio generally indicates better liquidity
        if current_ratios:
            avg_current = float(np.mean(current_ratios))
            if avg_current > 0.4:
                return "excellent"
            elif avg_current > 0.3:
                return "good"
            elif avg_current > 0.2:
                return "fair"
            else:
                return "poor"
        
        return "unknown"
    
    def _assess_liquidity_strength_score(self, current_ratios: List[float]) -> str:
        """Assess liquidity strength score"""
        if not current_ratios:
            return "unknown"
        
        avg_ratio = float(np.mean(current_ratios))
        if avg_ratio >= 2.0:
            return "excellent"
        elif avg_ratio >= 1.5:
            return "good"
        elif avg_ratio >= 1.2:
            return "fair"
        else:
            return "poor"
    
    def _assess_cash_adequacy_score(self, cash_asset_ratios: List[float], cash_revenue_ratios: List[float]) -> str:
        """Assess cash adequacy score"""
        if not cash_asset_ratios and not cash_revenue_ratios:
            return "unknown"
        
        score_factors = []
        
        if cash_asset_ratios:
            avg_cash_asset = float(np.mean(cash_asset_ratios))
            if avg_cash_asset > 0.15:
                score_factors.append(3)
            elif avg_cash_asset > 0.10:
                score_factors.append(2)
            elif avg_cash_asset > 0.05:
                score_factors.append(1)
            else:
                score_factors.append(0)
        
        if cash_revenue_ratios:
            avg_cash_revenue = float(np.mean(cash_revenue_ratios))
            if avg_cash_revenue > 0.20:
                score_factors.append(3)
            elif avg_cash_revenue > 0.10:
                score_factors.append(2)
            elif avg_cash_revenue > 0.05:
                score_factors.append(1)
            else:
                score_factors.append(0)
        
        if score_factors:
            avg_score = float(np.mean(score_factors))
            if avg_score >= 2.5:
                return "excellent"
            elif avg_score >= 1.5:
                return "good"
            elif avg_score >= 0.5:
                return "fair"
            else:
                return "poor"
        
        return "unknown"
    
    def _assess_off_balance_sheet_risk_level(self, leverage_ratios: List[float]) -> str:
        """Assess off-balance sheet risk level"""
        if not leverage_ratios:
            return "unknown"
        
        volatility = self._calculate_volatility(leverage_ratios)
        avg_leverage = float(np.mean(leverage_ratios))
        
        if volatility > 0.3 or avg_leverage > 0.8:
            return "high"
        elif volatility > 0.2 or avg_leverage > 0.6:
            return "medium"
        else:
            return "low"

    # Helper methods for earnings quality analysis
    def _assess_cfo_consistency_score(self, ratios: List[float]) -> str:
        """Assess CFO consistency score"""
        if not ratios:
            return "unknown"
        
        volatility = self._calculate_volatility(ratios)
        if volatility < 0.1:
            return "excellent"
        elif volatility < 0.2:
            return "good"
        elif volatility < 0.3:
            return "fair"
        else:
            return "poor"
    
    def _assess_accrual_quality_score(self, accruals: List[float], normalized_accruals: List[float]) -> str:
        """Assess accrual quality score - adjusted for large companies"""
        if not accruals:
            return "unknown"
        
        # Use normalized accruals if available (relative to assets)
        if normalized_accruals and len(normalized_accruals) >= 3:
            volatility = self._calculate_volatility(normalized_accruals)
            # More lenient thresholds for normalized accruals
            if volatility < 0.1:
                return "excellent"
            elif volatility < 0.2:
                return "good"
            elif volatility < 0.3:
                return "fair"
            else:
                return "poor"
        else:
            # For absolute accruals, use coefficient of variation (CV) instead of raw volatility
            mean_accruals = abs(sum(accruals) / len(accruals))
            if mean_accruals == 0:
                return "unknown"
            
            volatility = self._calculate_volatility(accruals)
            cv = volatility / mean_accruals  # Coefficient of variation
            
            # More appropriate thresholds for large companies
            if cv < 0.5:
                return "excellent"
            elif cv < 1.0:
                return "good"
            elif cv < 2.0:
                return "fair"
            else:
                return "poor"
    
    def _assess_revenue_consistency_score(self, growth_rates: List[float]) -> str:
        """Assess revenue consistency score"""
        if not growth_rates:
            return "unknown"
        
        volatility = self._calculate_volatility(growth_rates)
        if volatility < 0.15:
            return "excellent"
        elif volatility < 0.25:
            return "good"
        elif volatility < 0.35:
            return "fair"
        else:
            return "poor"
    
    def _assess_revenue_quality_score(self, revenue_values: List[float], growth_rates: List[float]) -> str:
        """Assess overall revenue quality score - improved methodology"""
        if not revenue_values or not growth_rates:
            return "unknown"
        
        # Multiple factors for revenue quality assessment
        factors = []
        
        # 1. Growth consistency (40% weight)
        positive_growth_count = sum(1 for rate in growth_rates if rate > 0)
        consistency_ratio = positive_growth_count / len(growth_rates)
        if consistency_ratio >= 0.8:
            factors.append(4)  # excellent
        elif consistency_ratio >= 0.6:
            factors.append(3)  # good
        elif consistency_ratio >= 0.4:
            factors.append(2)  # fair
        else:
            factors.append(1)  # poor
        
        # 2. Growth stability (30% weight) - lower volatility is better
        if len(growth_rates) >= 3:
            volatility = self._calculate_volatility(growth_rates)
            if volatility < 0.1:
                factors.append(4)  # excellent
            elif volatility < 0.2:
                factors.append(3)  # good
            elif volatility < 0.3:
                factors.append(2)  # fair
            else:
                factors.append(1)  # poor
        
        # 3. Revenue trend (30% weight) - positive trend is better
        if len(revenue_values) >= 3:
            trend = self._calculate_trend_direction(revenue_values)
            if trend == "increasing":
                factors.append(4)  # excellent
            elif trend == "stable":
                factors.append(3)  # good
            else:
                factors.append(2)  # fair
        
        # Calculate weighted average
        if factors:
            avg_score = sum(factors) / len(factors)
            if avg_score >= 3.5:
                return "excellent"
            elif avg_score >= 2.5:
                return "good"
            elif avg_score >= 1.5:
                return "fair"
            else:
                return "poor"
        
        return "unknown"
    
    def _assess_working_capital_efficiency(self, turnover_ratios: List[float]) -> str:
        """Assess working capital efficiency"""
        if not turnover_ratios:
            return "unknown"
        
        avg_turnover = float(np.mean(turnover_ratios))
        if avg_turnover > 8:
            return "excellent"
        elif avg_turnover > 5:
            return "good"
        elif avg_turnover > 3:
            return "fair"
        else:
            return "poor"
    
    def _assess_cash_flow_consistency(self, cf_values: List[float]) -> float:
        """Assess cash flow consistency (0-1 scale)"""
        if not cf_values or len(cf_values) < 2:
            return 0.5
        
        # Calculate coefficient of variation
        mean_cf = float(np.mean(cf_values))
        if mean_cf == 0:
            return 0.5
        
        cv = float(np.std(cf_values)) / abs(mean_cf)
        # Convert to 0-1 scale (lower CV = higher consistency)
        consistency = max(0, min(1, 1 - cv))
        return consistency
    
    def _calculate_cash_flow_quality_overall(self, cf_metrics: Dict[str, Any]) -> float:
        """Calculate overall cash flow quality score (0-100)"""
        try:
            score = 50  # Base score
            
            # Operating CF consistency (40% weight)
            if "operating_cf_consistency" in cf_metrics:
                consistency = cf_metrics["operating_cf_consistency"]
                score += consistency * 20  # Add up to 20 points
            
            # CF to NI ratio (30% weight)
            if "cf_to_ni_ratio" in cf_metrics:
                avg_ratio = cf_metrics["cf_to_ni_ratio"].get("average", 1.0)
                if avg_ratio > 1.2:
                    score += 15
                elif avg_ratio > 1.0:
                    score += 10
                elif avg_ratio > 0.8:
                    score += 5
            
            # Operating CF trend (30% weight)
            if "operating_cf_trend" in cf_metrics:
                trend = cf_metrics["operating_cf_trend"]
                if trend == "increasing":
                    score += 15
                elif trend == "stable":
                    score += 10
                elif trend == "decreasing":
                    score -= 10
            
            return max(0, min(100, score))
            
        except Exception as e:
            logger.error(f"Error calculating cash flow quality overall: {str(e)}")
            return 50
    
    def _calculate_manipulation_risk_score(self, indicators: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall manipulation risk score"""
        try:
            risk_factors = []
            severity_scores = {"low": 1, "medium": 2, "high": 3}
            
            # Debug logging
            logger.info(f"Calculating manipulation risk score for {len(indicators)} indicators")
            
            # Exclude the overall_risk_score key to avoid circular reference
            for indicator_name, indicator_data in indicators.items():
                if indicator_name != "overall_risk_score" and isinstance(indicator_data, dict) and "red_flag" in indicator_data:
                    red_flag = indicator_data["red_flag"]
                    severity = indicator_data.get("severity", "low")
                    logger.info(f"Indicator {indicator_name}: red_flag={red_flag}, severity={severity}")
                    
                    if indicator_data["red_flag"]:
                        risk_factors.append(severity_scores.get(severity, 1))
                        logger.info(f"Added risk factor: {severity} (score: {severity_scores.get(severity, 1)})")
            
            logger.info(f"Total risk factors found: {len(risk_factors)}")
            
            if risk_factors:
                avg_risk = float(np.mean(risk_factors))
                if avg_risk >= 2.5:
                    risk_level = "high"
                elif avg_risk >= 1.5:
                    risk_level = "medium"
                else:
                    risk_level = "low"
            else:
                risk_level = "low"
                avg_risk = 0
            
            result = {
                "risk_level": risk_level,
                "risk_score": avg_risk,
                "risk_factors_count": len(risk_factors),
                "overall_assessment": "clean" if risk_level == "low" else "monitor" if risk_level == "medium" else "investigate"
            }
            
            logger.info(f"Manipulation risk result: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error calculating manipulation risk score: {str(e)}")
            return {"risk_level": "unknown", "risk_score": 0, "risk_factors_count": 0, "overall_assessment": "unknown"}
    
    def _convert_quality_score_to_numeric(self, quality_score: str) -> float:
        """Convert quality score string to numeric value - Institutional Grade Mapping"""
        score_map = {
            "excellent": 85,  # A grade
            "good": 75,       # B grade  
            "fair": 65,       # C+ grade
            "moderate": 60,   # C grade
            "poor": 45,       # C- grade
            "weak": 35,       # D grade
            "unknown": 50    # Default neutral
        }
        return score_map.get(quality_score, 50)
    
    def _generate_grade_explanation(self, score: float, strength_metrics: Dict[str, Any]) -> str:
        """Generate contextual explanation for balance sheet grade"""
        try:
            # Get key metrics for context
            debt_ratio = strength_metrics.get("debt_analysis", {}).get("debt_equity_ratio", {}).get("latest_ratio", 0)
            interest_coverage = strength_metrics.get("interest_coverage", {}).get("latest", 0)
            current_ratio = strength_metrics.get("liquidity", {}).get("current_ratio", {}).get("latest", 0)
            
            if score >= 75:
                return f"Strong balance sheet with excellent debt management (D/E: {debt_ratio:.2f}x, Interest Coverage: {interest_coverage:.1f}x)"
            elif score >= 65:
                return f"Good balance sheet strength with moderate leverage (D/E: {debt_ratio:.2f}x, Interest Coverage: {interest_coverage:.1f}x)"
            elif score >= 55:
                return f"Moderate balance sheet strength; leverage acceptable for capital-intensive business (D/E: {debt_ratio:.2f}x, Interest Coverage: {interest_coverage:.1f}x)"
            elif score >= 45:
                return f"Below-average balance sheet strength; elevated leverage concerns (D/E: {debt_ratio:.2f}x, Interest Coverage: {interest_coverage:.1f}x)"
            else:
                return f"Weak balance sheet with high leverage risk (D/E: {debt_ratio:.2f}x, Interest Coverage: {interest_coverage:.1f}x)"
        except Exception:
            return "Balance sheet assessment based on available financial metrics"
    
    def _convert_score_to_grade(self, score: float) -> str:
        """Convert numeric score to letter grade - Institutional Grade Thresholds"""
        if score >= 85:
            return "A"
        elif score >= 75:
            return "B"
        elif score >= 65:
            return "C+"
        elif score >= 55:
            return "C"
        elif score >= 45:
            return "C-"
        elif score >= 35:
            return "D"
        else:
            return "F"

    def _generate_financial_summary(self, analysis_results: List[Any]) -> Dict[str, Any]:
        """Generate comprehensive financial summary"""
        try:
            summary = {
                "overall_grade": "B",
                "key_strengths": [],
                "key_concerns": [],
                "investment_thesis": "",
                "risk_assessment": "Moderate"
            }
            
            # Analyze results to generate summary
            # This would be enhanced based on the actual analysis results
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating financial summary: {str(e)}")
            return {"overall_grade": "Unknown", "key_strengths": [], "key_concerns": []}
    
    def _create_empty_analysis(self) -> Dict[str, Any]:
        """Create empty analysis structure when data is unavailable"""
        return {
            "ticker": "",
            "analysis_period_years": 0,
            "analysis_date": datetime.now().isoformat(),
            "income_statement_trends": {},
            "balance_sheet_trends": {},
            "cash_flow_trends": {},
            "financial_ratios": {},
            "margins_and_efficiency": {},
            "growth_metrics": {},
            "earnings_quality": {},
            "balance_sheet_strength": {},
            "summary": {
                "overall_grade": "Unknown",
                "key_strengths": [],
                "key_concerns": ["Insufficient financial data"],
                "investment_thesis": "Analysis pending - insufficient data",
                "risk_assessment": "Unknown"
            }
        }


# Global instance
deep_financial_analyzer = DeepFinancialAnalyzer()
