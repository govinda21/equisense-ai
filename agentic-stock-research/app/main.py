from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.config import AppSettings, get_settings
from app.logging import configure_logging, get_logger, init_langfuse_if_configured, log_custom_event, maybe_observe
from app.schemas.input import ResearchRequest, AnalysisRequest, ChatRequest
from app.utils.async_utils import AsyncProcessor, monitor_performance, get_performance_monitor
from app.tools.ticker_mapping import (
    map_ticker_to_symbol, 
    get_currency_symbol, 
    format_market_cap,
    get_supported_countries,
    INDIAN_STOCK_MAPPING,
    US_STOCK_MAPPING
)
from app.schemas.output import ResearchResponse
from app.graph.workflow import build_research_graph


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
                "message": "Request validation failed - check field types and required fields"
            }
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
            "env_langfuse_host": os.getenv("LANGFUSE_HOST", "Not set")
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
                "average_time": sum(stat.get("average", 0) for stat in stats.values()) / len(stats) if stats else 0
            }
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
                "country": getattr(req, 'country', 'United States'),
                "horizon_short": req.horizon_short_days,
                "horizon_long": req.horizon_long_days
            },
            metadata={
                "source": "equisense-analysis-endpoint",
                "model": "gemma3:4b"
            }
        )
        if trace:
            logger.info("Langfuse generation started for analysis request")
        else:
            logger.debug("Langfuse trace not created (client disabled or not configured)")
            
        if not req.tickers:
            raise HTTPException(status_code=400, detail="tickers cannot be empty")
        
        # Map tickers to proper Yahoo Finance symbols
        mapped_tickers = []
        country = getattr(req, 'country', 'United States')
        
        for ticker in req.tickers:
            try:
                mapped_symbol, exchange, currency = map_ticker_to_symbol(ticker, country)
                mapped_tickers.append(mapped_symbol)
                logger.info(f"Mapped {ticker} -> {mapped_symbol} [{exchange}] {currency}")
            except Exception as e:
                logger.warning(f"Failed to map ticker {ticker}: {e}")
                mapped_tickers.append(ticker)  # Use original if mapping fails
        
        try:
            graph = build_research_graph(settings)
            payload = {
                "tickers": mapped_tickers,
                "horizon_short_days": req.horizon_short_days,
                "horizon_long_days": req.horizon_long_days,
                "country": country,
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
                            "status": "completed"
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

    @app.post("/api/chat")
    @maybe_observe()
    async def chat(req: ChatRequest, settings: AppSettings = Depends(get_settings)) -> Any:
        """
        Chat endpoint that uses Ollama/Gemma3 for conversational AI about stocks and finance.
        """
        try:
            from app.tools.nlp import _ollama_chat
            from app.tools.finance import fetch_info
            import asyncio
            import re
            
            # Check if the user is asking about a specific stock price
            stock_request = await _detect_stock_request(req.message)
            
            if stock_request:
                # Get real-time stock data
                ticker = stock_request['ticker']
                try:
                    info = await fetch_info(ticker)
                    
                    if info:
                        current_price = info.get('currentPrice') or info.get('regularMarketPrice')
                        change = info.get('regularMarketChange')
                        change_percent = info.get('regularMarketChangePercent')
                        company_name = info.get('longName', ticker)
                        currency = info.get('currency', 'USD')
                        
                        # Determine currency symbol based on exchange/currency
                        if ticker.endswith('.NS') or ticker.endswith('.BO') or currency == 'INR':
                            currency_symbol = "₹"
                        elif currency == 'USD':
                            currency_symbol = "$"
                        elif currency == 'EUR':
                            currency_symbol = "€"
                        elif currency == 'GBP':
                            currency_symbol = "£"
                        elif currency == 'JPY':
                            currency_symbol = "¥"
                        else:
                            currency_symbol = currency + " "
                        
                        response = f"**{company_name} ({ticker})**\n\n"
                        response += f"**Current Price:** {currency_symbol}{current_price:.2f}\n" if current_price else "Price data unavailable\n"
                        
                        if change and change_percent:
                            direction = "📈" if change >= 0 else "📉"
                            response += f"**Daily Change:** {direction} {currency_symbol}{change:+.2f} ({change_percent:+.2f}%)\n"
                        
                        # Add key metrics if available
                        if info.get('marketCap'):
                            # Market cap is usually in the currency of the exchange
                            if currency == 'INR':
                                # Convert to Crores for Indian stocks (1 Crore = 10 million)
                                market_cap_cr = info['marketCap'] / 10_000_000
                                response += f"**Market Cap:** ₹{market_cap_cr:,.0f} Cr\n"
                            else:
                                response += f"**Market Cap:** {currency_symbol}{info['marketCap']:,.0f}\n"
                        if info.get('trailingPE'):
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
            raw_response = await asyncio.to_thread(_ollama_chat, full_prompt)
            
            # Additional parsing in case Ollama returned streaming JSON
            if raw_response and raw_response.startswith('{"model":'):
                # This is still raw streaming JSON, parse it here
                import json
                lines = raw_response.strip().split('\n')
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
                response = "I'm having trouble processing your request right now. Please try again in a moment."
            
            return {"response": response}
            
        except Exception as e:
            logger.exception("chat_failed", message=req.message[:100])
            return JSONResponse(
                status_code=500, 
                content={"error": "I encountered an issue processing your request. Please try again."}
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
