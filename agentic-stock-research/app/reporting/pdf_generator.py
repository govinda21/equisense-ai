"""
PDF report generation system for EquiSense AI
Generates professional investment research reports
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import io
import base64

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib.colors import HexColor, black, white
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    from reportlab.platypus.flowables import HRFlowable
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
    from reportlab.graphics.shapes import Drawing, Rect
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics import renderPDF
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logging.warning("ReportLab not available. PDF generation will be disabled.")

logger = logging.getLogger(__name__)


@dataclass
class ReportSection:
    """Represents a section in the PDF report"""
    title: str
    content: str
    data: Optional[Dict[str, Any]] = None
    chart_data: Optional[Dict[str, Any]] = None
    include_chart: bool = False


@dataclass
class ReportMetadata:
    """Report metadata"""
    ticker: str
    company_name: str
    report_date: datetime
    analyst: str = "EquiSense AI"
    report_type: str = "Investment Research Report"
    disclaimer: str = "This report is for informational purposes only and should not be considered as investment advice."


class PDFReportGenerator:
    """Generates professional PDF reports"""
    
    def __init__(self):
        self.styles = None
        self._initialize_styles()
        
    def _initialize_styles(self):
        """Initialize PDF styles"""
        if not PDF_AVAILABLE:
            return
            
        self.styles = getSampleStyleSheet()
        
        # Custom styles
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Title'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=HexColor('#1e40af')
        ))
        
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=HexColor('#374151'),
            borderWidth=1,
            borderColor=HexColor('#e5e7eb'),
            borderPadding=8
        ))
        
        self.styles.add(ParagraphStyle(
            name='SubsectionHeader',
            parent=self.styles['Heading3'],
            fontSize=14,
            spaceAfter=8,
            spaceBefore=12,
            textColor=HexColor('#6b7280')
        ))
        
        self.styles.add(ParagraphStyle(
            name='BodyText',
            parent=self.styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
            textColor=HexColor('#374151')
        ))
        
        self.styles.add(ParagraphStyle(
            name='Disclaimer',
            parent=self.styles['Normal'],
            fontSize=9,
            spaceAfter=6,
            alignment=TA_CENTER,
            textColor=HexColor('#9ca3af'),
            fontStyle='italic'
        ))
        
    async def generate_report(
        self,
        metadata: ReportMetadata,
        sections: List[ReportSection],
        include_charts: bool = True
    ) -> bytes:
        """Generate a complete PDF report"""
        if not PDF_AVAILABLE:
            raise RuntimeError("PDF generation not available. Install ReportLab.")
            
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        story = []
        
        # Title page
        story.extend(self._create_title_page(metadata))
        story.append(PageBreak())
        
        # Table of contents
        story.extend(self._create_table_of_contents(sections))
        story.append(PageBreak())
        
        # Executive summary
        story.extend(self._create_executive_summary(metadata, sections))
        story.append(PageBreak())
        
        # Main sections
        for section in sections:
            story.extend(self._create_section(section, include_charts))
            story.append(Spacer(1, 12))
            
        # Appendices
        story.extend(self._create_appendices(metadata))
        
        # Build PDF
        doc.build(story)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        logger.info(f"Generated PDF report for {metadata.ticker} ({len(pdf_bytes)} bytes)")
        return pdf_bytes
        
    def _create_title_page(self, metadata: ReportMetadata) -> List:
        """Create the title page"""
        elements = []
        
        # Company logo placeholder
        elements.append(Spacer(1, 2*inch))
        
        # Report title
        elements.append(Paragraph(
            f"{metadata.company_name} ({metadata.ticker})",
            self.styles['CustomTitle']
        ))
        
        elements.append(Spacer(1, 0.5*inch))
        
        # Report type
        elements.append(Paragraph(
            metadata.report_type,
            self.styles['Heading2']
        ))
        
        elements.append(Spacer(1, 1*inch))
        
        # Report details table
        report_data = [
            ['Report Date:', metadata.report_date.strftime('%B %d, %Y')],
            ['Analyst:', metadata.analyst],
            ['Ticker:', metadata.ticker],
            ['Company:', metadata.company_name]
        ]
        
        report_table = Table(report_data, colWidths=[2*inch, 3*inch])
        report_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 12),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ]))
        
        elements.append(report_table)
        elements.append(Spacer(1, 1*inch))
        
        # Disclaimer
        elements.append(Paragraph(
            metadata.disclaimer,
            self.styles['Disclaimer']
        ))
        
        return elements
        
    def _create_table_of_contents(self, sections: List[ReportSection]) -> List:
        """Create table of contents"""
        elements = []
        
        elements.append(Paragraph("Table of Contents", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.3*inch))
        
        toc_data = [['Section', 'Page']]
        page_num = 3  # Start after title page and TOC
        
        for i, section in enumerate(sections):
            toc_data.append([section.title, str(page_num)])
            page_num += 1
            
        toc_table = Table(toc_data, colWidths=[4*inch, 1*inch])
        toc_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('LINEBELOW', (0, 0), (-1, 0), 1, black),
        ]))
        
        elements.append(toc_table)
        
        return elements
        
    def _create_executive_summary(self, metadata: ReportMetadata, sections: List[ReportSection]) -> List:
        """Create executive summary section"""
        elements = []
        
        elements.append(Paragraph("Executive Summary", self.styles['SectionHeader']))
        
        # Extract key information from sections
        summary_content = f"""
        This report provides a comprehensive analysis of {metadata.company_name} ({metadata.ticker}) 
        as of {metadata.report_date.strftime('%B %d, %Y')}. The analysis covers fundamental metrics, 
        technical indicators, market sentiment, and provides investment recommendations based on 
        quantitative and qualitative factors.
        
        Key findings from our analysis include:
        """
        
        elements.append(Paragraph(summary_content, self.styles['BodyText']))
        
        # Add bullet points for key findings
        for section in sections[:3]:  # First 3 sections
            if section.data:
                elements.append(Paragraph(f"• {section.title}: {section.content[:100]}...", self.styles['BodyText']))
                
        return elements
        
    def _create_section(self, section: ReportSection, include_charts: bool) -> List:
        """Create a report section"""
        elements = []
        
        # Section header
        elements.append(Paragraph(section.title, self.styles['SectionHeader']))
        
        # Section content
        elements.append(Paragraph(section.content, self.styles['BodyText']))
        
        # Add data table if available
        if section.data:
            elements.extend(self._create_data_table(section.data))
            
        # Add chart if requested and available
        if include_charts and section.include_chart and section.chart_data:
            elements.extend(self._create_chart(section.chart_data))
            
        return elements
        
    def _create_data_table(self, data: Dict[str, Any]) -> List:
        """Create a data table from dictionary"""
        elements = []
        
        if not data:
            return elements
            
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Key Metrics", self.styles['SubsectionHeader']))
        
        # Convert data to table format
        table_data = [['Metric', 'Value']]
        for key, value in data.items():
            if isinstance(value, (int, float)):
                formatted_value = f"{value:,.2f}" if isinstance(value, float) else f"{value:,}"
            else:
                formatted_value = str(value)
            table_data.append([key.replace('_', ' ').title(), formatted_value])
            
        data_table = Table(table_data, colWidths=[2.5*inch, 2.5*inch])
        data_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#f3f4f6')),
            ('LINEBELOW', (0, 0), (-1, 0), 1, black),
            ('LINEBELOW', (0, -1), (-1, -1), 1, black),
        ]))
        
        elements.append(data_table)
        
        return elements
        
    def _create_chart(self, chart_data: Dict[str, Any]) -> List:
        """Create a chart from data"""
        elements = []
        
        if not chart_data:
            return elements
            
        elements.append(Spacer(1, 12))
        elements.append(Paragraph("Chart", self.styles['SubsectionHeader']))
        
        try:
            # Create a simple line chart
            drawing = Drawing(400, 200)
            
            chart_type = chart_data.get('type', 'line')
            
            if chart_type == 'line':
                chart = HorizontalLineChart()
                chart.x = 50
                chart.y = 50
                chart.height = 125
                chart.width = 300
                
                # Add sample data
                chart.data = chart_data.get('data', [[1, 2, 3, 4, 5]])
                chart.lines[0].strokeColor = HexColor('#3b82f6')
                
            elif chart_type == 'bar':
                chart = VerticalBarChart()
                chart.x = 50
                chart.y = 50
                chart.height = 125
                chart.width = 300
                chart.data = chart_data.get('data', [[1, 2, 3, 4, 5]])
                
            elif chart_type == 'pie':
                chart = Pie()
                chart.x = 150
                chart.y = 100
                chart.width = 100
                chart.height = 100
                chart.data = chart_data.get('data', [1, 2, 3, 4, 5])
                chart.labels = chart_data.get('labels', ['A', 'B', 'C', 'D', 'E'])
                
            drawing.add(chart)
            elements.append(drawing)
            
        except Exception as e:
            logger.error(f"Error creating chart: {e}")
            elements.append(Paragraph("Chart could not be generated", self.styles['BodyText']))
            
        return elements
        
    def _create_appendices(self, metadata: ReportMetadata) -> List:
        """Create appendices section"""
        elements = []
        
        elements.append(PageBreak())
        elements.append(Paragraph("Appendices", self.styles['SectionHeader']))
        
        # Methodology
        elements.append(Paragraph("Methodology", self.styles['SubsectionHeader']))
        methodology_text = """
        This report was generated using EquiSense AI's proprietary analysis engine, which combines:
        
        • Fundamental analysis using financial ratios, DCF valuation, and peer comparisons
        • Technical analysis using multiple indicators and chart patterns
        • Sentiment analysis from news sources and social media
        • Machine learning models for pattern recognition and prediction
        
        All data sources are verified and cross-referenced for accuracy. The analysis is updated 
        in real-time as new information becomes available.
        """
        elements.append(Paragraph(methodology_text, self.styles['BodyText']))
        
        # Data sources
        elements.append(Paragraph("Data Sources", self.styles['SubsectionHeader']))
        sources_text = """
        • Yahoo Finance - Price and volume data
        • SEC Edgar - Regulatory filings (US stocks)
        • BSE/NSE - Indian market data and filings
        • News APIs - Sentiment analysis
        • Company websites - Investor relations data
        """
        elements.append(Paragraph(sources_text, self.styles['BodyText']))
        
        # Contact information
        elements.append(Paragraph("Contact Information", self.styles['SubsectionHeader']))
        contact_text = """
        For questions about this report or to request additional analysis, please contact:
        
        EquiSense AI Research Team
        Email: research@equisense.ai
        Website: https://equisense.ai
        
        Report generated on: {date}
        """.format(date=metadata.report_date.strftime('%B %d, %Y at %I:%M %p'))
        
        elements.append(Paragraph(contact_text, self.styles['BodyText']))
        
        return elements


class ReportBuilder:
    """Builder class for creating custom reports"""
    
    def __init__(self):
        self.generator = PDFReportGenerator()
        self.metadata = None
        self.sections = []
        
    def set_metadata(self, ticker: str, company_name: str, **kwargs) -> 'ReportBuilder':
        """Set report metadata"""
        self.metadata = ReportMetadata(
            ticker=ticker,
            company_name=company_name,
            report_date=datetime.now(),
            **kwargs
        )
        return self
        
    def add_section(self, title: str, content: str, data: Dict[str, Any] = None, 
                   chart_data: Dict[str, Any] = None, include_chart: bool = False) -> 'ReportBuilder':
        """Add a section to the report"""
        section = ReportSection(
            title=title,
            content=content,
            data=data,
            chart_data=chart_data,
            include_chart=include_chart
        )
        self.sections.append(section)
        return self
        
    async def build(self, include_charts: bool = True) -> bytes:
        """Build the final PDF report"""
        if not self.metadata:
            raise ValueError("Report metadata not set")
            
        return await self.generator.generate_report(
            self.metadata,
            self.sections,
            include_charts
        )
        
    def get_base64_pdf(self, pdf_bytes: bytes) -> str:
        """Convert PDF bytes to base64 string"""
        return base64.b64encode(pdf_bytes).decode('utf-8')


# Global report generator instance
_report_generator = None

def get_report_generator() -> PDFReportGenerator:
    """Get the global report generator instance"""
    global _report_generator
    if _report_generator is None:
        _report_generator = PDFReportGenerator()
    return _report_generator
