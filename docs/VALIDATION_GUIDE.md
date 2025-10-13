# API Validation Test Suite Guide

**Last Updated**: October 13, 2025  
**Version**: 1.0

---

## Overview

The API Validation Test Suite is an automated testing framework that validates EquiSense AI API responses against ground truth data from Screener.in. It runs daily to catch data source issues early and ensure data accuracy.

---

## Installation

### 1. Install Validation Dependencies

```bash
# Install Python dependencies
pip install -e ".[validation]"

# Install Playwright browser
playwright install chromium
```

### 2. Verify Installation

```bash
# Test that Playwright is working
python -c "from playwright.async_api import async_playwright; print('✅ Playwright installed')"

# Test that API is running
curl http://localhost:8000/health
```

---

## Usage

### Quick Test (3 stocks)

Run validation on a small set of stocks for quick verification:

```bash
cd agentic-stock-research
pytest tests/validation/test_api_validation.py::test_fundamentals_accuracy -v
```

### Full Daily Test (12 stocks)

Run the complete daily validation suite:

```bash
cd agentic-stock-research
pytest tests/validation/ -v
```

### Test Specific Ticker

```bash
pytest tests/validation/test_api_validation.py::test_fundamentals_accuracy[HDFCBANK.NS] -v
```

### Generate HTML Report

```bash
pytest tests/validation/ -v --html=tests/validation/reports/report.html --self-contained-html
```

---

## Architecture

### Components

```
tests/validation/
├── __init__.py                    # Package init
├── conftest.py                    # Pytest fixtures
├── test_api_validation.py         # Main test suite
├── ground_truth_scraper.py        # Screener.in scraper
├── validation_rules.py            # Tolerance rules & validators
├── test_data.py                   # Test ticker configurations
├── reporter.py                    # HTML/CSV report generator
└── reports/                       # Generated reports
    ├── validation_report_*.html
    ├── validation_results_*.csv
    └── validation_results_*.json
```

### Data Flow

```
1. Fire API Request (httpx)
   ↓
2. Extract Fundamentals from Response
   ↓
3. Scrape Ground Truth (Playwright → Screener.in)
   ↓
4. Validate Each Field (ValidationEngine)
   ↓
5. Generate Reports (HTML, CSV, JSON)
```

---

## Test Ticker Configuration

### Test Sets

**Quick Test Set** (3 stocks - fast validation):
- HDFCBANK.NS (Banking)
- TCS.NS (IT)
- RELIANCE.NS (Conglomerate)

**Daily Test Set** (12 stocks - comprehensive):
- HDFCBANK.NS, ICICIBANK.NS (Banking)
- TCS.NS, INFY.NS, WIPRO.NS (IT)
- RELIANCE.NS (Conglomerate)
- HINDUNILVR.NS, ITC.NS (FMCG)
- MARUTI.NS (Auto)
- AXISBANK.NS, SBIN.NS (Banking)
- BHARTIARTL.NS (Telecom)

### Adding New Tickers

Edit `tests/validation/test_data.py`:

```python
TICKER_TO_SCREENER_ID = {
    "NEWTICKER.NS": "new-company-slug",  # Add here
}

DAILY_TEST_SET = [
    "NEWTICKER.NS",  # Add to daily tests
]
```

---

## Validation Rules

### Tolerance Levels

| Field | Tolerance | Critical | Reason |
|-------|-----------|----------|--------|
| Current Price | ±2% | ✅ | Market data changes frequently |
| Market Cap | ±5% | ✅ | Important for valuations |
| D/E Ratio | ±5% | ✅ | Known issue area |
| ROE | ±10% | ✅ | Key profitability metric |
| PE Ratio | ±10% | ❌ | Can vary by calculation method |
| Revenue | ±2% | ✅ | Reported financial data |
| Operating Margin | ±15% | ❌ | Calculation differences |

### Adjusting Tolerances

Edit `tests/validation/validation_rules.py`:

```python
VALIDATION_RULES = {
    "field_name": {
        "tolerance_pct": 10.0,  # Adjust tolerance
        "critical": True,        # Mark as critical
        "description": "Field description"
    }
}
```

---

## Reports

### HTML Report

Generated automatically after each test run:

**Location**: `tests/validation/reports/validation_report_*.html`

**Contents**:
- Summary statistics (pass rate, failures)
- Per-ticker validation results
- Color-coded status indicators
- Detailed comparison tables

**Example**:
```
Validation Report - 2025-10-13
================================
Overall Pass Rate: 87.5% (105/120 fields)
Critical Failures: 2

Summary by Ticker:
- HDFCBANK.NS: ✅ Pass (12/12 fields)
- ICICIBANK.NS: ⚠️ Warning (10/12 fields)
- TCS.NS: ❌ Fail (1 critical failure)
```

### CSV Report

Machine-readable format for analysis:

**Location**: `tests/validation/reports/validation_results_*.csv`

**Columns**:
- Timestamp
- Ticker
- Field
- API Value
- Ground Truth
- Difference %
- Status
- Critical
- Message

### JSON Report

Structured data for programmatic access:

**Location**: `tests/validation/reports/validation_results_*.json`

---

## CI/CD Integration

### GitHub Actions

Daily validation runs automatically via GitHub Actions:

