"""Filing Analysis Node - analyzes SEC, BSE, NSE regulatory filings."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from app.config import AppSettings
from app.graph.state import ResearchState
from app.tools.sec_edgar import get_recent_sec_filings, compare_consecutive_filings, FilingType
from app.tools.bse_nse_filings import analyze_indian_filings
from app.utils.retry import retry_async, RetryError

logger = logging.getLogger(__name__)


@retry_async(max_retries=3, base_delay=2.0, backoff_factor=2.0, exceptions=(Exception,))
async def _fetch_sec_filings(ticker: str) -> List[Any]:
    return await get_recent_sec_filings(
        ticker=ticker,
        filing_types=[FilingType.FORM_10K, FilingType.FORM_10Q, FilingType.FORM_8K],
        count=2, include_content=True
    )


@retry_async(max_retries=2, base_delay=3.0, backoff_factor=2.0, exceptions=(Exception,))
async def _fetch_indian_filings(ticker: str, days_back: int = 90) -> Dict[str, Any]:
    return await analyze_indian_filings(ticker, days_back=days_back)


async def _analyze_us_sec_filings(ticker: str, filing_data: Dict) -> Dict:
    try:
        try:
            filings = await _fetch_sec_filings(ticker)
        except RetryError as e:
            filing_data.update({"status": "fetch_failed", "error": str(e)})
            return filing_data

        if not filings:
            filing_data["status"] = "no_filings_found"
            return filing_data

        filing_data.update({"filings_analyzed": len(filings), "status": "success"})
        for f in filings:
            filing_data["recent_filings"].append({
                "type": f.filing_type.value,
                "filing_date": f.filing_date.strftime("%Y-%m-%d"),
                "report_date": f.report_date.strftime("%Y-%m-%d"),
                "url": f.url,
                "executive_summary": f.executive_summary or "N/A",
                "key_points": f.key_points or [],
            })
            filing_data["filing_dates"].append(f.filing_date.strftime("%Y-%m-%d"))

        annual = next((f for f in filings if f.filing_type == FilingType.FORM_10K), None)
        quarterly = next((f for f in filings if f.filing_type == FilingType.FORM_10Q), None)
        if annual and annual.key_points:
            filing_data["key_insights"].extend(annual.key_points[:3])
        if quarterly and quarterly.key_points:
            filing_data["key_insights"].extend(quarterly.key_points[:2])

        try:
            comparison = await asyncio.wait_for(
                compare_consecutive_filings(ticker, FilingType.FORM_10K), timeout=30.0
            )
            if comparison:
                filing_data["risk_factor_changes"] = comparison.risk_factor_changes
                if comparison.new_risks:
                    filing_data["new_risks"] = [r.strip() for r in comparison.new_risks if r.strip()]
                if comparison.removed_risks:
                    filing_data["removed_risks"] = [r.strip() for r in comparison.removed_risks if r.strip()]
        except asyncio.TimeoutError:
            filing_data["comparison_status"] = "timeout"
        except Exception as e:
            filing_data["comparison_status"] = "failed"

        source = annual or quarterly
        if source and source.md_and_a:
            filing_data["management_commentary"] = source.md_and_a[:500].strip() + "..."
    except Exception as e:
        filing_data.update({"status": "error", "error": str(e)})
    return filing_data


async def _analyze_indian_filings(ticker: str, filing_data: Dict) -> Dict:
    clean_ticker = ticker.replace(".NS", "").replace(".BO", "")
    try:
        try:
            analysis = await asyncio.wait_for(_fetch_indian_filings(clean_ticker), timeout=45.0)
        except asyncio.TimeoutError:
            filing_data.update({"status": "timeout", "error": "Request timed out after 45s"})
            return filing_data
        except RetryError as e:
            filing_data.update({"status": "fetch_failed", "error": str(e)})
            return filing_data

        if analysis.get("error"):
            filing_data.update({"status": "error", "error": analysis["error"]})
            return filing_data

        filing_data.update({"filings_analyzed": analysis.get("total_filings", 0), "status": "success"})
        for dev in analysis.get("recent_developments", [])[:10]:
            filing_data["recent_filings"].append({
                "type": dev.get("type", "corporate_announcement"),
                "filing_date": dev.get("date", ""),
                "title": dev.get("title", ""),
                "exchange": dev.get("exchange", "BSE/NSE"),
                "executive_summary": f"Indian regulatory filing: {dev.get('title', '')}",
                "key_points": [dev.get("title", "")],
            })
            filing_data["filing_dates"].append(dev.get("date", ""))

        fs = analysis.get("filing_summary", {})
        insights = []
        for key, label in [("annual_report", "Annual report"), ("quarterly_results", "Quarterly results"),
                           ("corporate_announcement", "Corporate announcements")]:
            if fs.get(key, 0) > 0:
                insights.append(f"{label} available ({fs[key]} filing(s))")
        filing_data["key_insights"] = insights

        mc = analysis.get("management_commentary", "")
        if mc:
            filing_data["management_commentary"] = mc[:500] + ("..." if len(mc) > 500 else "")
        filing_data["risk_factor_changes"] = analysis.get("risk_factors", [])[:5]
        filing_data["indian_analysis"] = {
            "filing_summary": fs,
            "key_metrics": analysis.get("key_metrics", {}),
            "analysis_date": analysis.get("analysis_date", ""),
        }
    except Exception as e:
        filing_data.update({"status": "error", "error": str(e)})
    return filing_data


async def filing_analysis_node(state: ResearchState, settings: AppSettings) -> ResearchState:
    ticker = state["tickers"][0]
    is_indian = ticker.endswith((".NS", ".BO"))
    filing_data: Dict[str, Any] = {
        "ticker": ticker, "market": "India" if is_indian else "US",
        "filings_analyzed": 0, "recent_filings": [], "key_insights": [],
        "risk_factor_changes": [], "management_commentary": "", "filing_dates": [],
    }
    try:
        if is_indian:
            filing_data = await _analyze_indian_filings(ticker, filing_data)
        else:
            filing_data = await _analyze_us_sec_filings(ticker, filing_data)
        state.setdefault("analysis", {})["filings"] = filing_data
    except Exception as e:
        logger.error(f"Filing analysis failed for {ticker}: {e}", exc_info=True)
        state.setdefault("analysis", {})["filings"] = {"ticker": ticker, "error": str(e), "status": "failed"}
    return state


async def get_filing_insights(ticker: str) -> Dict[str, Any]:
    result = await filing_analysis_node({"tickers": [ticker], "analysis": {}}, None)
    return result.get("analysis", {}).get("filings", {})
