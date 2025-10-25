"""
Institutional-Grade Report Formatter
Phase 1: Core Investment Framework - Professional Report Generation
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

from app.schemas.institutional_output import (
    InstitutionalTickerReport,
    InstitutionalResearchResponse,
    RecommendationType,
    ConvictionLevel,
    GradeLevel
)

logger = logging.getLogger(__name__)


class InstitutionalReportFormatter:
    """
    Professional formatter for institutional-grade equity research reports
    """
    
    def __init__(self):
        self.report_templates = {
            "investment_summary": self._format_investment_summary,
            "valuation_metrics": self._format_valuation_metrics,
            "horizon_analysis": self._format_horizon_analysis,
            "risk_assessment": self._format_risk_assessment,
            "professional_notes": self._format_professional_notes
        }
    
    def generate_markdown_report(
        self,
        institutional_response: InstitutionalResearchResponse,
        include_charts: bool = True,
        include_appendix: bool = True
    ) -> str:
        """
        Generate comprehensive institutional-grade Markdown report
        
        Args:
            institutional_response: Institutional research response
            include_charts: Whether to include chart placeholders
            include_appendix: Whether to include detailed appendix
            
        Returns:
            Formatted Markdown report
        """
        try:
            report_sections = []
            
            # Header
            report_sections.append(self._generate_header(institutional_response))
            
            # Executive Summary
            report_sections.append(self._generate_executive_summary_section(institutional_response))
            
            # Individual Ticker Reports
            for report in institutional_response.reports:
                report_sections.append(self._generate_ticker_report(report, include_charts))
            
            # Data Quality Summary
            report_sections.append(self._generate_data_quality_section(institutional_response))
            
            # Appendix
            if include_appendix:
                report_sections.append(self._generate_appendix(institutional_response))
            
            # Footer
            report_sections.append(self._generate_footer())
            
            return "\n\n".join(report_sections)
            
        except Exception as e:
            logger.error(f"Error generating markdown report: {str(e)}")
            return self._generate_error_report(str(e))
    
    def _generate_header(self, response: InstitutionalResearchResponse) -> str:
        """Generate report header"""
        timestamp = response.generated_at.strftime("%B %d, %Y at %I:%M %p")
        
        return f"""# Institutional Equity Research Report

**Generated:** {timestamp}  
**Analysis Framework:** {response.analysis_framework_version}  
**Tickers Analyzed:** {', '.join(response.tickers)}  
**Analyst:** {response.reports[0].analyst_name if response.reports else "Equisense AI Research"}

---

## Report Overview

This institutional-grade equity research report provides comprehensive analysis of {len(response.tickers)} stock{'s' if len(response.tickers) > 1 else ''} using advanced multi-dimensional analysis framework. The analysis incorporates fundamental, technical, sentiment, and governance factors to deliver professional investment recommendations suitable for institutional investors.

**Analysis Horizons:**
- **Short-term:** {response.analysis_horizon_short_days} days
- **Long-term:** {response.analysis_horizon_long_days} days

**Data Quality:** {response.data_quality_summary.get('overall_quality', 'Unknown')} ({response.data_quality_summary.get('average_confidence', 0):.1f}% confidence)

---
"""
    
    def _generate_executive_summary_section(self, response: InstitutionalResearchResponse) -> str:
        """Generate executive summary section"""
        summary_sections = []
        
        for report in response.reports:
            decision = report.decision
            summary_sections.append(f"""
### {report.ticker} - {report.company_name}

**Recommendation:** {decision.investment_summary.recommendation.value}  
**Grade:** {decision.investment_summary.letter_grade.value} ({decision.investment_summary.stars_rating})  
**Confidence:** {decision.investment_summary.confidence_score:.1f}/100  
**Conviction:** {decision.investment_summary.conviction_level.value}

**Executive Summary:**
{decision.investment_summary.executive_summary}

**Key Investment Thesis:**
{self._format_list_items(decision.investment_summary.key_investment_thesis)}

