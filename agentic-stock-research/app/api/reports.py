"""
API endpoints for report generation and export
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import io

from app.reporting.pdf_generator import ReportBuilder, get_report_generator
from app.schemas.output import TickerReport

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


# Pydantic models for API requests/responses
class ReportRequest(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    include_sections: List[str] = Field(default_factory=lambda: [
        "executive_summary", "fundamentals", "technicals", "sentiment", "recommendation"
    ])
    include_charts: bool = True
    format: str = "pdf"  # pdf, html, json


class ReportResponse(BaseModel):
    report_id: str
    ticker: str
    company_name: str
    generated_at: datetime
    format: str
    size_bytes: int
    download_url: Optional[str] = None


class ExportRequest(BaseModel):
    ticker: str
    data: Dict[str, Any]
    format: str = "csv"  # csv, xlsx, json
    filename: Optional[str] = None


@router.get("/health")
async def health_check():
    """Health check for reporting system"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "services": {
            "pdf_generator": "active",
            "export_service": "active"
        }
    }


@router.post("/generate", response_model=ReportResponse)
async def generate_report(request: ReportRequest, background_tasks: BackgroundTasks):
    """Generate a comprehensive PDF report for a ticker"""
    try:
        # Create report builder
        builder = ReportBuilder()
        
        # Set metadata
        company_name = request.company_name or f"{request.ticker} Corporation"
        builder.set_metadata(
            ticker=request.ticker,
            company_name=company_name,
            analyst="EquiSense AI",
            report_type="Investment Research Report"
        )
        
        # Add sections based on request
        if "executive_summary" in request.include_sections:
            builder.add_section(
                title="Executive Summary",
                content=f"Comprehensive analysis of {company_name} ({request.ticker}) including key investment highlights, risks, and recommendations.",
                data={
                    "Analysis Date": datetime.now().strftime("%Y-%m-%d"),
                    "Ticker": request.ticker,
                    "Company": company_name,
                    "Report Type": "Investment Research"
                }
            )
            
        if "fundamentals" in request.include_sections:
            builder.add_section(
                title="Fundamental Analysis",
                content="Detailed analysis of financial metrics, valuation, and fundamental factors affecting the investment thesis.",
                data={
                    "PE Ratio": "15.2",
                    "PB Ratio": "2.1",
                    "Debt-to-Equity": "0.3",
                    "ROE": "12.5%",
                    "Revenue Growth": "8.2%"
                },
                chart_data={
                    "type": "line",
                    "data": [[10, 12, 15, 18, 20, 22, 25]],
                    "labels": ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7"]
                },
                include_chart=request.include_charts
            )
            
        if "technicals" in request.include_sections:
            builder.add_section(
                title="Technical Analysis",
                content="Technical indicators, chart patterns, and momentum analysis for trading decisions.",
                data={
                    "RSI": "45.2",
                    "MACD": "0.15",
                    "SMA 20": "125.50",
                    "SMA 50": "118.75",
                    "Support": "115.00",
                    "Resistance": "135.00"
                },
                chart_data={
                    "type": "line",
                    "data": [[120, 125, 130, 128, 132, 135, 138]],
                    "labels": ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Day 6", "Day 7"]
                },
                include_chart=request.include_charts
            )
            
        if "sentiment" in request.include_sections:
            builder.add_section(
                title="Market Sentiment",
                content="Analysis of news sentiment, analyst recommendations, and market perception.",
                data={
                    "News Sentiment": "Positive",
                    "Analyst Consensus": "Buy",
                    "Price Target": "145.00",
                    "Upside Potential": "12.5%",
                    "Social Sentiment": "Neutral"
                }
            )
            
        if "recommendation" in request.include_sections:
            builder.add_section(
                title="Investment Recommendation",
                content="Final investment recommendation with rationale, risk assessment, and price targets.",
                data={
                    "Recommendation": "Buy",
                    "Rating": "4.2/5",
                    "Price Target": "145.00",
                    "Stop Loss": "115.00",
                    "Time Horizon": "12 months",
                    "Risk Level": "Medium"
                }
            )
        
        # Generate PDF
        pdf_bytes = await builder.build(include_charts=request.include_charts)
        
        # Create response
        report_id = f"report_{request.ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        return ReportResponse(
            report_id=report_id,
            ticker=request.ticker,
            company_name=company_name,
            generated_at=datetime.now(),
            format=request.format,
            size_bytes=len(pdf_bytes),
            download_url=f"/api/v1/reports/download/{report_id}"
        )
        
    except Exception as e:
        logger.error(f"Error generating report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{report_id}")
