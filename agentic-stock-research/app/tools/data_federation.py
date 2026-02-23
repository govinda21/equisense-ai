"""
Multi-source data federation and reconciliation for improved accuracy
"""
from __future__ import annotations

import asyncio
import logging
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import httpx
import yfinance as yf

from app.cache.redis_cache import get_cache_manager
from app.utils.retry import retry_async

logger = logging.getLogger(__name__)

_FALLBACK_RATES = {"USD": 1.0, "EUR": 0.85, "GBP": 0.73, "JPY": 110.0,
                   "INR": 75.0, "CNY": 6.5, "CAD": 1.25, "AUD": 1.35}


def _safe_float(value: Any) -> Optional[float]:
    try:
        return None if value is None or value == "None" else float(value)
    except Exception:
        return None


def _weighted_avg(values: List[float], weights: List[float]) -> float:
    total = sum(weights)
    return sum(v * w for v, w in zip(values, weights)) / total if total > 0 else values[0]


def _reconcile_fields(
    results: List[Tuple["DataSource", Dict[str, Any]]],
    fields: List[str],
    mode: str = "weighted"
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for field in fields:
        vals, wts, srcs = [], [], []
        for src, data in results:
            v = data.get(field)
            if v is not None:
                vals.append(v); wts.append(src.priority * src.success_rate); srcs.append(src.name)
        if not vals:
            continue
        if len(vals) == 1:
            out[field] = vals[0]
        elif mode == "max":
            out[field] = max(vals)
        else:
            mean = statistics.mean(vals)
            std = statistics.stdev(vals) if len(vals) > 1 else 0
            fv = [v for v, s in zip(vals, srcs) if std == 0 or abs(v - mean) <= 2 * std]
            fw = [w for v, w, s in zip(vals, wts, srcs) if std == 0 or abs(v - mean) <= 2 * std]
            if not fv:
                out[field] = statistics.median(vals)
            else:
                out[field] = _weighted_avg(fv, fw)
                cv = statistics.stdev(vals) / abs(mean) if mean != 0 else 0
                out[f"{field}_confidence"] = max(0, 1 - cv)
                if len(vals) > 1:
                    out[f"{field}_variance"] = statistics.stdev(vals) / out[field] if out[field] != 0 else 0
    return out


class DataSource:
    def __init__(self, name: str, priority: int = 1):
        self.name, self.priority = name, priority
        self.success_rate, self.total_requests, self.failed_requests = 1.0, 0, 0

    async def fetch(self, ticker: str, data_type: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def update_stats(self, success: bool):
        self.total_requests += 1
        if not success:
            self.failed_requests += 1
        self.success_rate = 1 - (self.failed_requests / self.total_requests)


class YahooFinanceSource(DataSource):
    def __init__(self):
        super().__init__("YahooFinance", priority=2)

    @retry_async(max_retries=2, base_delay=0.5)
    async def fetch(self, ticker: str, data_type: str) -> Optional[Dict[str, Any]]:
        try:
            result = await asyncio.to_thread(self._fetch_sync, ticker, data_type)
            self.update_stats(True)
            return result
        except Exception as e:
            logger.error(f"YahooFinance fetch failed for {ticker}/{data_type}: {e}")
            self.update_stats(False)
            return None

    def _fetch_sync(self, ticker: str, data_type: str) -> Optional[Dict[str, Any]]:
        info = yf.Ticker(ticker).info or {}
        ts = datetime.utcnow().isoformat()
        if data_type == "fundamentals":
            return {"pe_ratio": info.get("trailingPE"), "pb_ratio": info.get("priceToBook"),
                    "market_cap": info.get("marketCap"), "revenue": info.get("totalRevenue"),
                    "earnings": info.get("netIncomeToCommon"), "roe": info.get("returnOnEquity"),
                    "debt_equity": info.get("debtToEquity"), "current_ratio": info.get("currentRatio"),
                    "gross_margins": info.get("grossMargins"), "operating_margins": info.get("operatingMargins"),
                    "source": self.name, "timestamp": ts}
        if data_type == "price":
            return {"current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
                    "previous_close": info.get("previousClose"), "day_high": info.get("dayHigh"),
                    "day_low": info.get("dayLow"), "volume": info.get("volume"),
                    "market_cap": info.get("marketCap"), "52_week_high": info.get("fiftyTwoWeekHigh"),
                    "52_week_low": info.get("fiftyTwoWeekLow"),
                    "currency": info.get("currency", "USD"), "source": self.name, "timestamp": ts}
        if data_type == "analyst":
            return {"target_mean": info.get("targetMeanPrice"), "target_median": info.get("targetMedianPrice"),
                    "target_high": info.get("targetHighPrice"), "target_low": info.get("targetLowPrice"),
                    "recommendation": info.get("recommendationKey"),
                    "recommendation_mean": info.get("recommendationMean"),
                    "analyst_count": info.get("numberOfAnalystOpinions"),
                    "source": self.name, "timestamp": ts}
        return None


class AlphaVantageSource(DataSource):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__("AlphaVantage", priority=3)
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"

    async def fetch(self, ticker: str, data_type: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
        try:
            if data_type == "fundamentals":
                return await self._fetch_fundamentals(ticker)
            if data_type == "price":
                return await self._fetch_price(ticker)
            return None
        except Exception as e:
            logger.error(f"AlphaVantage fetch failed for {ticker}/{data_type}: {e}")
            self.update_stats(False)
            return None

    async def _fetch_fundamentals(self, ticker: str) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(self.base_url, params={"function": "OVERVIEW", "symbol": ticker, "apikey": self.api_key})
            if r.status_code == 200:
                data = r.json()
                if "Symbol" in data:
                    self.update_stats(True)
                    return {"pe_ratio": _safe_float(data.get("PERatio")), "pb_ratio": _safe_float(data.get("PriceToBookRatio")),
                            "market_cap": _safe_float(data.get("MarketCapitalization")), "revenue": _safe_float(data.get("RevenueTTM")),
                            "earnings": _safe_float(data.get("EBITDA")), "roe": _safe_float(data.get("ReturnOnEquityTTM")),
                            "profit_margin": _safe_float(data.get("ProfitMargin")), "operating_margin": _safe_float(data.get("OperatingMarginTTM")),
                            "dividend_yield": _safe_float(data.get("DividendYield")), "beta": _safe_float(data.get("Beta")),
                            "source": self.name, "timestamp": datetime.utcnow().isoformat()}
        self.update_stats(False)
        return None

    async def _fetch_price(self, ticker: str) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(self.base_url, params={"function": "GLOBAL_QUOTE", "symbol": ticker, "apikey": self.api_key})
            if r.status_code == 200:
                data = r.json()
                if "Global Quote" in data:
                    q = data["Global Quote"]
                    self.update_stats(True)
                    return {"current_price": _safe_float(q.get("05. price")), "previous_close": _safe_float(q.get("08. previous close")),
                            "day_high": _safe_float(q.get("03. high")), "day_low": _safe_float(q.get("04. low")),
                            "volume": _safe_float(q.get("06. volume")), "change": _safe_float(q.get("09. change")),
                            "change_percent": q.get("10. change percent", "").replace("%", ""),
                            "source": self.name, "timestamp": datetime.utcnow().isoformat()}
        self.update_stats(False)
        return None


class PolygonIOSource(DataSource):
    def __init__(self, api_key: Optional[str] = None):
        super().__init__("PolygonIO", priority=4)
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"

    async def fetch(self, ticker: str, data_type: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
        try:
            if data_type == "price":
                return await self._fetch_price(ticker)
            if data_type == "fundamentals":
                return await self._fetch_fundamentals(ticker)
            return None
        except Exception as e:
            logger.error(f"PolygonIO fetch failed for {ticker}/{data_type}: {e}")
            self.update_stats(False)
            return None

    async def _fetch_price(self, ticker: str) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{self.base_url}/v2/last/trade/{ticker}", params={"apiKey": self.api_key})
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "OK" and "results" in data:
                    t = data["results"]
                    self.update_stats(True)
                    return {"current_price": t.get("p"), "volume": t.get("s"),
                            "timestamp_exchange": t.get("t"), "source": self.name,
                            "timestamp": datetime.utcnow().isoformat()}
        self.update_stats(False)
        return None

    async def _fetch_fundamentals(self, ticker: str) -> Optional[Dict[str, Any]]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(f"{self.base_url}/v3/reference/tickers/{ticker}", params={"apiKey": self.api_key})
            if r.status_code == 200:
                data = r.json()
                if data.get("status") == "OK" and "results" in data:
                    c = data["results"]
                    self.update_stats(True)
                    return {"market_cap": c.get("market_cap"), "shares_outstanding": c.get("share_class_shares_outstanding"),
                            "sic_description": c.get("sic_description"), "ticker": c.get("ticker"),
                            "name": c.get("name"), "primary_exchange": c.get("primary_exchange"),
                            "type": c.get("type"), "source": self.name, "timestamp": datetime.utcnow().isoformat()}
        self.update_stats(False)
        return None


class DataFederation:
    """Federate data from multiple sources with reconciliation and validation."""

    _FIELD_MAP = {
        "price": {"fields": ["current_price", "previous_close", "day_high", "day_low"], "max_fields": ["volume"]},
        "fundamentals": {"fields": ["pe_ratio", "pb_ratio", "roe", "debt_equity", "current_ratio",
                                    "market_cap", "revenue", "earnings", "gross_margins", "operating_margins", "profit_margin"]},
        "analyst": {"fields": ["target_mean", "target_median", "target_high", "target_low"], "max_fields": ["analyst_count"]},
    }

    def __init__(self, sources: Optional[List[DataSource]] = None):
        self.sources = sources or [YahooFinanceSource()]
        self.reconciliation_threshold = 0.1

    def add_source(self, source: DataSource):
        self.sources.append(source)
        self.sources.sort(key=lambda x: x.priority, reverse=True)

    async def fetch_federated_data(self, ticker: str, data_type: str, use_cache: bool = True) -> Dict[str, Any]:
        if use_cache:
            cache = await get_cache_manager()
            cache_key = f"federated:{ticker}:{data_type}"
            if cached := await cache.get(cache_key):
                return cached

        results_raw = await asyncio.gather(
            *[s.fetch(ticker, data_type) for s in self.sources if s.success_rate > 0.2],
            return_exceptions=True
        )
        valid = [(self.sources[i], r) for i, r in enumerate(results_raw)
                 if not isinstance(r, Exception) and r is not None]

        if not valid:
            logger.warning(f"No valid data from any source for {ticker}/{data_type}")
            return {}

        reconciled = self._reconcile_data(valid, data_type)
        reconciled["federation_metadata"] = {
            "sources_used": [s.name for s, _ in valid],
            "reconciliation_method": "weighted_average_by_priority",
            "timestamp": datetime.utcnow().isoformat()
        }

        if use_cache:
            ttl = 900 if data_type == "price" else 3600
            await (await get_cache_manager()).set(cache_key, reconciled, ttl)

        return reconciled

    def _reconcile_data(self, results: List[Tuple[DataSource, Dict[str, Any]]], data_type: str) -> Dict[str, Any]:
        if len(results) == 1:
            return results[0][1]

        cfg = self._FIELD_MAP.get(data_type, {})
        out = _reconcile_fields(results, cfg.get("fields", []))

        for field in cfg.get("max_fields", []):
            vals = [d.get(field) for _, d in results if d.get(field) is not None]
            if vals:
                out[field] = max(vals)

        if data_type == "price":
            for _, data in results:
                if "currency" in data:
                    out["currency"] = data["currency"]
                    break
        elif data_type == "analyst":
            for _, data in results:
                if data.get("recommendation"):
                    out["recommendation"] = data["recommendation"]
                    break

        return out


class CurrencyConverter:
    """Handle currency conversions for cross-market analysis."""

    _CURRENCY_FIELDS = ["market_cap", "revenue", "earnings", "total_debt", "total_cash",
                        "free_cash_flow", "operating_cash_flow", "current_price",
                        "target_mean", "target_high", "target_low"]

    def __init__(self):
        self.base_currency = "USD"
        self.rates_cache: Dict[str, float] = {}
        self.last_update: Optional[datetime] = None
        self.update_interval = timedelta(hours=1)

    async def get_exchange_rates(self) -> Dict[str, float]:
        if self.last_update and datetime.utcnow() - self.last_update < self.update_interval and self.rates_cache:
            return self.rates_cache
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"https://api.exchangerate-api.com/v4/latest/{self.base_currency}")
                if r.status_code == 200:
                    self.rates_cache = r.json().get("rates", {})
                    self.last_update = datetime.utcnow()
                    return self.rates_cache
        except Exception as e:
            logger.error(f"Failed to fetch exchange rates: {e}")
        return _FALLBACK_RATES.copy()

    async def convert(self, amount: float, from_currency: str, to_currency: str = "USD") -> float:
        if from_currency == to_currency:
            return amount
        rates = await self.get_exchange_rates()
        if from_currency == "USD":
            return amount * rates.get(to_currency, 1.0)
        if to_currency == "USD":
            r = rates.get(from_currency, 1.0)
            return amount / r if r else amount
        usd = amount / rates.get(from_currency, 1.0) if rates.get(from_currency, 1.0) else amount
        return usd * rates.get(to_currency, 1.0)

    async def normalize_financials(self, data: Dict[str, Any], source_currency: str,
                                   target_currency: str = "USD") -> Dict[str, Any]:
        if source_currency == target_currency:
            return data
        normalized = data.copy()
        for field in self._CURRENCY_FIELDS:
            if data.get(field) is not None:
                try:
                    normalized[field] = await self.convert(data[field], source_currency, target_currency)
                    normalized[f"{field}_original_currency"] = source_currency
                except Exception as e:
                    logger.warning(f"Failed to convert {field}: {e}")
        normalized["normalized_currency"] = target_currency
        return normalized
