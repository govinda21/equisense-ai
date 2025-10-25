"""
Enhanced API Endpoints for Institutional Analysis
Phase 1: Core Investment Framework Integration
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, HTTPException, Request, Body
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.config import AppSettings, get_settings
from app.schemas.input import ResearchRequest
from app.schemas.institutional_output import InstitutionalResearchResponse
from app.tools.institutional_formatter import institutional_formatter
from app.graph.workflow import build_research_graph
from app.utils.async_utils import monitor_performance

logger = logging.getLogger(__name__)

# Create router for institutional endpoints
institutional_router = APIRouter(prefix="/api/institutional", tags=["institutional"])


class InstitutionalAnalysisRequest(BaseModel):
    """Enhanced request model for institutional analysis"""
    tickers: List[str] = Field(..., description="List of stock tickers to analyze")
    horizon_short_days: int = Field(default=180, ge=30, le=365, description="Short-term horizon in days")
    horizon_long_days: int = Field(default=1095, ge=365, le=2190, description="Long-term horizon in days")
    include_charts: bool = Field(default=True, description="Include chart placeholders in report")
    include_appendix: bool = Field(default=True, description="Include detailed appendix")
    export_format: str = Field(default="markdown", description="Export format (markdown, json, csv)")
    generate_report: bool = Field(default=True, description="Generate formatted report")


@institutional_router.post("/analyze")
async def institutional_analyze(
    request: InstitutionalAnalysisRequest,
    settings: AppSettings = get_settings()
) -> JSONResponse:
    """
    Enhanced institutional-grade stock analysis endpoint
    
    Provides comprehensive analysis suitable for institutional investors including:
    - Professional investment recommendations with confidence scores
    - Horizon-specific analysis (short-term vs long-term)
    - Comprehensive valuation metrics
    - Risk assessment and position sizing recommendations
    - Professional report formatting
    """
    start_time = time.time()
    
    try:
        logger.info(f"Starting institutional analysis for {request.tickers}")
        
        # Build research graph with enhanced synthesis
        graph = build_research_graph(settings)
        
        # Prepare research state
        research_state = {
            "tickers": request.tickers,
            "horizon_short_days": request.horizon_short_days,
            "horizon_long_days": request.horizon_long_days,
            "analysis_type": "institutional",
            "include_charts": request.include_charts,
            "include_appendix": request.include_appendix
        }
        
        # Execute analysis with performance monitoring
        with monitor_performance("institutional_analysis"):
            result = await graph.ainvoke(research_state)
        
        # Extract institutional output
        institutional_output = result.get("institutional_output")
        
        if not institutional_output:
            logger.warning("No institutional output found, falling back to legacy format")
            # Fallback to legacy format
            legacy_output = result.get("final_output", {})
            return JSONResponse(content={
                "status": "success",
                "message": "Analysis completed (legacy format)",
                "data": legacy_output,
                "analysis_type": "legacy",
                "processing_time": time.time() - start_time
            })
        
        # Generate formatted report if requested
        formatted_report = None
        if request.generate_report and request.export_format.lower() == "markdown":
            try:
                formatted_report = institutional_formatter.generate_markdown_report(
                    institutional_output,
                    include_charts=request.include_charts,
                    include_appendix=request.include_appendix
                )
            except Exception as e:
                logger.error(f"Error generating formatted report: {str(e)}")
                formatted_report = f"Error generating report: {str(e)}"
        
        # Prepare response
        response_data = {
            "status": "success",
            "message": "Institutional analysis completed successfully",
            "analysis_type": "institutional",
            "processing_time": time.time() - start_time,
            "data": {
                "institutional_response": institutional_output.model_dump(),
                "formatted_report": formatted_report,
                "export_formats": ["markdown", "json", "csv"],
                "data_quality": institutional_output.data_quality_summary
            },
            "metadata": {
                "tickers_analyzed": len(request.tickers),
                "horizon_short_days": request.horizon_short_days,
                "horizon_long_days": request.horizon_long_days,
                "framework_version": institutional_output.analysis_framework_version,
                "generated_at": institutional_output.generated_at.isoformat()
            }
        }
        
        logger.info(f"Institutional analysis completed for {request.tickers} in {time.time() - start_time:.2f}s")
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"Error in institutional analysis: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "message": f"Institutional analysis failed: {str(e)}",
                "analysis_type": "institutional",
                "processing_time": time.time() - start_time
            }
        )


@institutional_router.post("/export")
async def export_institutional_report(
    request: InstitutionalAnalysisRequest,
    settings: AppSettings = get_settings()
) -> StreamingResponse:
    """
    Export institutional analysis report to file
    
    Supports multiple export formats:
    - Markdown (.md) - Professional formatted report
    - JSON (.json) - Structured data export
    - CSV (.csv) - Tabular data export
    """
    try:
        logger.info(f"Exporting institutional report for {request.tickers}")
        
        # Perform analysis first
        analysis_response = await institutional_analyze(request, settings)
        analysis_data = analysis_response.body
        
        if analysis_data.get("status") != "success":
            raise HTTPException(status_code=500, detail="Analysis failed")
        
        # Extract institutional response
        institutional_data = analysis_data["data"]["institutional_response"]
        
        # Generate export content based on format
        export_format = request.export_format.lower()
        
        if export_format == "markdown":
            content = analysis_data["data"]["formatted_report"]
            media_type = "text/markdown"
            filename = f"institutional_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        elif export_format == "json":
            import json
            content = json.dumps(institutional_data, indent=2)
            media_type = "application/json"
            filename = f"institutional_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        elif export_format == "csv":
            # Generate CSV from institutional data
            content = _generate_csv_export(institutional_data)
            media_type = "text/csv"
            filename = f"institutional_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported export format: {export_format}")
        
        # Return streaming response
        return StreamingResponse(
            iter([content]),
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Error exporting institutional report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")


@institutional_router.get("/formats")
async def get_export_formats() -> JSONResponse:
    """Get available export formats for institutional reports"""
    return JSONResponse(content={
        "available_formats": [
            {
                "format": "markdown",
                "description": "Professional formatted report with charts and analysis",
                "extension": ".md",
                "media_type": "text/markdown"
            },
            {
                "format": "json",
                "description": "Structured data export with all analysis details",
                "extension": ".json",
                "media_type": "application/json"
            },
            {
                "format": "csv",
                "description": "Tabular data export for spreadsheet analysis",
                "extension": ".csv",
                "media_type": "text/csv"
            }
        ],
        "default_format": "markdown"
    })


@institutional_router.get("/health")
async def institutional_health_check() -> JSONResponse:
    """Health check for institutional analysis service"""
    try:
        # Check if institutional components are available
        from app.tools.institutional_analysis import institutional_engine
        from app.tools.horizon_filtering import horizon_engine
        from app.tools.institutional_formatter import institutional_formatter
        
        return JSONResponse(content={
            "status": "healthy",
            "service": "institutional_analysis",
            "components": {
                "institutional_engine": "available",
                "horizon_engine": "available",
                "formatter": "available"
            },
            "timestamp": datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Institutional health check failed: {str(e)}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "service": "institutional_analysis",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
        )


def _generate_csv_export(institutional_data: Dict[str, Any]) -> str:
    """Generate CSV export from institutional data"""
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow([
        "Ticker", "Company", "Sector", "Recommendation", "Grade", "Confidence",
        "Conviction", "Current_Price", "Target_Price", "Expected_Return_Short",
        "Expected_Return_Long", "Upside_vs_Intrinsic", "Risk_Rating"
    ])
    
    # Write data rows
    reports = institutional_data.get("reports", [])
    for report in reports:
        decision = report.get("decision", {})
        investment_summary = decision.get("investment_summary", {})
        valuation_metrics = decision.get("valuation_metrics", {})
        
        writer.writerow([
            report.get("ticker", ""),
            report.get("company_name", ""),
            report.get("sector", ""),
            investment_summary.get("recommendation", ""),
            investment_summary.get("letter_grade", ""),
            investment_summary.get("confidence_score", ""),
            investment_summary.get("conviction_level", ""),
            valuation_metrics.get("current_price", ""),
            valuation_metrics.get("analyst_consensus_target", ""),
            valuation_metrics.get("expected_return_short_term", ""),
            valuation_metrics.get("expected_return_long_term", ""),
            valuation_metrics.get("upside_vs_intrinsic", ""),
            decision.get("overall_risk_rating", "")
        ])
    
    return output.getvalue()


# Export router
__all__ = ["institutional_router"]
