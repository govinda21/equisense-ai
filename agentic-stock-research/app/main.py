from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.config import AppSettings, get_settings
from app.logging import configure_logging, get_logger, init_langfuse_if_configured, log_custom_event, maybe_observe
from app.schemas.input import ResearchRequest, AnalysisRequest, ChatRequest
from app.utils.async_utils import monitor_performance, get_performance_monitor
from app.tools.ticker_mapping import (
    map_ticker_to_symbol,
    get_supported_countries,
    INDIAN_STOCK_MAPPING,
    US_STOCK_MAPPING,
)
from app.tools.bulk_analyzer import analyze_stocks_bulk, BulkAnalysisConfig
from app.monitoring.performance_monitor import get_performance_monitor, get_performance_summary
from app.schemas.output import ResearchResponse
from app.graph.workflow import build_research_graph
from app.api.reports import router as reports_router
# from app.api.auth import router as auth_router  # Disabled for now
from app.api.realtime import router as realtime_router
from app.api.institutional import institutional_router


# ---------------------------------------------------------------------------
# Module-level helpers (shared by multiple endpoints)
# ---------------------------------------------------------------------------

def _map_tickers(tickers: list[str], country: str, logger: Any) -> list[str]:
    """Map raw tickers to proper Yahoo Finance symbols, falling back to originals on error."""
    mapped = []
    for ticker in tickers:
        try:
            mapped_symbol, exchange, currency = map_ticker_to_symbol(ticker, country)
            mapped.append(mapped_symbol)
            logger.info(f"Mapped {ticker} -> {mapped_symbol} [{exchange}] {currency}")
        except Exception as e:
            logger.warning(f"Failed to map ticker {ticker}: {e}")
            mapped.append(ticker)  # Use original if mapping fails
    return mapped


# Determine currency symbol based on exchange/currency
_CURRENCY_SYMBOLS: dict[str, str] = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "JPY": "¥",
}


def _get_currency_symbol(ticker: str, currency: str) -> str:
    if ticker.endswith(".NS") or ticker.endswith(".BO") or currency == "INR":
        return "₹"
    return _CURRENCY_SYMBOLS.get(currency, currency + " ")


# Fallback chat responses when Ollama is unavailable
_CHAT_FALLBACKS = [
    (
        lambda m: ("grade" in m or "rating" in m) and ("b-" in m or "b minus" in m),
        """A grade of B- typically indicates:

**Investment Grade Scale:**
- **A+ to A-**: Excellent investment quality, strong fundamentals
- **B+ to B-**: Good investment quality, moderate risk
- **C+ to C-**: Fair investment quality, higher risk
- **D+ to D-**: Poor investment quality, high risk
- **F**: Very poor investment quality, very high risk

**B- specifically means:**
- Above average investment quality
- Moderate risk profile
- Generally suitable for conservative to moderate risk investors
- May have some areas of concern but overall positive outlook

For detailed analysis of specific stocks, I recommend using the Stock Analysis feature.""",
    ),
    (
        lambda m: ("meaning" in m or "what does" in m) and ("hold" in m or "buy" in m or "sell" in m),
        """**Investment Recommendation Meanings:**

**BUY/STRONG BUY**: 
- Positive outlook, expected price appreciation
- Suitable for new positions or adding to existing holdings

**HOLD**: 
- Neutral outlook, maintain current position
- Not recommended for new purchases or selling

**SELL/STRONG SELL**: 
- Negative outlook, expected price decline
- Consider reducing or exiting position

**WEAK HOLD**: 
- Slightly negative outlook, consider reducing position
- Between Hold and Sell recommendations

These recommendations are based on fundamental analysis, technical indicators, and market conditions.""",
    ),
    (
        lambda m: "pe ratio" in m or "p/e" in m or "price to earnings" in m,
        """**P/E Ratio (Price-to-Earnings) Explanation:**

**What it measures:** How much investors pay for each dollar of earnings

**Interpretation:**
- **Low P/E (5-15)**: Potentially undervalued, but may indicate problems
- **Moderate P/E (15-25)**: Fairly valued for most companies
- **High P/E (25+)**: Potentially overvalued, or high growth expectations

**Important:** Compare P/E ratios within the same industry for meaningful analysis.

**Trailing P/E**: Based on past 12 months earnings
**Forward P/E**: Based on projected next 12 months earnings""",
    ),
    (
        lambda m: "help" in m or "what can you do" in m,
        """**I can help you with:**

**Investment Analysis:**
- Explain investment grades (A+, B-, C+, etc.)
- Clarify recommendation meanings (Buy, Hold, Sell, Weak Hold)
- Interpret financial ratios (P/E, P/B, ROE, Debt-to-Equity)
- Explain technical indicators and market analysis

**Stock Information:**
- Current stock prices and market data
- Company fundamentals and financial health
- Sector analysis and market trends

**How to get started:**
1. Ask specific questions like "What does grade B- mean?"
2. Use the Stock Analysis tab for detailed reports
3. Ask about specific stocks: "What's the current price of AAPL?"

**Note:** For full AI capabilities, install Ollama: https://ollama.ai/download""",
    ),
]