**Workflow**: `.github/workflows/daily_validation.yml`

**Schedule**: 2 AM UTC daily

**Triggers**:
- Scheduled (daily)
- Manual (workflow_dispatch)

**Artifacts**:
- HTML reports
- CSV results
- pytest HTML output

**Notifications**:
- Slack alert on failure (requires `SLACK_WEBHOOK_URL` secret)

### Manual Trigger

```bash
# Via GitHub UI:
Actions → Daily API Validation → Run workflow

# Via GitHub CLI:
gh workflow run daily_validation.yml
```

---

## Troubleshooting

### Issue: Playwright Browser Not Found

```bash
# Solution: Install Playwright browsers
playwright install chromium

# Verify installation
playwright --version
```

### Issue: Scraper Returns Empty Data

**Causes**:
- Screener.in changed their HTML structure
- Rate limiting / anti-scraping measures
- Incorrect ticker to Screener ID mapping

**Solutions**:
1. Check if URL is accessible: `https://www.screener.in/company/hdfc-bank/`
2. Update CSS selectors in `ground_truth_scraper.py`
3. Add delays between requests
4. Clear cache: `rm -rf tests/validation/.cache/*`

### Issue: API Request Timeout

```bash
# Solution: Increase timeout in test
# Edit conftest.py:
async with httpx.AsyncClient(timeout=120.0) as client:  # Increase from 60
```

### Issue: High Failure Rate

**Check**:
1. Is API server running? `curl http://localhost:8000/health`
2. Are yfinance data sources working?
3. Has Screener.in data been updated recently?
4. Review tolerance levels in `validation_rules.py`

### Issue: Cache Issues

```bash
# Clear all cached Screener data
rm -rf agentic-stock-research/tests/validation/.cache/*

# Force re-scrape by reducing cache TTL
# Edit ground_truth_scraper.py:
ScreenerScraper(cache_ttl_hours=1)  # Reduce from 24
```

---

## Best Practices

### 1. Run Locally Before Pushing

```bash
# Quick validation
pytest tests/validation/ -v -k "HDFCBANK"

# Full validation
pytest tests/validation/ -v
```

### 2. Review Reports

Always review HTML reports after failures:
- Check which fields failed
- Compare API vs ground truth values
- Assess if tolerance adjustment needed

### 3. Update Test Data

Review and update test tickers monthly:
- Add newly listed companies
- Remove delisted tickers
- Ensure sector diversity

### 4. Monitor Trends

Track validation pass rates over time:
- Daily: Should be >85%
- Weekly avg: Should be >90%
- Critical failures: Should be 0

### 5. Handle Breaking Changes

If Screener.in changes their layout:
1. Use browser dev tools to inspect new structure
2. Update CSS selectors in `ground_truth_scraper.py`
3. Test manually before committing
4. Update this guide with new selectors

---

## Maintenance

### Weekly Tasks

- Review validation reports
- Investigate consistent failures
- Adjust tolerances if needed

### Monthly Tasks

- Update test ticker list
- Review and archive old reports
- Check for Screener.in layout changes

### Quarterly Tasks

- Review tolerance levels
- Update documentation
- Backtest validation accuracy

---

## Advanced Usage

### Custom Validation Rules

Create custom rules for specific fields:

```python
from tests.validation.validation_rules import ValidationEngine

# Create engine with custom rules
custom_rules = {
    "my_field": {"tolerance_pct": 5.0, "critical": True}
}
engine = ValidationEngine(rules=custom_rules)

# Validate
result = engine.validate_numeric("TICKER", "my_field", api_val, truth_val)
```

### Parallel Execution

Run tests in parallel for faster execution:

```bash
pytest tests/validation/ -n auto  # Requires pytest-xdist
```

### Debugging Tests

```bash
# Run with detailed logging
pytest tests/validation/ -v -s --log-cli-level=DEBUG

# Run specific test with pdb
pytest tests/validation/ -k "test_name" --pdb
```

---

## FAQ

**Q: How long does a full validation run take?**  
A: ~5-10 minutes for 12 stocks (with caching). First run may take longer.

**Q: Can I run validation without starting the API server?**  
A: No, the API must be running on `localhost:8000`.

**Q: What if a stock is delisted?**  
A: Remove it from `DAILY_TEST_SET` in `test_data.py`.

**Q: How accurate is Screener.in data?**  
A: Very accurate for Indian stocks. They source from official filings. However, timing differences may cause temporary mismatches.

**Q: Why are some fields always N/A?**  
A: Either:
- API doesn't provide that field
- Screener.in doesn't show it
- Scraper couldn't extract it (check logs)

**Q: How do I add email notifications?**  
A: Add email action to `.github/workflows/daily_validation.yml` or integrate with your monitoring system.

---

## Support

For issues or questions:
1. Check this guide
2. Review validation reports
3. Check logs: `tests/validation/logs/`
4. Create GitHub issue with:
   - Test command used
   - Error message
   - Relevant log snippets
   - Report files (if available)

---

## Changelog

### v1.0 (2025-10-13)
- Initial release
- Screener.in scraper with Playwright
- Validation engine with tolerance rules
- HTML/CSV/JSON report generation
- GitHub Actions daily workflow
- Quick (3) and Daily (12) test sets

---

## License

Proprietary - EquiSense AI