**Key Risks:**
{self._format_list_items(decision.investment_summary.key_risks)}
""")
        
        return f"""## Executive Summary

{''.join(summary_sections)}

---
"""
    
    def _generate_ticker_report(self, report: InstitutionalTickerReport, include_charts: bool) -> str:
        """Generate detailed ticker report"""
        sections = []
        
        # Investment Summary
        sections.append(self._format_investment_summary(report))
        
        # Valuation Metrics
        sections.append(self._format_valuation_metrics(report))
        
        # Horizon Analysis
        sections.append(self._format_horizon_analysis(report))
        
        # Risk Assessment
        sections.append(self._format_risk_assessment(report))
        
        # Professional Notes
        sections.append(self._format_professional_notes(report))
        
        # Charts placeholder
        if include_charts:
            sections.append(self._generate_charts_section(report))
        
        return f"""## {report.ticker} - {report.company_name}

**Sector:** {report.sector} | **Country:** {report.country} | **Exchange:** {report.exchange}

{''.join(sections)}

---
"""
    
    def _format_investment_summary(self, report: InstitutionalTickerReport) -> str:
        """Format investment summary section"""
        decision = report.decision
        summary = decision.investment_summary
        
        return f"""### Investment Summary

| Metric | Value |
|--------|-------|
| **Recommendation** | {summary.recommendation.value} |
| **Letter Grade** | {summary.letter_grade.value} |
| **Stars Rating** | {summary.stars_rating} |
| **Confidence Score** | {summary.confidence_score:.1f}/100 |
| **Conviction Level** | {summary.conviction_level.value} |
| **Quantitative Score** | {summary.quantitative_score:.1f}/100 |
| **Qualitative Score** | {summary.qualitative_score:.1f}/100 |
| **Data Quality** | {summary.data_quality_score:.1f}/100 |

**Professional Rationale:**
{summary.analyst_notes}

**Short-term Outlook (0-6 months):**
{decision.short_term_analysis.analyst_outlook}

**Long-term Outlook (12-36 months):**
{decision.long_term_analysis.analyst_outlook}
"""
    
    def _format_valuation_metrics(self, report: InstitutionalTickerReport) -> str:
        """Format valuation metrics section"""
        metrics = report.decision.valuation_metrics
        
        return f"""### Valuation Metrics

| Metric | Value |
|--------|-------|
| **Current Price** | {self._format_currency(metrics.current_price)} |
| **Market Cap** | {self._format_currency(metrics.market_cap)} |
| **Analyst Consensus Target** | {self._format_currency(metrics.analyst_consensus_target)} |
| **DCF Intrinsic Value (Base)** | {self._format_currency(metrics.dcf_intrinsic_value_base)} |
| **DCF Intrinsic Value (Bear)** | {self._format_currency(metrics.dcf_intrinsic_value_bear)} |
| **DCF Intrinsic Value (Bull)** | {self._format_currency(metrics.dcf_intrinsic_value_bull)} |
| **Expected Return (Short-term)** | {self._format_percentage(metrics.expected_return_short_term)} |
| **Expected Return (Long-term)** | {self._format_percentage(metrics.expected_return_long_term)} |
| **Upside vs Intrinsic** | {self._format_percentage(metrics.upside_vs_intrinsic)} |
| **Upside vs Consensus** | {self._format_percentage(metrics.upside_vs_consensus)} |
| **Valuation Attractiveness** | {metrics.valuation_attractiveness} |

**Trading Levels:**
- **Entry Zone:** {self._format_currency(metrics.entry_zone_low)} - {self._format_currency(metrics.entry_zone_high)}
- **Target Price:** {self._format_currency(metrics.target_price)}
- **Stop Loss:** {self._format_currency(metrics.stop_loss)}
"""
    
    def _format_horizon_analysis(self, report: InstitutionalTickerReport) -> str:
        """Format horizon analysis section"""
        decision = report.decision
        
        return f"""### Time Horizon Analysis

