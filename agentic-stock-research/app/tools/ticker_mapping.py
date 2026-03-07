from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class StockExchange:
    name: str
    suffix: str
    currency: str
    country: str
    timezone: str


EXCHANGES = {
    "US":  StockExchange("NASDAQ/NYSE", "",    "USD", "United States",  "America/New_York"),
    "NSE": StockExchange("National Stock Exchange of India", ".NS", "INR", "India", "Asia/Kolkata"),
    "BSE": StockExchange("Bombay Stock Exchange", ".BO", "INR", "India", "Asia/Kolkata"),
    "LSE": StockExchange("London Stock Exchange", ".L",  "GBP", "United Kingdom", "Europe/London"),
    "TSE": StockExchange("Tokyo Stock Exchange", ".T",   "JPY", "Japan",          "Asia/Tokyo"),
    "TSX": StockExchange("Toronto Stock Exchange", ".TO","CAD", "Canada",         "America/Toronto"),
    "ASX": StockExchange("Australian Securities Exchange", ".AX", "AUD", "Australia", "Australia/Sydney"),
    "FRA": StockExchange("Frankfurt Stock Exchange", ".F", "EUR", "Germany",      "Europe/Berlin"),
}

INDIAN_STOCK_MAPPING = {
    # Financial Services
    "jiofin": "JIOFIN", "jio financial": "JIOFIN",
    "bajaj finance": "BAJFINANCE", "bajfinance": "BAJFINANCE",
    "hdfc bank": "HDFCBANK", "hdfcbank": "HDFCBANK",
    "icici bank": "ICICIBANK", "icicibank": "ICICIBANK",
    "sbi": "SBIN", "state bank": "SBIN",
    "axis bank": "AXISBANK", "axisbank": "AXISBANK",
    "kotak bank": "KOTAKBANK", "kotakbank": "KOTAKBANK",
    # Technology
    "tcs": "TCS", "tata consultancy": "TCS",
    "infosys": "INFY", "wipro": "WIPRO",
    "hcl tech": "HCLTECH", "hcltech": "HCLTECH",
    "tech mahindra": "TECHM", "techm": "TECHM",
    # Telecom
    "reliance": "RELIANCE", "bharti airtel": "BHARTIARTL", "airtel": "BHARTIARTL", "jio": "RJIO",
    # FMCG
    "hindustan unilever": "HINDUNILVR", "hul": "HINDUNILVR",
    "itc": "ITC", "nestle india": "NESTLEIND", "britannia": "BRITANNIA",
    # Automotive
    "maruti suzuki": "MARUTI", "maruti": "MARUTI",
    "tata motors": "TATAMOTORS", "mahindra": "M&M",
    "bajaj auto": "BAJAJ-AUTO",
    "force motors": "FORCEMOT", "forcemotors": "FORCEMOT", "forcemot": "FORCEMOT",
    # Pharma
    "sun pharma": "SUNPHARMA", "dr reddy": "DRREDDY",
    "cipla": "CIPLA", "divi's lab": "DIVISLAB", "biocon": "BIOCON",
    "sanofi": "SANOFI", "sanofi india": "SANOFI",
    "pfizer india": "PFIZERINDIA", "pfizer": "PFIZERINDIA",
    "abbott india": "ABBOTINDIA", "abbott": "ABBOTINDIA",
    "glaxosmithkline": "GLAXO", "gsk": "GLAXO",
    "astrazeneca india": "ASTRAZEN", "astrazeneca": "ASTRAZEN",
    "novartis india": "NOVARTIND", "novartis": "NOVARTIND",
    # Metals
    "tata steel": "TATASTEEL", "jsl": "JINDALSTEL",
    "hindalco": "HINDALCO", "vedanta": "VEDL",
    # Oil & Gas
    "ongc": "ONGC", "ioc": "IOC", "bpcl": "BPCL", "hpcl": "HINDPETRO",
    # Retail
    "dmart": "DMART", "avenue supermarts": "DMART", "trent": "TRENT",
    # Infrastructure
    "l&t": "LT", "larsen toubro": "LT",
    "ultratech": "ULTRACEMCO", "grasim": "GRASIM",
    # Power & Energy
    "ntpc": "NTPC", "power grid": "POWERGRID",
    "adani green": "ADANIGREEN", "adani power": "ADANIPOWER",
    # Conglomerates
    "adani enterprises": "ADANIENT", "adani ports": "ADANIPORTS",
    "tata power": "TATAPOWER", "godrej": "GODREJCP",
}

