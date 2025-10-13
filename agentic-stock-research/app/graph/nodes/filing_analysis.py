"""
Filing Analysis Node

Analyzes regulatory filings (SEC, BSE, NSE) to extract insights
about company operations, risks, and management strategy.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.sec_edgar import (
    get_recent_sec_filings,
    compare_consecutive_filings,
    FilingType
)
from app.tools.bse_nse_filings import analyze_indian_filings
from app.utils.retry import retry_async, RetryError

logger = logging.getLogger(__name__)


async def filing_analysis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    """
    Analyze regulatory filings to extract insights
    
    Processes:
    1. Recent SEC filings (10-K, 10-Q, 8-K) for US tickers
    2. BSE/NSE filings for Indian tickers (if available)
    3. Extract key sections and changes
    4. Identify new risks or concerns
    5. Summarize management commentary
    """
    ticker = state["tickers"][0]
    logger.info(f"Starting filing analysis for {ticker}")
    
    try:
        # Determine market (US vs Indian)
        is_indian_stock = ticker.endswith(('.NS', '.BO'))
        
        filing_data = {
            "ticker": ticker,
            "market": "India" if is_indian_stock else "US",
            "filings_analyzed": 0,
            "recent_filings": [],
            "key_insights": [],
            "risk_factor_changes": [],
            "management_commentary": "",
            "filing_dates": []
        }
        
        if is_indian_stock:
            # Indian market filings - use BSE/NSE analysis
            logger.info(f"Analyzing Indian market filings for {ticker}")
            filing_data = await _analyze_indian_filings(ticker, filing_data)
        else:
            # US market - use SEC Edgar
            filing_data = await _analyze_us_sec_filings(ticker, filing_data)
        
        # Add to state
        if "analysis" not in state:
            state["analysis"] = {}
        
        state["analysis"]["filings"] = filing_data
        
        logger.info(f"Filing analysis complete for {ticker}: {filing_data.get('filings_analyzed', 0)} filings analyzed")
        
        return state
    
    except Exception as e:
        logger.error(f"Filing analysis failed for {ticker}: {e}", exc_info=True)
        
        # Add error info to state but don't fail the workflow
        if "analysis" not in state:
            state["analysis"] = {}
        
        state["analysis"]["filings"] = {
            "ticker": ticker,
            "error": str(e),
            "status": "failed"
        }
        
        return state


@retry_async(max_retries=3, base_delay=2.0, backoff_factor=2.0, exceptions=(Exception,))
async def _fetch_sec_filings_with_retry(ticker: str) -> List[Any]:
    """Fetch SEC filings with retry logic"""
    return await get_recent_sec_filings(
        ticker=ticker,
        filing_types=[FilingType.FORM_10K, FilingType.FORM_10Q, FilingType.FORM_8K],
        count=2,  # 2 of each type
        include_content=True
    )


async def _analyze_us_sec_filings(ticker: str, filing_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze SEC filings for US companies with robust error handling"""
    try:
        # Get recent 10-K, 10-Q, and 8-K filings with retry
        logger.info(f"Fetching recent SEC filings for {ticker}")
        
        try:
            filings = await _fetch_sec_filings_with_retry(ticker)
        except RetryError as e:
            logger.error(f"Failed to fetch SEC filings after retries for {ticker}: {e}")
            filing_data["status"] = "fetch_failed"
            filing_data["error"] = f"All retry attempts exhausted: {str(e)}"
            return filing_data
        
        if not filings:
            logger.warning(f"No SEC filings found for {ticker}")
            filing_data["status"] = "no_filings_found"
            return filing_data
        
        # Process filings
        filing_data["filings_analyzed"] = len(filings)
        filing_data["status"] = "success"
        
        # Extract filing summaries
        for filing in filings:
            filing_summary = {
                "type": filing.filing_type.value,
                "filing_date": filing.filing_date.strftime("%Y-%m-%d"),
                "report_date": filing.report_date.strftime("%Y-%m-%d"),
                "url": filing.url,
                "executive_summary": filing.executive_summary or "N/A",
                "key_points": filing.key_points or []
            }
            filing_data["recent_filings"].append(filing_summary)
            filing_data["filing_dates"].append(filing.filing_date.strftime("%Y-%m-%d"))
        
        # Extract key insights from most recent 10-K/10-Q
        most_recent_annual = next((f for f in filings if f.filing_type == FilingType.FORM_10K), None)
        most_recent_quarterly = next((f for f in filings if f.filing_type == FilingType.FORM_10Q), None)
        
        if most_recent_annual and most_recent_annual.key_points:
            filing_data["key_insights"].extend(most_recent_annual.key_points[:3])
        
        if most_recent_quarterly and most_recent_quarterly.key_points:
            filing_data["key_insights"].extend(most_recent_quarterly.key_points[:2])
        
        # Analyze risk factor changes (compare consecutive 10-Ks) with timeout protection
        try:
            logger.info(f"Comparing consecutive 10-K filings for {ticker}")
            
            # Add timeout to prevent hanging
            comparison = await asyncio.wait_for(
                compare_consecutive_filings(ticker, FilingType.FORM_10K),
                timeout=30.0  # 30 second timeout
            )
            
            if comparison:
                filing_data["risk_factor_changes"] = comparison.risk_factor_changes
                
                if comparison.new_risks:
                    filing_data["new_risks"] = [r.strip() for r in comparison.new_risks if r.strip()]
                
                if comparison.removed_risks:
                    filing_data["removed_risks"] = [r.strip() for r in comparison.removed_risks if r.strip()]
        
        except asyncio.TimeoutError:
            logger.warning(f"Filing comparison timed out for {ticker}")
            filing_data["comparison_status"] = "timeout"
        except Exception as e:
            logger.warning(f"Could not compare filings for {ticker}: {e}")
            filing_data["comparison_status"] = "failed"
        
        # Extract management commentary from MD&A
        if most_recent_annual and most_recent_annual.md_and_a:
            # Take first 500 characters as summary
            filing_data["management_commentary"] = most_recent_annual.md_and_a[:500].strip() + "..."
        elif most_recent_quarterly and most_recent_quarterly.md_and_a:
            filing_data["management_commentary"] = most_recent_quarterly.md_and_a[:500].strip() + "..."
        
        return filing_data
    
    except Exception as e:
        logger.error(f"Error analyzing US SEC filings for {ticker}: {e}")
        filing_data["status"] = "error"
        filing_data["error"] = str(e)
        return filing_data


