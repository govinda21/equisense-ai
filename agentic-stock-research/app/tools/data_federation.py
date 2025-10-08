"""
Multi-source data federation and reconciliation for improved accuracy
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import statistics

import yfinance as yf
import httpx

from app.utils.retry import retry_async
from app.cache.redis_cache import get_cache_manager

logger = logging.getLogger(__name__)


class DataSource:
    """Base class for data sources"""
    
    def __init__(self, name: str, priority: int = 1):
        self.name = name
        self.priority = priority  # Higher priority = more trusted
        self.success_rate = 1.0
        self.total_requests = 0
        self.failed_requests = 0
    
    async def fetch(self, ticker: str, data_type: str) -> Optional[Dict[str, Any]]:
        """Fetch data from source"""
        raise NotImplementedError
    
    def update_stats(self, success: bool):
        """Update source reliability stats"""
        self.total_requests += 1
        if not success:
            self.failed_requests += 1
        self.success_rate = 1 - (self.failed_requests / self.total_requests)


class YahooFinanceSource(DataSource):
    """Yahoo Finance data source"""
    
    def __init__(self):
        super().__init__("YahooFinance", priority=2)
    
    @retry_async(max_retries=2, base_delay=0.5)
    async def fetch(self, ticker: str, data_type: str) -> Optional[Dict[str, Any]]:
        """Fetch data from Yahoo Finance"""
        try:
            if data_type == "fundamentals":
                return await self._fetch_fundamentals(ticker)
            elif data_type == "price":
                return await self._fetch_price(ticker)
            elif data_type == "analyst":
                return await self._fetch_analyst(ticker)
            else:
                return None
        except Exception as e:
            logger.error(f"YahooFinance fetch failed for {ticker}/{data_type}: {e}")
            self.update_stats(False)
            return None
    
    async def _fetch_fundamentals(self, ticker: str) -> Dict[str, Any]:
        """Fetch fundamental data"""
        def _fetch():
            t = yf.Ticker(ticker)
            info = t.info or {}
            return {
                "pe_ratio": info.get("trailingPE"),
                "pb_ratio": info.get("priceToBook"),
                "market_cap": info.get("marketCap"),
                "revenue": info.get("totalRevenue"),
                "earnings": info.get("netIncomeToCommon"),
                "roe": info.get("returnOnEquity"),
                "debt_equity": info.get("debtToEquity"),
                "current_ratio": info.get("currentRatio"),
                "gross_margins": info.get("grossMargins"),
                "operating_margins": info.get("operatingMargins"),
                "source": self.name,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        result = await asyncio.to_thread(_fetch)
        self.update_stats(True)
        return result
    
    async def _fetch_price(self, ticker: str) -> Dict[str, Any]:
        """Fetch price data"""
        def _fetch():
            t = yf.Ticker(ticker)
            info = t.info or {}
            return {
                "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "previous_close": info.get("previousClose"),
                "day_high": info.get("dayHigh"),
                "day_low": info.get("dayLow"),
                "volume": info.get("volume"),
                "market_cap": info.get("marketCap"),
                "52_week_high": info.get("fiftyTwoWeekHigh"),
                "52_week_low": info.get("fiftyTwoWeekLow"),
                "currency": info.get("currency", "USD"),
                "source": self.name,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        result = await asyncio.to_thread(_fetch)
        self.update_stats(True)
        return result
    
    async def _fetch_analyst(self, ticker: str) -> Dict[str, Any]:
        """Fetch analyst data"""
        def _fetch():
            t = yf.Ticker(ticker)
            info = t.info or {}
            return {
                "target_mean": info.get("targetMeanPrice"),
                "target_median": info.get("targetMedianPrice"),
                "target_high": info.get("targetHighPrice"),
                "target_low": info.get("targetLowPrice"),
                "recommendation": info.get("recommendationKey"),
                "recommendation_mean": info.get("recommendationMean"),
                "analyst_count": info.get("numberOfAnalystOpinions"),
                "source": self.name,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        result = await asyncio.to_thread(_fetch)
        self.update_stats(True)
        return result


class AlphaVantageSource(DataSource):
    """Alpha Vantage data source (requires API key)"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__("AlphaVantage", priority=3)
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
    
    async def fetch(self, ticker: str, data_type: str) -> Optional[Dict[str, Any]]:
        """Fetch data from Alpha Vantage"""
        if not self.api_key:
            return None
        
        try:
            if data_type == "fundamentals":
                return await self._fetch_fundamentals(ticker)
            elif data_type == "price":
                return await self._fetch_price(ticker)
            else:
                return None
        except Exception as e:
            logger.error(f"AlphaVantage fetch failed for {ticker}/{data_type}: {e}")
            self.update_stats(False)
            return None
    
    async def _fetch_fundamentals(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch fundamental data from Alpha Vantage"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                self.base_url,
                params={
                    "function": "OVERVIEW",
                    "symbol": ticker,
                    "apikey": self.api_key
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if "Symbol" in data:
                    self.update_stats(True)
                    return {
                        "pe_ratio": self._safe_float(data.get("PERatio")),
                        "pb_ratio": self._safe_float(data.get("PriceToBookRatio")),
                        "market_cap": self._safe_float(data.get("MarketCapitalization")),
                        "revenue": self._safe_float(data.get("RevenueTTM")),
                        "earnings": self._safe_float(data.get("EBITDA")),
                        "roe": self._safe_float(data.get("ReturnOnEquityTTM")),
                        "profit_margin": self._safe_float(data.get("ProfitMargin")),
                        "operating_margin": self._safe_float(data.get("OperatingMarginTTM")),
                        "dividend_yield": self._safe_float(data.get("DividendYield")),
                        "beta": self._safe_float(data.get("Beta")),
                        "source": self.name,
                        "timestamp": datetime.utcnow().isoformat()
                    }
        
        self.update_stats(False)
        return None
    
    async def _fetch_price(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch price data from Alpha Vantage"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                self.base_url,
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": ticker,
                    "apikey": self.api_key
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if "Global Quote" in data:
                    quote = data["Global Quote"]
                    self.update_stats(True)
                    return {
                        "current_price": self._safe_float(quote.get("05. price")),
                        "previous_close": self._safe_float(quote.get("08. previous close")),
                        "day_high": self._safe_float(quote.get("03. high")),
                        "day_low": self._safe_float(quote.get("04. low")),
                        "volume": self._safe_float(quote.get("06. volume")),
                        "change": self._safe_float(quote.get("09. change")),
                        "change_percent": quote.get("10. change percent", "").replace("%", ""),
                        "source": self.name,
                        "timestamp": datetime.utcnow().isoformat()
                    }
        
        self.update_stats(False)
        return None
    
    def _safe_float(self, value: Any) -> Optional[float]:
        """Safely convert to float"""
        try:
            if value is None or value == "None":
                return None
            return float(value)
        except:
            return None


class PolygonIOSource(DataSource):
    """Polygon.io data source (requires API key)"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__("PolygonIO", priority=4)
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
    
    async def fetch(self, ticker: str, data_type: str) -> Optional[Dict[str, Any]]:
        """Fetch data from Polygon.io"""
        if not self.api_key:
            return None
        
        try:
            if data_type == "price":
                return await self._fetch_price(ticker)
            elif data_type == "fundamentals":
                return await self._fetch_fundamentals(ticker)
            else:
                return None
        except Exception as e:
            logger.error(f"PolygonIO fetch failed for {ticker}/{data_type}: {e}")
            self.update_stats(False)
            return None
    
    async def _fetch_price(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch price data from Polygon.io"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get latest trade
            response = await client.get(
                f"{self.base_url}/v2/last/trade/{ticker}",
                params={"apiKey": self.api_key}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "OK" and "results" in data:
                    trade = data["results"]
                    self.update_stats(True)
                    return {
                        "current_price": trade.get("p"),  # price
                        "volume": trade.get("s"),  # size
                        "timestamp_exchange": trade.get("t"),  # exchange timestamp
                        "source": self.name,
                        "timestamp": datetime.utcnow().isoformat()
                    }
        
        self.update_stats(False)
        return None
    
    async def _fetch_fundamentals(self, ticker: str) -> Optional[Dict[str, Any]]:
        """Fetch fundamental data from Polygon.io"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.base_url}/v3/reference/tickers/{ticker}",
                params={"apiKey": self.api_key}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "OK" and "results" in data:
                    company = data["results"]
                    self.update_stats(True)
                    return {
                        "market_cap": company.get("market_cap"),
                        "shares_outstanding": company.get("share_class_shares_outstanding"),
                        "sic_description": company.get("sic_description"),
                        "ticker": company.get("ticker"),
                        "name": company.get("name"),
                        "primary_exchange": company.get("primary_exchange"),
                        "type": company.get("type"),
                        "source": self.name,
                        "timestamp": datetime.utcnow().isoformat()
                    }
        
        self.update_stats(False)
        return None


class DataFederation:
    """
    Federate data from multiple sources with reconciliation and validation
    """
    
    def __init__(self, sources: Optional[List[DataSource]] = None):
        self.sources = sources or [YahooFinanceSource()]
        self.reconciliation_threshold = 0.1  # 10% difference threshold
    
    def add_source(self, source: DataSource):
        """Add a data source"""
        self.sources.append(source)
        # Sort by priority (highest first)
        self.sources.sort(key=lambda x: x.priority, reverse=True)
    
    async def fetch_federated_data(
        self,
        ticker: str,
        data_type: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Fetch data from multiple sources and reconcile
        """
        
        # Check cache first
        if use_cache:
            cache = await get_cache_manager()
            cache_key = f"federated:{ticker}:{data_type}"
            cached_data = await cache.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for federated data: {ticker}/{data_type}")
                return cached_data
        
        # Fetch from all sources in parallel
        fetch_tasks = []
        for source in self.sources:
            if source.success_rate > 0.2:  # Skip unreliable sources
                fetch_tasks.append(source.fetch(ticker, data_type))
        
        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        
        # Filter valid results
        valid_results = []
        for i, result in enumerate(results):
            if not isinstance(result, Exception) and result is not None:
                valid_results.append((self.sources[i], result))
        
        if not valid_results:
            logger.warning(f"No valid data from any source for {ticker}/{data_type}")
            return {}
        
        # Reconcile data
        reconciled = self._reconcile_data(valid_results, data_type)
        
        # Add metadata
        reconciled["federation_metadata"] = {
            "sources_used": [source.name for source, _ in valid_results],
            "reconciliation_method": "weighted_average_by_priority",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Cache the result
        if use_cache:
            cache = await get_cache_manager()
            ttl = 900 if data_type == "price" else 3600  # 15 min for prices, 1 hour for others
            await cache.set(cache_key, reconciled, ttl)
        
        return reconciled
    
    def _reconcile_data(
        self,
        results: List[Tuple[DataSource, Dict[str, Any]]],
        data_type: str
    ) -> Dict[str, Any]:
        """
        Reconcile data from multiple sources
        """
        
        if len(results) == 1:
            # Single source, return as-is
            return results[0][1]
        
        # Multiple sources, reconcile based on data type
        if data_type == "price":
            return self._reconcile_price_data(results)
        elif data_type == "fundamentals":
            return self._reconcile_fundamental_data(results)
        elif data_type == "analyst":
            return self._reconcile_analyst_data(results)
        else:
            # Default: return highest priority source
            return results[0][1]
    
    def _reconcile_price_data(
        self,
        results: List[Tuple[DataSource, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Reconcile price data from multiple sources"""
        
        reconciled = {}
        
        # For each price field, use weighted average based on source priority
        price_fields = ["current_price", "previous_close", "day_high", "day_low", "volume"]
        
        for field in price_fields:
            values = []
            weights = []
            
            for source, data in results:
                if field in data and data[field] is not None:
                    values.append(data[field])
                    weights.append(source.priority * source.success_rate)
            
            if values:
                if field == "volume":
                    # For volume, take the maximum
                    reconciled[field] = max(values)
                else:
                    # For prices, use weighted average
                    if len(values) == 1:
                        reconciled[field] = values[0]
                    else:
                        weighted_sum = sum(v * w for v, w in zip(values, weights))
                        total_weight = sum(weights)
                        reconciled[field] = weighted_sum / total_weight if total_weight > 0 else values[0]
                
                # Add variance info for transparency
                if len(values) > 1:
                    variance = statistics.stdev(values) / reconciled[field] if reconciled[field] != 0 else 0
                    reconciled[f"{field}_variance"] = variance
        
        # Add currency from highest priority source
        for source, data in results:
            if "currency" in data:
                reconciled["currency"] = data["currency"]
                break
        
        return reconciled
    
    def _reconcile_fundamental_data(
        self,
        results: List[Tuple[DataSource, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Reconcile fundamental data from multiple sources"""
        
        reconciled = {}
        
        # Group fields by type
        ratio_fields = ["pe_ratio", "pb_ratio", "roe", "debt_equity", "current_ratio"]
        value_fields = ["market_cap", "revenue", "earnings"]
        margin_fields = ["gross_margins", "operating_margins", "profit_margin"]
        
        all_fields = ratio_fields + value_fields + margin_fields
        
        for field in all_fields:
            values = []
            weights = []
            sources_with_field = []
            
            for source, data in results:
                if field in data and data[field] is not None:
                    values.append(data[field])
                    weights.append(source.priority * source.success_rate)
                    sources_with_field.append(source.name)
            
            if values:
                if len(values) == 1:
                    reconciled[field] = values[0]
                else:
                    # Check for outliers
                    mean_val = statistics.mean(values)
                    std_val = statistics.stdev(values) if len(values) > 1 else 0
                    
                    # Filter outliers (more than 2 std devs away)
                    filtered_values = []
                    filtered_weights = []
                    
                    for v, w, s in zip(values, weights, sources_with_field):
                        if std_val == 0 or abs(v - mean_val) <= 2 * std_val:
                            filtered_values.append(v)
                            filtered_weights.append(w)
                        else:
                            logger.warning(f"Outlier detected for {field} from {s}: {v} (mean: {mean_val})")
                    
                    if filtered_values:
                        # Use weighted average of non-outlier values
                        weighted_sum = sum(v * w for v, w in zip(filtered_values, filtered_weights))
                        total_weight = sum(filtered_weights)
                        reconciled[field] = weighted_sum / total_weight if total_weight > 0 else filtered_values[0]
                    else:
                        # All values were outliers, use median
                        reconciled[field] = statistics.median(values)
                
                # Add confidence score based on agreement
                if len(values) > 1:
                    cv = statistics.stdev(values) / abs(statistics.mean(values)) if statistics.mean(values) != 0 else 0
                    reconciled[f"{field}_confidence"] = max(0, 1 - cv)  # Higher confidence when values agree
        
        return reconciled
    
    def _reconcile_analyst_data(
        self,
        results: List[Tuple[DataSource, Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Reconcile analyst data from multiple sources"""
        
        reconciled = {}
        
        # For target prices, use weighted average
        target_fields = ["target_mean", "target_median", "target_high", "target_low"]
        
        for field in target_fields:
            values = []
            weights = []
            
            for source, data in results:
                if field in data and data[field] is not None:
                    values.append(data[field])
                    weights.append(source.priority * source.success_rate)
            
            if values:
                if len(values) == 1:
                    reconciled[field] = values[0]
                else:
                    # Use weighted average
                    weighted_sum = sum(v * w for v, w in zip(values, weights))
                    total_weight = sum(weights)
                    reconciled[field] = weighted_sum / total_weight if total_weight > 0 else values[0]
        
        # For recommendation, use highest priority source
        for source, data in results:
            if "recommendation" in data and data["recommendation"]:
                reconciled["recommendation"] = data["recommendation"]
                break
        
        # For analyst count, use maximum
        counts = [data.get("analyst_count", 0) for _, data in results if "analyst_count" in data]
        if counts:
            reconciled["analyst_count"] = max(counts)
        
        return reconciled


# Currency conversion utilities
class CurrencyConverter:
    """Handle currency conversions for cross-market analysis"""
    
    def __init__(self):
        self.base_currency = "USD"
        self.rates_cache = {}
        self.last_update = None
        self.update_interval = timedelta(hours=1)
    
    async def get_exchange_rates(self) -> Dict[str, float]:
        """Get current exchange rates"""
        
        # Check if cache is still valid
        if (self.last_update and 
            datetime.utcnow() - self.last_update < self.update_interval and
            self.rates_cache):
            return self.rates_cache
        
        try:
            # Fetch from a free API (e.g., exchangerate-api.com)
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"https://api.exchangerate-api.com/v4/latest/{self.base_currency}"
                )
                
                if response.status_code == 200:
                    data = response.json()
                    self.rates_cache = data.get("rates", {})
                    self.last_update = datetime.utcnow()
                    logger.info(f"Updated exchange rates: {len(self.rates_cache)} currencies")
                    return self.rates_cache
        except Exception as e:
            logger.error(f"Failed to fetch exchange rates: {e}")
        
        # Fallback to approximate rates
        return {
            "USD": 1.0,
            "EUR": 0.85,
            "GBP": 0.73,
            "JPY": 110.0,
            "INR": 75.0,
            "CNY": 6.5,
            "CAD": 1.25,
            "AUD": 1.35
        }
    
    async def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str = "USD"
    ) -> float:
        """Convert amount between currencies"""
        
        if from_currency == to_currency:
            return amount
        
        rates = await self.get_exchange_rates()
        
        # Convert via USD as base
        if from_currency == "USD":
            rate = rates.get(to_currency, 1.0)
            return amount * rate
        elif to_currency == "USD":
            rate = rates.get(from_currency, 1.0)
            return amount / rate if rate != 0 else amount
        else:
            # Convert from -> USD -> to
            usd_amount = amount / rates.get(from_currency, 1.0) if rates.get(from_currency, 1.0) != 0 else amount
            return usd_amount * rates.get(to_currency, 1.0)
    
    async def normalize_financials(
        self,
        data: Dict[str, Any],
        source_currency: str,
        target_currency: str = "USD"
    ) -> Dict[str, Any]:
        """Normalize financial data to target currency"""
        
        if source_currency == target_currency:
            return data
        
        # Fields that need currency conversion
        currency_fields = [
            "market_cap", "revenue", "earnings", "total_debt", "total_cash",
            "free_cash_flow", "operating_cash_flow", "current_price",
            "target_mean", "target_high", "target_low"
        ]
        
        normalized = data.copy()
        
        for field in currency_fields:
            if field in data and data[field] is not None:
                try:
                    normalized[field] = await self.convert(
                        data[field],
                        source_currency,
                        target_currency
                    )
                    normalized[f"{field}_original_currency"] = source_currency
                except Exception as e:
                    logger.warning(f"Failed to convert {field}: {e}")
        
        normalized["normalized_currency"] = target_currency
        return normalized