_CHAT_FALLBACK_DEFAULT = """I'm currently unable to process your request because Ollama (the AI model) is not running. 

**To fix this:**
1. Install Ollama: https://ollama.ai/download
2. Start Ollama service: `ollama serve`
3. Pull the model: `ollama pull gemma3:4b`

**Common Questions I can help with:**
- Investment grade meanings (A+, B-, etc.)
- Recommendation explanations (Buy, Hold, Sell)
- Financial ratios (P/E, P/B, ROE)
- Stock analysis interpretation

For detailed stock analysis, use the Stock Analysis tab."""


def _get_fallback_chat_response(message: str) -> str:
    """Return an appropriate offline fallback response for the given chat message."""
    lower = message.lower()
    for predicate, response in _CHAT_FALLBACKS:
        if predicate(lower):
            return response
    return _CHAT_FALLBACK_DEFAULT


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger().bind(component="app")

    # Initialize Langfuse (optional and non-fatal)
    try:
        init_langfuse_if_configured(settings)
    except Exception:
        pass

    # Manual Langfuse initialization is gated by LANGFUSE_ENABLED to avoid unwanted traces in dev
    if settings.langfuse_enabled:
        try:
            from langfuse import Langfuse
            manual_langfuse = Langfuse(
                secret_key=settings.langfuse_secret_key,
                public_key=settings.langfuse_public_key,
                host=settings.langfuse_host or "http://localhost:3100",
            )
            import app.logging
            app.logging._langfuse_client = manual_langfuse
            logger.info("Manual Langfuse client initialized successfully")
        except Exception as e:
            logger.warning(f"Manual Langfuse initialization failed: {e}")

    app = FastAPI(default_response_class=ORJSONResponse, title="Agentic Stock Research API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(reports_router)
    # app.include_router(auth_router)  # Disabled for now
    app.include_router(realtime_router)
    app.include_router(institutional_router)

    # Custom validation error handler for better debugging
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.error(f"Validation error for {request.method} {request.url}: {exc.errors()}")
        body = await request.body()
        logger.error(f"Request body: {body.decode() if body else 'Empty'}")
        return JSONResponse(
            status_code=422,
            content={
                "detail": exc.errors(),
                "message": "Request validation failed - check field types and required fields",
            },
        )

    @app.on_event("startup")
    async def on_startup() -> None:
        # Serve production build if available (frontend lives under agentic-stock-research/frontend)
        dist_dir = Path(__file__).resolve().parents[1] / "frontend" / "dist"
        if dist_dir.exists():
            app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="static")
            logger.info("frontend_mounted", path=str(dist_dir))

    @app.get("/health")
    async def health() -> Any:
        return {"status": "ok"}

    @app.get("/cache-stats")
    async def cache_stats():
        """Get cache statistics"""
        try:
            from app.cache.redis_cache import get_cache_manager
            cache_manager = await get_cache_manager()
            stats = cache_manager.get_cache_stats()
            return stats
        except Exception as e:
            return {"error": str(e), "status": "cache_stats_unavailable"}

    @app.post("/cache-clear")
    async def clear_cache():
        """Clear all cache entries"""
        try:
            from app.cache.redis_cache import get_cache_manager
            cache_manager = await get_cache_manager()
            # Clear all cache entries
            if hasattr(cache_manager, "_memory_cache"):
                cache_manager._memory_cache.clear()
            return {"status": "success", "message": "Cache cleared successfully"}
        except Exception as e:
            return {"error": str(e), "status": "cache_clear_failed"}

    @app.post("/cache-clear/{ticker}")
    async def clear_ticker_cache(ticker: str):
        """Clear cache entries for a specific ticker"""
        try:
            from app.cache.redis_cache import get_cache_manager
            cache_manager = await get_cache_manager()

            # Clear earnings call analysis cache for this ticker
            cache_keys_to_clear = [
                f"earnings_call_analysis:{ticker}:90:5",
                f"earnings_call_analysis:{ticker}:180:5",
                f"api_ninja_transcripts:{ticker}:90",
                f"api_ninja_transcripts:{ticker}:180",
                f"fmp_transcripts:{ticker}:90",
                f"fmp_transcripts:{ticker}:180",
            ]

            cleared_count = 0
            for key in cache_keys_to_clear:
                if await cache_manager.delete(key):
                    cleared_count += 1

            return {
                "status": "success",
                "message": f"Cleared {cleared_count} cache entries for {ticker}",
                "ticker": ticker,
                "cleared_entries": cleared_count,
            }
        except Exception as e:
            return {"error": str(e), "status": "cache_clear_failed"}

    @app.get("/countries")
    async def get_countries() -> Any:
        """Get list of supported countries for stock analysis"""
        return {"countries": get_supported_countries()}

    @app.get("/debug")
    async def debug_env():
        """Debug endpoint to check environment configuration."""
        import os
        return {
            "langfuse_configured": bool(settings.langfuse_public_key and settings.langfuse_secret_key),
            "langfuse_public_key": settings.langfuse_public_key[:20] + "..." if settings.langfuse_public_key else None,
            "langfuse_host": settings.langfuse_host,
            "ollama_model": settings.ollama_model,
            "env_langfuse_public": os.getenv("LANGFUSE_PUBLIC_KEY", "Not set")[:20] + "..." if os.getenv("LANGFUSE_PUBLIC_KEY") else "Not set",
            "env_langfuse_host": os.getenv("LANGFUSE_HOST", "Not set"),
        }

    @app.get("/performance")
    async def get_performance_stats():
        """Get performance statistics for all operations."""
        monitor = get_performance_monitor()
        stats = monitor.get_all_stats()
        return {
            "operations": stats,
            "summary": {
                "total_operations": sum(stat.get("count", 0) for stat in stats.values()),
                "total_time": sum(stat.get("total", 0) for stat in stats.values()),
                "average_time": sum(stat.get("average", 0) for stat in stats.values()) / len(stats) if stats else 0,
            },
        }

    @app.post("/analyze", response_model=ResearchResponse)
    @monitor_performance("stock_analysis")
    async def analyze(body: dict = Body(...), settings: AppSettings = Depends(get_settings)) -> Any:
        # Construct AnalysisRequest explicitly to avoid body parsing edge-cases
        req = AnalysisRequest(**body)

        # Create Langfuse trace for this analysis
        from app.logging import create_trace, update_generation_output, flush_langfuse
        trace = create_trace(
            name="stock-analysis",
            input_data={
                "tickers": req.tickers,
                "country": getattr(req, "country", "United States"),
                "horizon_short": req.horizon_short_days,
                "horizon_long": req.horizon_long_days,
            },
            metadata={
                "source": "equisense-analysis-endpoint",
                "model": "gemma3:4b",
            },
        )
        if trace:
            logger.info("Langfuse generation started for analysis request")
        else:
            logger.debug("Langfuse trace not created (client disabled or not configured)")

        if not req.tickers:
            raise HTTPException(status_code=400, detail="tickers cannot be empty")

        # Map tickers to proper Yahoo Finance symbols
        country = getattr(req, "country", "United States")
        mapped_tickers = _map_tickers(req.tickers, country, logger)

        try:
            graph = build_research_graph(settings)
            payload = {
                "tickers": mapped_tickers,
                "horizon_short_days": req.horizon_short_days,
                "horizon_long_days": req.horizon_long_days,
                "country": country,
                "analysis_type": "institutional" if req.horizon_short_days and req.horizon_long_days else "standard",
            }
            callbacks = None
            # If Langfuse callback is available from compiled graph, use it
            cb_cls = getattr(graph, "_langfuse_callback_cls", None)
            if cb_cls is not None:
                try:
                    callbacks = [cb_cls()]
                except Exception:
                    callbacks = None
            result = await graph.ainvoke(payload, callbacks=callbacks) if callbacks else await graph.ainvoke(payload)
            out = ResearchResponse(**result["final_output"])  # type: ignore[index]

            # Complete Langfuse generation
            try:
                if trace is not None:
                    # Get recommendation from the first report's decision
                    recommendation = out.reports[0].decision.action if out.reports else "Unknown"
                    rating = out.reports[0].decision.rating if out.reports else 0
                    try:
                        update_generation_output({
                            "recommendation": recommendation,
                            "rating": rating,
                            "tickers_analyzed": len(out.reports),
                            "status": "completed",
                        })
                        logger.info("Langfuse generation updated with output")
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Failed to complete Langfuse trace: {e}")

            # Flush any pending Langfuse data
            try:
                flush_langfuse()
            except Exception:
                pass

            # Emit a custom observability event (non-blocking)
            try:
                log_custom_event(
                    "analyze",
                    {
                        "tickers": req.tickers,
                        "h_s": req.horizon_short_days,
                        "h_l": req.horizon_long_days,
                    },
                )
            except Exception:
                pass

            return out
        except Exception as e:
            logger.exception("analyze_failed", tickers=req.tickers)
            return JSONResponse(status_code=500, content={"error": str(e)})

    @app.post("/analyze-bulk")
    @maybe_observe()
    @monitor_performance("bulk_analysis")
    async def analyze_bulk(
        req: ResearchRequest,
        settings: AppSettings = Depends(get_settings),
    ) -> Any:
        """
        Optimized bulk analysis endpoint for multiple stocks
        """
        logger.info("bulk_analysis_started", ticker_count=len(req.tickers))

        try:
            # Map tickers to proper Yahoo Finance symbols
            country = getattr(req, "country", "United States")
            mapped_tickers = _map_tickers(req.tickers, country, logger)

            # Configure bulk analysis based on request size
            config = BulkAnalysisConfig(
                max_concurrent_stocks=min(10, len(mapped_tickers)),  # Adaptive concurrency
                batch_size=min(20, len(mapped_tickers)),  # Adaptive batch size
                timeout_per_stock=30.0,
                cache_shared_data=True,
                enable_performance_monitoring=True,
            )

            # Perform bulk analysis
            result = await analyze_stocks_bulk(mapped_tickers, country, config)

            # Format response with per-ticker dictionary structure
            # PHASE 3: Create stock_data dict structure as requested
            # CRITICAL: Validate each report has correct ticker to prevent contamination
            stock_data_dict = result.performance_metrics.get("stock_data_dict", {})
            if not stock_data_dict:
                # Fallback: build dict from successful_analyses
                stock_data_dict = {}
                for report in result.successful_analyses:
                    ticker = report.get("ticker")
                    if ticker:
                        # CRITICAL VALIDATION: Ensure ticker matches expected tickers
                        if ticker not in mapped_tickers:
                            logger.error(f"CRITICAL: Report ticker {ticker} not in requested tickers {mapped_tickers}. Skipping to prevent contamination.")
                            continue
                        # Validate report doesn't contain data from other tickers
                        if "currentPrice" in report:
                            # Basic sanity check - price should be reasonable
                            price = report.get("currentPrice")
                            if price and (price < 0 or price > 1e7):
                                logger.warning(f"[{ticker}] Suspicious price in report: {price}")
                        stock_data_dict[ticker] = report
                        logger.info(f"[{ticker}] Added validated report to stock_data_dict")

            response_data = {
                "success": True,
                "total_stocks": len(mapped_tickers),
                "successful_analyses": len(result.successful_analyses),
                "failed_analyses": len(result.failed_analyses),
                "success_rate": result.success_rate,
                "total_time": result.total_time,
                "average_time_per_stock": result.performance_metrics.get("average_time_per_stock", 0),
                "reports": result.successful_analyses,  # List format for backward compatibility
                "stock_data": stock_data_dict,  # PHASE 3: Per-ticker dict structure
                "failed_tickers": [ticker for ticker, _ in result.failed_analyses],
                "performance_metrics": result.performance_metrics,
            }

            logger.info(
                "bulk_analysis_completed",
                successful=len(result.successful_analyses),
                failed=len(result.failed_analyses),
                total_time=result.total_time,
            )

            return ORJSONResponse(content=response_data)

        except Exception as e:
            logger.exception("bulk_analysis_failed", tickers=req.tickers)
            return JSONResponse(status_code=500, content={"error": str(e)})

    @app.get("/performance-metrics")
    async def get_performance_metrics():
        """
        Get current performance metrics and system status
        """
        try:
            monitor = get_performance_monitor()
            summary = monitor.get_detailed_performance_summary()
            return ORJSONResponse(content={
                "success": True,
                "performance_summary": summary,
                "timestamp": time.time(),
            })
        except Exception as e:
            logger.error(f"Failed to get performance metrics: {e}")
            return JSONResponse(status_code=500, content={"error": str(e)})

    @app.post("/api/generate-pdf")
    @maybe_observe()
    async def generate_pdf(req: AnalysisRequest, settings: AppSettings = Depends(get_settings)) -> Any:
        """
        Generate a PDF report for analyzed ticker(s)
        """
        try:
            from app.reporting.pdf_generator import generate_pdf_report

            logger.info("pdf_generation_started", tickers=req.tickers)

            # First, run analysis to get report data
            graph = build_research_graph(settings)
            state = await graph.ainvoke({"request": req, "raw_search_data": {}})
            analysis = state.get("analysis", {})

            if not analysis or "tickers" not in analysis:
                raise HTTPException(status_code=400, detail="Analysis failed - no data available")

            reports = analysis.get("reports", [])
            if not reports:
                raise HTTPException(status_code=400, detail="No reports generated")

            # Generate PDF for the first report (or combine if multiple)
            report_data = reports[0]

            # Generate PDF
            pdf_buffer = generate_pdf_report(report_data)

            # Get ticker for filename
            ticker = report_data.get("ticker", "report")
            filename = f"{ticker}_equity_research_{datetime.now().strftime('%Y%m%d')}.pdf"

            logger.info("pdf_generated", ticker=ticker, filename=filename)

            return StreamingResponse(
                pdf_buffer,
                media_type="application/pdf",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

        except ImportError as e:
            logger.error("pdf_generation_failed", error=str(e))
            return JSONResponse(
                status_code=501,
                content={"error": "PDF generation not available. Install reportlab: pip install reportlab"},
            )
        except Exception as e:
            logger.exception("pdf_generation_failed", tickers=req.tickers)
            return JSONResponse(status_code=500, content={"error": str(e)})

    @app.post("/api/chat")
    @maybe_observe()
    async def chat(req: ChatRequest, settings: AppSettings = Depends(get_settings)) -> Any:
        """
        Chat endpoint that uses Ollama/Gemma3 for conversational AI about stocks and finance.
        """
        try:
            from app.tools.nlp import _ollama
            from app.tools.finance import fetch_info
            import asyncio
            import re

            # Check if the user is asking about a specific stock price
            stock_request = await _detect_stock_request(req.message)

            if stock_request:
                # Get real-time stock data
                ticker = stock_request["ticker"]
                try:
                    info = await fetch_info(ticker)

                    if info:
                        current_price = info.get("currentPrice") or info.get("regularMarketPrice")
                        change = info.get("regularMarketChange")
                        change_percent = info.get("regularMarketChangePercent")
                        company_name = info.get("longName", ticker)
                        currency = info.get("currency", "USD")

                        # Determine currency symbol based on exchange/currency
                        currency_symbol = _get_currency_symbol(ticker, currency)

                        response = f"**{company_name} ({ticker})**\n\n"
                        response += f"**Current Price:** {currency_symbol}{current_price:.2f}\n" if current_price else "Price data unavailable\n"

                        if change and change_percent:
                            direction = "📈" if change >= 0 else "📉"
                            response += f"**Daily Change:** {direction} {currency_symbol}{change:+.2f} ({change_percent:+.2f}%)\n"

                        # Add key metrics if available
                        if info.get("marketCap"):
                            # Market cap is usually in the currency of the exchange
                            if currency == "INR":
                                # Convert to Crores for Indian stocks (1 Crore = 10 million)
                                market_cap_cr = info["marketCap"] / 10_000_000
                                response += f"**Market Cap:** ₹{market_cap_cr:,.0f} Cr\n"
                            else:
                                response += f"**Market Cap:** {currency_symbol}{info['marketCap']:,.0f}\n"
                        if info.get("trailingPE"):
                            response += f"**P/E Ratio:** {info['trailingPE']:.2f}\n"

                        response += "\n*Data provided by Yahoo Finance*\n"
                        response += "\n**Disclaimer:** This is real-time market data for informational purposes only. Not financial advice."

                        return {"response": response}
                    else:
                        return {"response": f"Sorry, I couldn't find current price data for {ticker}. Please verify the ticker symbol."}

                except Exception as e:
                    return {"response": f"Error fetching data for {ticker}: {str(e)}"}

            # For non-stock-price questions, use the LLM
            system_prompt = """You are a helpful AI financial assistant. You can:
- Analyze stock prices and market trends (for real-time prices, I can fetch current data)
- Explain financial concepts
- Provide insights on companies and sectors
- Help with investment research

For detailed stock analysis reports, suggest using the Stock Analysis tab.
Keep responses concise and helpful. Always include appropriate disclaimers for investment advice.

User question: """

            full_prompt = system_prompt + req.message

            # Use async to prevent blocking
            raw_response = await asyncio.to_thread(_ollama, full_prompt)

            # Additional parsing in case Ollama returned streaming JSON
            if raw_response and raw_response.startswith('{"model":'):
                # This is still raw streaming JSON, parse it here
                import json
                lines = raw_response.strip().split("\n")
                response = ""
                for line in lines:
                    try:
                        json_obj = json.loads(line)
                        response += json_obj.get("response", "")
                    except:
                        continue
            else:
                response = raw_response

            if not response:
                # Provide helpful fallback responses based on common questions
                response = _get_fallback_chat_response(req.message)

            return {"response": response}

        except Exception as e:
            logger.exception("chat_failed", message=req.message[:100])
            return JSONResponse(
                status_code=500,
                content={"error": "I encountered an issue processing your request. Please try again."},
            )

    return app


async def _detect_stock_request(message: str) -> dict | None:
    """
    Detect if user is asking for stock price/info and extract ticker
    """
    import re

    message_lower = message.lower()

    # Patterns for stock price requests
    price_patterns = [
        r"current price of ([a-zA-Z.]+)",
        r"price of ([a-zA-Z.]+)",
        r"([a-zA-Z.]+) current price",
        r"([a-zA-Z.]+) price",
        r"how is ([a-zA-Z.]+) doing",
        r"([a-zA-Z.]+) stock price",
        r"what.*price.*([a-zA-Z.]+)",
    ]

    # Use the comprehensive ticker mapping system
    # Combine Indian and US stock mappings
    ticker_mappings = {}

    # Add Indian stocks with .NS suffix
    for key, symbol in INDIAN_STOCK_MAPPING.items():
        if not symbol.endswith(".NS"):
            ticker_mappings[key] = f"{symbol}.NS"

    # Add US stocks without suffix
    for key, symbol in US_STOCK_MAPPING.items():
        ticker_mappings[key] = symbol

    # Try to find stock mentions
    for pattern in price_patterns:
        match = re.search(pattern, message_lower)
        if match:
            company_name = match.group(1).strip()

            # Look up in mappings first
            ticker = ticker_mappings.get(company_name)
            if ticker:
                return {"ticker": ticker, "company": company_name}

            # If not found, assume it might be a direct ticker
            if len(company_name) <= 6 and company_name.replace(".", "").isalpha():
                return {"ticker": company_name.upper(), "company": company_name}

    return None


app = create_app()