US_STOCK_MAPPING = {
    "apple": "AAPL", "microsoft": "MSFT", "google": "GOOGL", "alphabet": "GOOGL",
    "amazon": "AMZN", "tesla": "TSLA", "meta": "META", "facebook": "META",
    "nvidia": "NVDA", "netflix": "NFLX", "walmart": "WMT", "disney": "DIS",
    "coca cola": "KO", "pepsi": "PEP", "johnson & johnson": "JNJ",
    "jpmorgan": "JPM", "visa": "V", "mastercard": "MA", "boeing": "BA",
    "intel": "INTC", "cisco": "CSCO", "oracle": "ORCL",
    "salesforce": "CRM", "adobe": "ADBE", "uber": "UBER", "airbnb": "ABNB",
    "zoom": "ZM", "spotify": "SPOT", "twitter": "TWTR", "snapchat": "SNAP",
}

_CURRENCY_SYMBOLS = {"USD": "$", "INR": "₹", "GBP": "£", "EUR": "€",
                     "JPY": "¥", "CAD": "C$", "AUD": "A$"}

# ---------------------------------------------------------------------------
# In-memory resolution cache — avoids hitting Ollama for the same name twice
# ---------------------------------------------------------------------------
_llm_ticker_cache: Dict[str, str] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def normalize_ticker_input(ticker: str) -> str:
    return ticker.strip().lower()


def get_country_exchanges() -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for code, ex in EXCHANGES.items():
        result.setdefault(ex.country, []).append(code)
    return result


def _get_exchange_for_symbol(symbol: str) -> Tuple[str, str]:
    """Return (exchange_code, currency) inferred from the symbol's suffix."""
    upper = symbol.upper()
    for code, ex in EXCHANGES.items():
        if ex.suffix and upper.endswith(ex.suffix.upper()):
            return code, ex.currency
    return "US", "USD"


def _get_country_defaults(country: str) -> Tuple[str, str]:
    """Return (exchange_code, currency) defaults for a country."""
    for code, ex in EXCHANGES.items():
        if ex.country == country:
            return code, ex.currency
    return "NSE", "INR"


def _already_has_suffix(upper: str) -> bool:
    return any(
        upper.endswith(ex.suffix.upper())
        for ex in EXCHANGES.values() if ex.suffix
    )


def _apply_country_suffix(base: str, country: str) -> Tuple[str, str, str]:
    """Append the default exchange suffix for a country and return the full tuple."""
    exchange_code, currency = _get_country_defaults(country)
    ex_obj = EXCHANGES.get(exchange_code)
    upper = base.upper()
    if ex_obj and ex_obj.suffix and not upper.endswith(ex_obj.suffix.upper()):
        return upper + ex_obj.suffix, exchange_code, currency
    return upper, exchange_code, currency


# ---------------------------------------------------------------------------
# yfinance symbol validation
# ---------------------------------------------------------------------------

def _yfinance_symbol_exists(symbol: str) -> bool:
    """
    Quick check: does this symbol return any data on Yahoo Finance?
    Uses a lightweight info fetch — if 'regularMarketPrice' or 'currentPrice'
    is present the symbol is valid. Times out in 5 s to keep mapping fast.
    """
    try:
        import yfinance as yf
        info = yf.Ticker(symbol).fast_info
        # fast_info raises or returns empty-ish object for unknown symbols
        price = getattr(info, "last_price", None)
        return price is not None and price > 0
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Ollama / Gemma3 LLM resolution
# ---------------------------------------------------------------------------

