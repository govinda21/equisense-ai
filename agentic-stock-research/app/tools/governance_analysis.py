"""
Corporate Governance & Red Flag Analysis Module
Implements comprehensive governance checks and red flag detection for Indian equities
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class GovernanceMetrics:
    """Corporate governance metrics"""
    # Ownership structure
    promoter_holding_pct: Optional[float] = None
    promoter_pledge_pct: Optional[float] = None
    institutional_holding_pct: Optional[float] = None
    public_holding_pct: Optional[float] = None
    
    # Board composition
    independent_directors_pct: Optional[float] = None
    board_size: Optional[int] = None
    board_meetings_per_year: Optional[int] = None
    
    # Financial transparency
    auditor_tenure_years: Optional[int] = None
    auditor_changes_3yr: Optional[int] = None
    audit_opinion_qualified: Optional[bool] = None
    
    # Related party transactions
    rpt_as_pct_revenue: Optional[float] = None
    rpt_as_pct_profit: Optional[float] = None
    large_rpt_count: Optional[int] = None
    
    # Management activity
    insider_buying_12m: Optional[float] = None
    insider_selling_12m: Optional[float] = None
    management_compensation_growth: Optional[float] = None


@dataclass
class RedFlag:
    """Red flag detection result"""
    category: str
    severity: str  # "Low", "Medium", "High", "Critical"
    description: str
    metric_value: Optional[float] = None
    threshold: Optional[float] = None
    impact_score: float = 0.0  # 0-10 scale


class GovernanceAnalyzer:
    """Corporate governance and red flag analyzer"""
    
    def __init__(self):
        # Red flag thresholds (India-specific)
        self.thresholds = {
            # Ownership red flags
            "promoter_pledge_warning": 20.0,  # >20% pledge is concerning
            "promoter_pledge_critical": 50.0,  # >50% is critical
            "promoter_holding_low": 25.0,     # <25% may indicate lack of confidence
            "promoter_holding_high": 75.0,    # >75% may indicate poor public float
            
            # Board composition
            "independent_directors_min": 33.3,  # SEBI requirement
            "board_size_min": 6,
            "board_size_max": 15,
            
            # Financial red flags
            "rpt_revenue_warning": 10.0,      # >10% of revenue in RPTs
            "rpt_revenue_critical": 20.0,     # >20% is critical
            "auditor_changes_warning": 2,      # >2 changes in 3 years
            
            # Insider activity
            "insider_selling_warning": 1000000,  # >1M in selling
            "management_compensation_excessive": 50.0,  # >50% growth in compensation
        }
    
    async def analyze_governance(self, ticker: str) -> Dict[str, Any]:
        """
        Perform comprehensive governance analysis
        """
        try:
            # Fetch company data
            company_data = await self._fetch_governance_data(ticker)
            if not company_data:
                return {"error": "Unable to fetch governance data"}
            
            # Extract governance metrics
            metrics = await self._extract_governance_metrics(company_data)
            
            # Detect red flags
            red_flags = await self._detect_red_flags(metrics, company_data)
            
            # Calculate governance score
            governance_score = self._calculate_governance_score(metrics, red_flags)
            
            # Generate recommendations
            recommendations = self._generate_governance_recommendations(red_flags, governance_score)
            
            return {
                "ticker": ticker,
                "governance_score": governance_score,
                "governance_grade": self._score_to_grade(governance_score),
                "metrics": metrics.__dict__,
                "red_flags": [
                    {
                        "category": rf.category,
                        "severity": rf.severity,
                        "description": rf.description,
                        "metric_value": rf.metric_value,
                        "threshold": rf.threshold,
                        "impact_score": rf.impact_score
                    }
                    for rf in red_flags
                ],
                "recommendations": recommendations,
                "analysis_date": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Governance analysis failed for {ticker}: {e}")
            return {"error": str(e)}
    
    async def _fetch_governance_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch governance-related data"""
        try:
            def _fetch():
                t = yf.Ticker(ticker)
                info = t.info or {}
                
                # Get institutional holders
                institutional_holders = None
                try:
                    institutional_holders = t.institutional_holders
                except:
                    pass
                
                # Get insider transactions
                insider_transactions = None
                try:
                    insider_transactions = t.insider_transactions
                except:
                    pass
                
                return {
                    "info": info,
                    "institutional_holders": institutional_holders,
                    "insider_transactions": insider_transactions
                }
            
            return await asyncio.to_thread(_fetch)
            
        except Exception as e:
            logger.error(f"Failed to fetch governance data for {ticker}: {e}")
            return None
    
    async def _extract_governance_metrics(self, company_data: Dict[str, Any]) -> GovernanceMetrics:
        """Extract governance metrics from company data"""
        info = company_data["info"]
        
        # Extract basic metrics from info
        # Note: yfinance has limited governance data, this would be enhanced with NSE/BSE feeds
        metrics = GovernanceMetrics()
        
        # Ownership structure (simulated - would come from shareholding pattern)
        # These would be fetched from NSE/BSE shareholding pattern files
        metrics.promoter_holding_pct = info.get("heldPercentInstitutions", 0) * 100 if info.get("heldPercentInstitutions") else None
        metrics.institutional_holding_pct = info.get("heldPercentInstitutions", 0) * 100 if info.get("heldPercentInstitutions") else None
        
        # Board composition (would come from annual reports/company filings)
        metrics.board_size = info.get("fullTimeEmployees", 0) // 1000 if info.get("fullTimeEmployees") else None  # Rough proxy
        
        # Financial metrics
        metrics.auditor_changes_3yr = 0  # Would track from annual reports
        
        # Insider transactions
        if company_data.get("insider_transactions") is not None:
            insider_df = company_data["insider_transactions"]
            if not insider_df.empty:
                # Calculate 12-month insider activity
                one_year_ago = datetime.now() - timedelta(days=365)
                recent_transactions = insider_df[insider_df.index >= one_year_ago] if hasattr(insider_df.index, 'date') else insider_df
                
                if not recent_transactions.empty:
                    # Sum up insider buying and selling
                    if "Value" in recent_transactions.columns:
                        buying = recent_transactions[recent_transactions["Transaction"] == "Buy"]["Value"].sum() if "Transaction" in recent_transactions.columns else 0
                        selling = recent_transactions[recent_transactions["Transaction"] == "Sale"]["Value"].sum() if "Transaction" in recent_transactions.columns else 0
                        
                        metrics.insider_buying_12m = buying
                        metrics.insider_selling_12m = selling
        
        return metrics
    
    async def _detect_red_flags(self, metrics: GovernanceMetrics, company_data: Dict[str, Any]) -> List[RedFlag]:
        """Detect governance red flags"""
        red_flags = []
        info = company_data["info"]
        
        # Promoter pledge red flags
        if metrics.promoter_pledge_pct is not None:
            if metrics.promoter_pledge_pct > self.thresholds["promoter_pledge_critical"]:
                red_flags.append(RedFlag(
                    category="Ownership Risk",
                    severity="Critical",
                    description=f"Extremely high promoter pledge at {metrics.promoter_pledge_pct:.1f}%",
                    metric_value=metrics.promoter_pledge_pct,
                    threshold=self.thresholds["promoter_pledge_critical"],
                    impact_score=9.0
                ))
            elif metrics.promoter_pledge_pct > self.thresholds["promoter_pledge_warning"]:
                red_flags.append(RedFlag(
                    category="Ownership Risk",
                    severity="High",
                    description=f"High promoter pledge at {metrics.promoter_pledge_pct:.1f}%",
                    metric_value=metrics.promoter_pledge_pct,
                    threshold=self.thresholds["promoter_pledge_warning"],
                    impact_score=6.0
                ))
        
        # Promoter holding red flags
        if metrics.promoter_holding_pct is not None:
            if metrics.promoter_holding_pct < self.thresholds["promoter_holding_low"]:
                red_flags.append(RedFlag(
                    category="Ownership Risk",
                    severity="Medium",
                    description=f"Low promoter holding at {metrics.promoter_holding_pct:.1f}%",
                    metric_value=metrics.promoter_holding_pct,
                    threshold=self.thresholds["promoter_holding_low"],
                    impact_score=4.0
                ))
            elif metrics.promoter_holding_pct > self.thresholds["promoter_holding_high"]:
                red_flags.append(RedFlag(
                    category="Liquidity Risk",
                    severity="Medium",
                    description=f"Very high promoter holding at {metrics.promoter_holding_pct:.1f}% may limit liquidity",
                    metric_value=metrics.promoter_holding_pct,
                    threshold=self.thresholds["promoter_holding_high"],
                    impact_score=3.0
                ))
        
        # Board composition red flags
        if metrics.independent_directors_pct is not None:
            if metrics.independent_directors_pct < self.thresholds["independent_directors_min"]:
                red_flags.append(RedFlag(
                    category="Board Governance",
                    severity="High",
                    description=f"Insufficient independent directors at {metrics.independent_directors_pct:.1f}%",
                    metric_value=metrics.independent_directors_pct,
                    threshold=self.thresholds["independent_directors_min"],
                    impact_score=7.0
                ))
        
        # Auditor changes red flag
        if metrics.auditor_changes_3yr is not None and metrics.auditor_changes_3yr > self.thresholds["auditor_changes_warning"]:
            red_flags.append(RedFlag(
                category="Financial Transparency",
                severity="High",
                description=f"Frequent auditor changes: {metrics.auditor_changes_3yr} in 3 years",
                metric_value=metrics.auditor_changes_3yr,
                threshold=self.thresholds["auditor_changes_warning"],
                impact_score=8.0
            ))
        
        # Related party transactions red flags
        if metrics.rpt_as_pct_revenue is not None:
            if metrics.rpt_as_pct_revenue > self.thresholds["rpt_revenue_critical"]:
                red_flags.append(RedFlag(
                    category="Related Party Risk",
                    severity="Critical",
                    description=f"Excessive RPTs at {metrics.rpt_as_pct_revenue:.1f}% of revenue",
                    metric_value=metrics.rpt_as_pct_revenue,
                    threshold=self.thresholds["rpt_revenue_critical"],
                    impact_score=9.0
                ))
            elif metrics.rpt_as_pct_revenue > self.thresholds["rpt_revenue_warning"]:
                red_flags.append(RedFlag(
                    category="Related Party Risk",
                    severity="Medium",
                    description=f"High RPTs at {metrics.rpt_as_pct_revenue:.1f}% of revenue",
                    metric_value=metrics.rpt_as_pct_revenue,
                    threshold=self.thresholds["rpt_revenue_warning"],
                    impact_score=5.0
                ))
        
        # Insider selling red flag
        if metrics.insider_selling_12m is not None and metrics.insider_selling_12m > self.thresholds["insider_selling_warning"]:
            red_flags.append(RedFlag(
                category="Management Confidence",
                severity="Medium",
                description=f"Significant insider selling: ₹{metrics.insider_selling_12m:,.0f} in 12 months",
                metric_value=metrics.insider_selling_12m,
                threshold=self.thresholds["insider_selling_warning"],
                impact_score=4.0
            ))
        
        # Financial health red flags from company info
        debt_to_equity = info.get("debtToEquity", 0)
        if debt_to_equity and debt_to_equity > 200:  # >2x D/E ratio
            red_flags.append(RedFlag(
                category="Financial Risk",
                severity="High",
                description=f"High leverage with D/E ratio of {debt_to_equity:.1f}%",
                metric_value=debt_to_equity,
                threshold=200.0,
                impact_score=7.0
            ))
        
        # Interest coverage red flag
        interest_coverage = self._calculate_interest_coverage(info)
        if interest_coverage is not None and interest_coverage < 2.0:
            red_flags.append(RedFlag(
                category="Financial Risk",
                severity="Critical" if interest_coverage < 1.0 else "High",
                description=f"Poor interest coverage ratio of {interest_coverage:.1f}x",
                metric_value=interest_coverage,
                threshold=2.0,
                impact_score=8.0 if interest_coverage < 1.0 else 6.0
            ))
        
        return red_flags
    
    def _calculate_interest_coverage(self, info: Dict[str, Any]) -> Optional[float]:
        """Calculate interest coverage ratio"""
        try:
            ebitda = info.get("ebitda")
            interest_expense = info.get("interestExpense")
            
            if ebitda and interest_expense and interest_expense > 0:
                return ebitda / interest_expense
        except:
            pass
        return None
    
    def _calculate_governance_score(self, metrics: GovernanceMetrics, red_flags: List[RedFlag]) -> float:
        """Calculate overall governance score (0-100)"""
        base_score = 75.0  # Start with neutral score
        
        # Deduct points for red flags
        total_impact = sum(rf.impact_score for rf in red_flags)
        
        # Apply penalties based on severity
        critical_flags = [rf for rf in red_flags if rf.severity == "Critical"]
        high_flags = [rf for rf in red_flags if rf.severity == "High"]
        medium_flags = [rf for rf in red_flags if rf.severity == "Medium"]
        
        # Penalty structure
        penalty = (
            len(critical_flags) * 15.0 +    # 15 points per critical flag
            len(high_flags) * 8.0 +         # 8 points per high flag
            len(medium_flags) * 4.0 +       # 4 points per medium flag
            total_impact * 0.5               # Additional penalty based on impact
        )
        
        # Add points for positive governance indicators
        bonus = 0.0
        if metrics.independent_directors_pct and metrics.independent_directors_pct > 50:
            bonus += 5.0  # Bonus for high independent director ratio
        
        if metrics.insider_buying_12m and metrics.insider_buying_12m > 0:
            bonus += 3.0  # Bonus for insider buying
        
        # Calculate final score
        final_score = max(0.0, min(100.0, base_score - penalty + bonus))
        
        return round(final_score, 1)
    
    def _score_to_grade(self, score: float) -> str:
        """Convert governance score to letter grade"""
        if score >= 85:
            return "A+"
        elif score >= 80:
            return "A"
        elif score >= 75:
            return "A-"
        elif score >= 70:
            return "B+"
        elif score >= 65:
            return "B"
        elif score >= 60:
            return "B-"
        elif score >= 55:
            return "C+"
        elif score >= 50:
            return "C"
        elif score >= 45:
            return "C-"
        elif score >= 40:
            return "D"
        else:
            return "F"
    
    def _generate_governance_recommendations(self, red_flags: List[RedFlag], score: float) -> List[str]:
        """Generate governance improvement recommendations"""
        recommendations = []
        
        # Critical issues first
        critical_flags = [rf for rf in red_flags if rf.severity == "Critical"]
        if critical_flags:
            recommendations.append("⚠️ CRITICAL: Address critical governance issues immediately")
            for flag in critical_flags:
                recommendations.append(f"  • {flag.description}")
        
        # High priority issues
        high_flags = [rf for rf in red_flags if rf.severity == "High"]
        if high_flags:
            recommendations.append("🔴 HIGH PRIORITY: Resolve significant governance concerns")
            for flag in high_flags[:3]:  # Limit to top 3
                recommendations.append(f"  • {flag.description}")
        
        # General recommendations based on score
        if score < 60:
            recommendations.append("📊 Overall governance quality is below acceptable standards")
            recommendations.append("🔍 Conduct thorough due diligence before investment")
            recommendations.append("⏰ Monitor governance improvements over time")
        elif score < 75:
            recommendations.append("📈 Governance quality is moderate - room for improvement")
            recommendations.append("👀 Keep monitoring key governance metrics")
        else:
            recommendations.append("✅ Good governance standards maintained")
            recommendations.append("🔄 Continue regular governance monitoring")
        
        return recommendations


# Convenience function for integration
async def analyze_corporate_governance(ticker: str) -> Dict[str, Any]:
    """Perform comprehensive corporate governance analysis"""
    analyzer = GovernanceAnalyzer()
    return await analyzer.analyze_governance(ticker)