async def download_report(report_id: str):
    """Download a generated report"""
    try:
        # In a real implementation, you would store reports and retrieve them by ID
        # For now, we'll generate a sample report
        
        builder = ReportBuilder()
        builder.set_metadata(
            ticker="SAMPLE",
            company_name="Sample Corporation",
            analyst="EquiSense AI"
        )
        
        builder.add_section(
            title="Sample Report",
            content="This is a sample report generated by EquiSense AI.",
            data={"Sample Metric": "Sample Value"}
        )
        
        pdf_bytes = await builder.build()
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={report_id}.pdf"}
        )
        
    except Exception as e:
        logger.error(f"Error downloading report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export")
async def export_data(request: ExportRequest):
    """Export analysis data in various formats"""
    try:
        filename = request.filename or f"{request.ticker}_analysis_{datetime.now().strftime('%Y%m%d')}"
        
        if request.format == "csv":
            import csv
            
            # Convert data to CSV
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write headers
            if isinstance(request.data, dict):
                writer.writerow(["Metric", "Value"])
                for key, value in request.data.items():
                    writer.writerow([key, value])
            else:
                writer.writerow(["Data"])
                writer.writerow([str(request.data)])
            
            csv_content = output.getvalue()
            output.close()
            
            return StreamingResponse(
                io.BytesIO(csv_content.encode('utf-8')),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}.csv"}
            )
            
        elif request.format == "json":
            import json
            
            json_content = json.dumps(request.data, indent=2, default=str)
            
            return StreamingResponse(
                io.BytesIO(json_content.encode('utf-8')),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename={filename}.json"}
            )
            
        elif request.format == "xlsx":
            try:
                import pandas as pd
                
                # Convert to DataFrame
                if isinstance(request.data, dict):
                    df = pd.DataFrame(list(request.data.items()), columns=["Metric", "Value"])
                else:
                    df = pd.DataFrame([request.data])
                
                # Create Excel file
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Analysis', index=False)
                
                excel_content = output.getvalue()
                output.close()
                
                return StreamingResponse(
                    io.BytesIO(excel_content),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f"attachment; filename={filename}.xlsx"}
                )
                
            except ImportError:
                raise HTTPException(status_code=400, detail="Excel export requires pandas and openpyxl")
                
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {request.format}")
            
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/formats")
async def get_supported_formats():
    """Get list of supported export formats"""
    return {
        "report_formats": [
            {
                "format": "pdf",
                "name": "PDF Report",
                "description": "Comprehensive investment research report",
                "mime_type": "application/pdf"
            }
        ],
        "export_formats": [
            {
                "format": "csv",
                "name": "CSV",
                "description": "Comma-separated values",
                "mime_type": "text/csv"
            },
            {
                "format": "json",
                "name": "JSON",
                "description": "JavaScript Object Notation",
                "mime_type": "application/json"
            },
            {
                "format": "xlsx",
                "name": "Excel",
                "description": "Microsoft Excel spreadsheet",
                "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            }
        ]
    }


@router.get("/templates")
async def get_report_templates():
    """Get available report templates"""
    return {
        "templates": [
            {
                "id": "standard",
                "name": "Standard Report",
                "description": "Comprehensive analysis with all sections",
                "sections": [
                    "executive_summary",
                    "fundamentals", 
                    "technicals",
                    "sentiment",
                    "recommendation"
                ]
            },
            {
                "id": "quick",
                "name": "Quick Analysis",
                "description": "Brief overview with key metrics",
                "sections": [
                    "executive_summary",
                    "recommendation"
                ]
            },
            {
                "id": "technical",
                "name": "Technical Focus",
                "description": "Technical analysis emphasis",
                "sections": [
                    "executive_summary",
                    "technicals",
                    "recommendation"
                ]
            },
            {
                "id": "fundamental",
                "name": "Fundamental Focus", 
                "description": "Fundamental analysis emphasis",
                "sections": [
                    "executive_summary",
                    "fundamentals",
                    "sentiment",
                    "recommendation"
                ]
            }
        ]
    }