@retry_async(max_retries=2, base_delay=3.0, backoff_factor=2.0, exceptions=(Exception,))
async def _fetch_indian_filings_with_retry(ticker: str, days_back: int = 90) -> Dict[str, Any]:
    """Fetch Indian filings with retry logic"""
    return await analyze_indian_filings(ticker, days_back=days_back)


async def _analyze_indian_filings(ticker: str, filing_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze Indian regulatory filings (BSE/NSE) with robust error handling"""
    try:
        # Remove .NS/.BO suffix for analysis
        clean_ticker = ticker.replace('.NS', '').replace('.BO', '')
        
        logger.info(f"Fetching Indian regulatory filings for {clean_ticker}")
        
        # Get comprehensive Indian filing analysis with retry and timeout
        try:
            indian_analysis = await asyncio.wait_for(
                _fetch_indian_filings_with_retry(clean_ticker, days_back=90),
                timeout=45.0  # 45 second timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Indian filing fetch timed out for {ticker}")
            filing_data["status"] = "timeout"
            filing_data["error"] = "Request timed out after 45 seconds"
            return filing_data
        except RetryError as e:
            logger.error(f"Failed to fetch Indian filings after retries for {ticker}: {e}")
            filing_data["status"] = "fetch_failed"
            filing_data["error"] = f"All retry attempts exhausted: {str(e)}"
            return filing_data
        
        if indian_analysis.get("error"):
            logger.warning(f"Indian filing analysis error for {ticker}: {indian_analysis['error']}")
            filing_data["status"] = "error"
            filing_data["error"] = indian_analysis["error"]
            return filing_data
        
        # Update filing data with Indian analysis results
        filing_data["filings_analyzed"] = indian_analysis.get("total_filings", 0)
        filing_data["status"] = "success"
        
        # Process recent developments
        recent_developments = indian_analysis.get("recent_developments", [])
        for dev in recent_developments[:10]:  # Top 10 recent developments
            filing_summary = {
                "type": dev.get("type", "corporate_announcement"),
                "filing_date": dev.get("date", ""),
                "title": dev.get("title", ""),
                "exchange": dev.get("exchange", "BSE/NSE"),
                "executive_summary": f"Indian regulatory filing: {dev.get('title', '')}",
                "key_points": [dev.get("title", "")]
            }
            filing_data["recent_filings"].append(filing_summary)
            filing_data["filing_dates"].append(dev.get("date", ""))
        
        # Extract key insights from filing summary
        filing_summary = indian_analysis.get("filing_summary", {})
        key_insights = []
        
        if filing_summary.get("annual_report", 0) > 0:
            key_insights.append(f"Annual report available ({filing_summary['annual_report']} filing(s))")
        
        if filing_summary.get("quarterly_results", 0) > 0:
            key_insights.append(f"Quarterly results available ({filing_summary['quarterly_results']} filing(s))")
        
        if filing_summary.get("corporate_announcement", 0) > 0:
            key_insights.append(f"Corporate announcements ({filing_summary['corporate_announcement']} filing(s))")
        
        filing_data["key_insights"] = key_insights
        
        # Extract management commentary
        management_commentary = indian_analysis.get("management_commentary", "")
        if management_commentary:
            filing_data["management_commentary"] = management_commentary[:500] + "..." if len(management_commentary) > 500 else management_commentary
        
        # Extract risk factors
        risk_factors = indian_analysis.get("risk_factors", [])
        filing_data["risk_factor_changes"] = risk_factors[:5]  # Top 5 risk factors
        
        # Add Indian-specific metadata
        filing_data["indian_analysis"] = {
            "filing_summary": filing_summary,
            "key_metrics": indian_analysis.get("key_metrics", {}),
            "analysis_date": indian_analysis.get("analysis_date", "")
        }
        
        logger.info(f"Indian filing analysis complete for {ticker}: {filing_data['filings_analyzed']} filings analyzed")
        
        return filing_data
    
    except Exception as e:
        logger.error(f"Error analyzing Indian filings for {ticker}: {e}")
        filing_data["status"] = "error"
        filing_data["error"] = str(e)
        return filing_data


# Optional: Add to existing comprehensive fundamentals node
# This would require modifying the workflow to include filing analysis

async def get_filing_insights(ticker: str) -> Dict[str, Any]:
    """
    Convenience function to get filing insights without full workflow
    
    Args:
        ticker: Stock ticker symbol
    
    Returns:
        Dictionary with filing analysis results
    """
    mock_state = {
        "tickers": [ticker],
        "analysis": {}
    }
    
    mock_settings = None  # Not used currently
    
    result_state = await filing_analysis_node(mock_state, mock_settings)
    
    return result_state.get("analysis", {}).get("filings", {})