#### Short-term Analysis ({decision.short_term_analysis.horizon.value})
- **Recommendation:** {decision.short_term_analysis.recommendation.value}
- **Confidence:** {decision.short_term_analysis.confidence_score:.1f}/100
- **Expected Return:** {self._format_percentage(decision.short_term_analysis.expected_return)}
- **Success Probability:** {decision.short_term_analysis.probability_of_success:.1f}%

**Primary Drivers:**
{self._format_list_items(decision.short_term_analysis.primary_drivers)}

**Key Catalysts:**
{self._format_list_items(decision.short_term_analysis.key_catalysts)}

**Risk Factors:**
{self._format_list_items(decision.short_term_analysis.risk_factors)}

**Key Monitoring Points:**
{self._format_list_items(decision.short_term_analysis.key_monitoring_points)}

#### Long-term Analysis ({decision.long_term_analysis.horizon.value})
- **Recommendation:** {decision.long_term_analysis.recommendation.value}
- **Confidence:** {decision.long_term_analysis.confidence_score:.1f}/100
- **Expected Return:** {self._format_percentage(decision.long_term_analysis.expected_return)}
- **Success Probability:** {decision.long_term_analysis.probability_of_success:.1f}%

**Primary Drivers:**
{self._format_list_items(decision.long_term_analysis.primary_drivers)}

**Key Catalysts:**
{self._format_list_items(decision.long_term_analysis.key_catalysts)}

**Risk Factors:**
{self._format_list_items(decision.long_term_analysis.risk_factors)}

**Key Monitoring Points:**
{self._format_list_items(decision.long_term_analysis.key_monitoring_points)}
"""
    
    def _format_risk_assessment(self, report: InstitutionalTickerReport) -> str:
        """Format risk assessment section"""
        decision = report.decision
        
        return f"""### Risk Assessment

| Risk Category | Assessment |
|---------------|------------|
| **Overall Risk Rating** | {decision.overall_risk_rating} |
| **Position Sizing** | {decision.position_sizing_recommendation} |
| **Sector Outlook** | {decision.sector_outlook} |
| **Market Regime** | {decision.market_regime} |

**Key Risk Factors:**
{self._format_list_items(report.decision.investment_summary.key_risks)}

**Risk Mitigation Strategies:**
- Monitor key technical levels and support/resistance zones
- Track fundamental metrics and earnings quality
- Stay informed on sector and macro developments
- Maintain appropriate position sizing based on conviction level
"""
    
    def _format_professional_notes(self, report: InstitutionalTickerReport) -> str:
        """Format professional notes section"""
        return f"""### Professional Notes

**Analyst:** {report.analyst_name}  
**Report Version:** {report.report_version}  
**Generated:** {report.report_generated_at.strftime("%B %d, %Y at %I:%M %p")}  
**Data Sources:** {', '.join(report.data_sources)}

**Compliance Notes:**
{report.decision.compliance_notes}

**Disclaimer:**
{report.decision.disclaimer}
"""
    
    def _generate_charts_section(self, report: InstitutionalTickerReport) -> str:
        """Generate charts section placeholder"""
        return f"""### Charts and Visualizations

*Note: Interactive charts and visualizations would be displayed here in the web interface.*

**Available Charts:**
- Price and Volume Analysis
- Technical Indicators (RSI, MACD, Bollinger Bands)
- Fundamental Metrics Trends
- Peer Comparison Charts
- Valuation Analysis Charts
- Risk-Return Scatter Plot

**Export Formats:** {', '.join(report.export_formats)}
"""
    
    def _generate_data_quality_section(self, response: InstitutionalResearchResponse) -> str:
        """Generate data quality summary section"""
        quality = response.data_quality_summary
        
        return f"""## Data Quality Summary

| Metric | Value |
|--------|-------|
| **Overall Quality** | {quality.get('overall_quality', 'Unknown')} |
| **Average Confidence** | {quality.get('average_confidence', 0):.1f}% |
| **Tickers Analyzed** | {quality.get('tickers_analyzed', 0)} |
| **Data Completeness** | {quality.get('data_completeness', 'Unknown')} |