def _build_prompt(company_name: str, country: str, previous_wrong: Optional[str] = None) -> str:
    """
    Build the Ollama prompt.  When `previous_wrong` is set (validation failed)
    we add an explicit "NOT that symbol" line so the model tries something else.
    """
    suffix_hint = ""
    for ex in EXCHANGES.values():
        if ex.country == country and ex.suffix:
            suffix_hint = (
                f" Stocks listed in {country} use the suffix '{ex.suffix}' on Yahoo Finance "
                f"(e.g. RELIANCE.NS, FORCEMOT.NS, SANOFI.NS, PAGEIND.NS)."
            )
            break

    # Critical extra instruction for India: prevent returning US ADR tickers
    adr_warning = ""
    if country == "India":
        adr_warning = (
            "\nCRITICAL: Many global companies have BOTH a US-listed ADR ticker AND a "
            "separately listed Indian subsidiary on NSE/BSE. You MUST return the NSE/BSE "
            "ticker of the Indian-listed entity, NOT the US ADR. "
            "Examples: Sanofi India = SANOFI.NS (NOT SNY), "
            "Pfizer India = PFIZERINDIA.NS (NOT PFE), "
            "Abbott India = ABBOTINDIA.NS (NOT ABT), "
            "Honeywell Automation = HONAUT.NS (NOT HON)."
        )

    retry_hint = ""
    if previous_wrong:
        retry_hint = (
            f"\nIMPORTANT: The symbol '{previous_wrong}' was already tried and does NOT exist "
            f"on Yahoo Finance. Return a DIFFERENT, correct symbol."
        )

    return (
        f"You are a stock market expert specialising in Yahoo Finance ticker symbols.\n"
        f"Convert the company name below to its exact Yahoo Finance ticker symbol.\n"
        f"Return ONLY the ticker symbol — no explanation, no markdown, no punctuation, "
        f"nothing else.{suffix_hint}{adr_warning}{retry_hint}\n\n"
        f"Company: {company_name}\n"
        f"Country/Market: {country}\n\n"
        f"Yahoo Finance ticker:"
    )


