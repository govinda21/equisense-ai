# Perplexity Fallback Integration - Complete

## Objective
Integrate Perplexity API as a comprehensive fallback data source when primary sources (Yahoo Finance, Screener.in, Indian market data) fail or return incomplete data.

## Implementation Summary

### ✅ 1. `fetch_info()` - Already Had Perplexity Fallback
**File**: `app/tools/finance.py`
- ✅ Already implemented Perplexity fallback on Yahoo Finance failures
- ✅ Enhanced 404 error detection and structured error responses
- ✅ Perplexity data normalized to Yahoo Finance format

### ✅ 2. `compute_fundamentals()` - NEW Perplexity Fallback
**File**: `app/tools/fundamentals.py`
- ✅ Check if primary data source (Yahoo Finance) failed or returned empty
- ✅ If missing price/market cap, attempt Perplexity fallback
- ✅ Merge Perplexity data into `info`, preferring existing values
- ✅ For Indian stocks: Also use Perplexity if Indian sources (NSE/BSE/Screener) fail

**Integration Points**:
```python
# After fetch_info() - if data incomplete
if not info or info.get("_error") or (not info.get("regularMarketPrice") and not info.get("currentPrice")):
    perplexity_data = await fetch_stock_data_perplexity(ticker)
    # Merge Perplexity data into info

# After Indian market data fetch - if empty
if not indian_data or len(indian_data) == 0:
    perplexity_data = await fetch_stock_data_perplexity(ticker)
    indian_data.update(perplexity_data)
```

### ✅ 3. `get_indian_market_data()` - NEW Perplexity Fallback
**File**: `app/tools/indian_market_data.py`
- ✅ Check if Indian market data is empty or incomplete (missing price/market cap)
- ✅ If incomplete, attempt Perplexity fallback
- ✅ Normalize Perplexity data to match Indian market data format
- ✅ Even if provider crashes, try Perplexity as last resort

**Integration Points**:
```python
# After get_comprehensive_company_data()
if not data or len(data) == 0 or (data.get("current_price") is None and data.get("market_cap") is None):
    perplexity_data = await fetch_stock_data_perplexity(ticker)
    # Normalize and merge

# In exception handler
except Exception as e:
    # Try Perplexity even if provider crashes
    perplexity_data = await fetch_stock_data_perplexity(ticker)
```

### ✅ 4. `get_screener_fundamentals()` - NEW Perplexity Fallback
**File**: `app/tools/screener_scraper.py`
- ✅ Check if Screener.in returned empty data
- ✅ If empty, attempt Perplexity fallback
- ✅ Convert Perplexity data to Screener-like format (interest_coverage, roe, pe, pb, etc.)
- ✅ Even if Screener crashes, try Perplexity as last resort

**Integration Points**:
```python
# After scrape_fundamentals() - if empty
if not data or len(data) == 0:
    perplexity_data = await fetch_stock_data_perplexity(ticker)
    # Convert to Screener format

# In exception handler
except Exception as e:
    # Try Perplexity even if Screener crashes
    perplexity_data = await fetch_stock_data_perplexity(ticker)
```

### ✅ 5. `perform_dcf_valuation()` - Already Had Perplexity Fallback
**File**: `app/tools/dcf_valuation.py`
- ✅ Already checks if Yahoo Finance data is incomplete/missing
- ✅ Uses Perplexity fallback if market cap missing
- ✅ Normalizes Perplexity data to DCF format

## Fallback Chain Strategy

For each data source, the fallback chain is:

1. **Primary Source** (Yahoo Finance, Screener.in, NSE/BSE)
   - Try primary source first
   - Check if data is complete (has required fields)
   
2. **Perplexity Fallback**
   - If primary source fails or returns incomplete data
   - Timeout: 20 seconds max
   - Normalize Perplexity data to match primary source format
   
3. **Graceful Degradation**
   - If Perplexity also fails, return empty dict `{}`
   - Analysis continues with best-effort using available data

## Data Normalization

Perplexity data is normalized to match each source's expected format:

- **Yahoo Finance format**: `regularMarketPrice`, `marketCap`, `trailingPE`, etc.
- **Screener format**: `interest_coverage`, `roe`, `pe`, `pb`, `dividend_yield`, etc.
- **Indian market format**: `current_price`, `market_cap`, `pe_ratio`, `pb_ratio`, etc.
- **DCF format**: `marketCap`, `currentPrice`, `totalRevenue`, etc.

## Benefits

1. **Higher Success Rate**: Stocks with 404 errors (OBEROI.NS, SUNTEKREALTY.NS, etc.) can still be analyzed
2. **Better Data Coverage**: Perplexity provides real-time web data that may not be in Yahoo Finance
3. **Graceful Degradation**: Analysis continues even if some sources fail
4. **Consistent API**: All fallbacks use same `fetch_stock_data_perplexity()` function

## Testing

Expected results after this fix:
- ✅ Bulk analysis should show higher success rate (fewer "Failed" stocks)
- ✅ Stocks like OBEROI.NS, SUNTEKREALTY.NS should complete with Perplexity data
- ✅ Logs should show "✅ Perplexity provided data" messages
- ✅ Data quality may vary (Perplexity vs Yahoo Finance) but analysis should complete