**Data Sources Used:**
- Yahoo Finance (Fundamentals, Price Data)
- News APIs (Sentiment Analysis)
- Technical Analysis Libraries
- Analyst Recommendation Databases
- Sector and Macro Data Providers

---
"""
    
    def _generate_appendix(self, response: InstitutionalResearchResponse) -> str:
        """Generate detailed appendix"""
        return f"""## Appendix

### Methodology

This institutional-grade analysis employs a comprehensive multi-dimensional framework:

1. **Fundamental Analysis:** Financial metrics, ratios, and business quality assessment
2. **Technical Analysis:** Price patterns, momentum indicators, and trend analysis
3. **Sentiment Analysis:** News sentiment, social media analysis, and market psychology
4. **Valuation Analysis:** DCF modeling, relative valuation, and scenario analysis
5. **Risk Assessment:** Quantitative and qualitative risk factor analysis
6. **Governance Analysis:** Management quality, corporate governance, and ESG factors

### Horizon-Specific Weighting

**Short-term Analysis (0-6 months):**
- Technical Analysis: 40%
- Sentiment Analysis: 30%
- Fundamentals: 20%
- Growth Prospects: 10%

**Long-term Analysis (18+ months):**
- Fundamentals: 40%
- Growth Prospects: 40%
- Technical Analysis: 10%
- Sentiment Analysis: 10%

### Confidence Scoring

Confidence scores are calculated based on:
- Data availability and quality
- Analysis consistency across multiple sources
- Historical accuracy of similar analyses
- Market condition stability

### Export Capabilities

**Available Formats:**
{', '.join(response.available_exports)}

**Usage Rights:** This report is for informational purposes only and does not constitute investment advice.

---
"""
    
    def _generate_footer(self) -> str:
        """Generate report footer"""
        return f"""## Contact Information

**Equisense AI Research**  
Advanced Equity Research Platform  
Generated on {datetime.now().strftime("%B %d, %Y")}

---

*This report was generated using institutional-grade analysis framework. Past performance does not guarantee future results. Please consult with a qualified financial advisor before making investment decisions.*
"""
    
    def _format_list_items(self, items: List[str]) -> str:
        """Format list items for Markdown"""
        if not items:
            return "- No items available"
        
        return "\n".join([f"- {item}" for item in items])
    
    def _format_currency(self, value: Optional[float]) -> str:
        """Format currency values"""
        if value is None:
            return "N/A"
        return f"${value:,.2f}"
    
    def _format_percentage(self, value: Optional[float]) -> str:
        """Format percentage values"""
        if value is None:
            return "N/A"
        return f"{value:.1f}%"
    
    def _generate_error_report(self, error_message: str) -> str:
        """Generate error report when formatting fails"""
        return f"""# Institutional Equity Research Report - Error

**Error:** {error_message}

**Timestamp:** {datetime.now().strftime("%B %d, %Y at %I:%M %p")}

Please retry the analysis or contact support if the issue persists.

---
"""
    
    def export_to_file(
        self,
        institutional_response: InstitutionalResearchResponse,
        output_path: str,
        format_type: str = "markdown"
    ) -> bool:
        """
        Export institutional report to file
        
        Args:
            institutional_response: Institutional research response
            output_path: Output file path
            format_type: Export format (markdown, csv, json)
            
        Returns:
            Success status
        """
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            if format_type.lower() == "markdown":
                content = self.generate_markdown_report(institutional_response)
                output_file.write_text(content, encoding='utf-8')
            elif format_type.lower() == "json":
                import json
                content = institutional_response.model_dump_json(indent=2)
                output_file.write_text(content, encoding='utf-8')
            else:
                logger.error(f"Unsupported format: {format_type}")
                return False
            
            logger.info(f"Successfully exported report to {output_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error exporting report: {str(e)}")
            return False


# Global instance
institutional_formatter = InstitutionalReportFormatter()