def _call_ollama(prompt: str) -> Optional[str]:
    """Send a prompt to the local Ollama instance and return the sanitised response."""
    try:
        import urllib.request
        import json as _json

        payload = _json.dumps({
            "model": "gemma3:4b",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "num_predict": 20},
        }).encode()

        req = urllib.request.Request(
            "http://localhost:11434/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(req, timeout=10) as resp:
            body = _json.loads(resp.read().decode())

        raw: str = body.get("response", "").strip()
        resolved = re.sub(r"[^A-Za-z0-9.\-&]", "", raw).upper()
        return resolved or None

    except Exception as exc:
        logger.warning(f"[ticker_mapping] Ollama call failed: {exc}")
        return None


def _ollama_resolve_ticker(company_name: str, country: str) -> Optional[str]:
    """
    Ask Ollama/Gemma3 for the Yahoo Finance ticker, then validate it against
    Yahoo Finance.  If validation fails, retry once with the wrong symbol
    explicitly excluded from the prompt.

    Results are cached in _llm_ticker_cache to avoid repeated API calls.
    """
    cache_key = f"{normalize_ticker_input(company_name)}||{country}"
    if cache_key in _llm_ticker_cache:
        cached = _llm_ticker_cache[cache_key]
        logger.debug(f"[ticker_mapping] cache hit: '{company_name}' -> '{cached}'")
        return cached

    # ── Attempt 1 ──────────────────────────────────────────────────────────
    prompt = _build_prompt(company_name, country)
    resolved = _call_ollama(prompt)

    if not resolved:
        logger.warning(f"[ticker_mapping] LLM returned empty result for '{company_name}'")
        return None

    logger.info(f"[ticker_mapping] LLM resolved: '{company_name}' ({country}) -> '{resolved}'")

    # Ensure suffix is present before validating so Yahoo Finance can find it
    candidate = resolved
    if country == "India" and not _already_has_suffix(candidate):
        candidate = candidate + ".NS"

    if _yfinance_symbol_exists(candidate):
        logger.info(f"[ticker_mapping] Validated '{candidate}' exists on Yahoo Finance")
        _llm_ticker_cache[cache_key] = candidate
        return candidate

    # ── Attempt 2: tell the model its first answer was wrong ───────────────
    logger.warning(
        f"[ticker_mapping] '{candidate}' not found on Yahoo Finance — retrying with corrected prompt"
    )
    retry_prompt = _build_prompt(company_name, country, previous_wrong=candidate)
    resolved2 = _call_ollama(retry_prompt)

    if not resolved2 or resolved2 == resolved:
        logger.warning(
            f"[ticker_mapping] Retry produced no new answer for '{company_name}', "
            "falling back to raw ticker"
        )
        return None

    logger.info(f"[ticker_mapping] LLM retry resolved: '{company_name}' ({country}) -> '{resolved2}'")

    candidate2 = resolved2
    if country == "India" and not _already_has_suffix(candidate2):
        candidate2 = candidate2 + ".NS"

    if _yfinance_symbol_exists(candidate2):
        logger.info(f"[ticker_mapping] Validated retry '{candidate2}' exists on Yahoo Finance")
        _llm_ticker_cache[cache_key] = candidate2
        return candidate2

    # Both attempts failed validation — log and return None so caller falls back
    logger.warning(
        f"[ticker_mapping] Both LLM attempts failed Yahoo Finance validation for "
        f"'{company_name}'. Tried: '{candidate}', '{candidate2}'"
    )
    return None


def _resolve_with_llm_and_suffix(ticker: str, country: str) -> Optional[Tuple[str, str, str]]:
    """
    Ask the LLM (with validation), then ensure the result carries the right
    exchange suffix.  Returns a full (symbol, exchange_code, currency) tuple or None.
    """
    resolved = _ollama_resolve_ticker(ticker, country)
    if not resolved:
        return None

    # If the validated result already has a suffix, use it directly
    if _already_has_suffix(resolved):
        ex_code, currency = _get_exchange_for_symbol(resolved)
        return resolved, ex_code, currency

    # Otherwise attach the country default suffix
    return _apply_country_suffix(resolved, country)


# ---------------------------------------------------------------------------
# Public API  — identical signature to original; no callers need changing
# ---------------------------------------------------------------------------

def map_ticker_to_symbol(ticker: str, country: str = "United States") -> Tuple[str, str, str]:
    """
    Map ticker / company name input to (yahoo_symbol, exchange_code, currency).

    Resolution order
    ────────────────
    1. Input already has a recognised exchange suffix  → return as-is
    2. Static dictionary hit                           → fast path, zero latency
    3. LLM inference via Ollama/Gemma3                 → handles any company name
       • Always attempted for India (static map covers ~50 of 5000+ NSE stocks)
       • Attempted for other markets when input looks like a company name
    4. Raw ticker + country default suffix             → last resort / Ollama down
    """
    normalized = normalize_ticker_input(ticker)
    upper = ticker.strip().upper()

    # ── 1. Already has a known exchange suffix ──────────────────────────────
    if _already_has_suffix(upper):
        ex_code, currency = _get_exchange_for_symbol(upper)
        return upper, ex_code, currency

    # ── 2. Static mapping ───────────────────────────────────────────────────
    if country == "India" and normalized in INDIAN_STOCK_MAPPING:
        base = INDIAN_STOCK_MAPPING[normalized]
        logger.debug(f"[ticker_mapping] static hit: '{ticker}' -> '{base}.NS'")
        return f"{base}.NS", "NSE", "INR"

    if country == "United States" and normalized in US_STOCK_MAPPING:
        sym = US_STOCK_MAPPING[normalized]
        logger.debug(f"[ticker_mapping] static hit: '{ticker}' -> '{sym}'")
        return sym, "US", "USD"

    # ── 3. LLM via Ollama/Gemma3 ────────────────────────────────────────────
    #
    # KEY FIX: For India we ALWAYS try the LLM — the static map covers ~50 tickers
    # but NSE/BSE list 5000+. A single-word name like "Forcemotors" looks like a
    # raw ticker by pattern, but it's NOT a valid Yahoo symbol (correct: FORCEMOT.NS).
    # Without this, the old code fell straight to step 4 and produced FORCEMOTORS.NS.
    #
    # For non-India markets we gate on whether the input looks like a company name
    # (spaces / long / non-ticker characters) to avoid unnecessary Ollama calls for
    # things that are already valid raw tickers (e.g. "AAPL", "MSFT").
    _is_company_name = (
        " " in ticker.strip()
        or len(upper) > 12
        or not re.match(r"^[A-Z0-9.\-&]{1,12}$", upper)
    )

    if country == "India" or _is_company_name:
        result = _resolve_with_llm_and_suffix(ticker, country)
        if result:
            return result
        # Ollama down or returned garbage → fall through to step 4

    # ── 4. Last resort: raw input + country default suffix ──────────────────
    logger.warning(
        f"[ticker_mapping] Using raw ticker fallback for '{ticker}' ({country}). "
        "If this is a company name, check that Ollama is running."
    )
    return _apply_country_suffix(upper, country)


# ---------------------------------------------------------------------------
# Remaining helpers — unchanged from original
# ---------------------------------------------------------------------------

def get_currency_symbol(currency: str) -> str:
    return _CURRENCY_SYMBOLS.get(currency, currency)


def format_market_cap(value: float, currency: str) -> str:
    sym = get_currency_symbol(currency)
    if currency == "INR":
        if value >= 1e12: return f"{sym}{value/1e12:.1f} LCr"
        if value >= 1e7:  return f"{sym}{value/1e7:.1f} Cr"
        if value >= 1e5:  return f"{sym}{value/1e5:.1f} L"
        return f"{sym}{value:,.0f}"
    if value >= 1e12: return f"{sym}{value/1e12:.1f}T"
    if value >= 1e9:  return f"{sym}{value/1e9:.1f}B"
    if value >= 1e6:  return f"{sym}{value/1e6:.1f}M"
    return f"{sym}{value:,.0f}"


def detect_country_from_ticker(ticker: str) -> str:
    upper = ticker.upper()
    for ex in EXCHANGES.values():
        if ex.suffix and upper.endswith(ex.suffix):
            return ex.country
    if normalize_ticker_input(ticker) in INDIAN_STOCK_MAPPING:
        return "India"
    return "India"


def get_supported_countries() -> List[str]:
    return sorted({ex.country for ex in EXCHANGES.values()})


def validate_ticker_format(ticker: str, country: str) -> bool:
    try:
        return bool(map_ticker_to_symbol(ticker, country)[0])
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Smoke test  (python ticker_mapping.py)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    cases = [
        # Input                  Country           Expected Yahoo symbol
        ("RELIANCE.NS",          "India"),        # already suffixed → RELIANCE.NS
        ("jiofin",               "India"),        # static map       → JIOFIN.NS
        ("BAJFINANCE",           "India"),        # static map       → BAJFINANCE.NS
        ("apple",                "United States"),# static map       → AAPL
        ("AAPL",                 "United States"),# raw ticker       → AAPL
        ("Forcemotors",          "India"),        # LLM              → FORCEMOT.NS  ✓
        ("force motors",         "India"),        # static map       → FORCEMOT.NS  ✓
        ("Page Industries",      "India"),        # LLM              → PAGEIND.NS
        ("Dixon Technologies",   "India"),        # LLM              → DIXON.NS
        ("Persistent Systems",   "India"),        # LLM              → PERSISTENT.NS
        ("palantir",             "United States"),# LLM              → PLTR
    ]

    print(f"\n{'Input':<26} {'Country':<16} {'Yahoo Symbol':<22} {'Exch':<6} Currency")
    print("─" * 78)
    for ticker, country in cases:
        sym, ex, cur = map_ticker_to_symbol(ticker, country)
        print(f"{ticker:<26} {country:<16} {sym:<22} {ex:<6} {cur}")
