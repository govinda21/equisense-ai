# API Data Validation Test Suite

Automated testing framework that validates EquiSense AI API responses against ground truth data from Screener.in.

## Quick Start

```bash
# Install dependencies
pip install -e ".[validation]"
playwright install chromium

# Run quick validation (3 stocks)
cd agentic-stock-research
python tests/validation/run_validation.py --quick

# Run full daily validation (12 stocks)
python tests/validation/run_validation.py --full

# Test specific ticker
python tests/validation/run_validation.py --ticker HDFCBANK.NS
```

## Using pytest

```bash
# Run all validation tests
pytest tests/validation/ -v

# Run specific test
pytest tests/validation/test_api_validation.py::test_fundamentals_accuracy[HDFCBANK.NS] -v

# Generate HTML report
pytest tests/validation/ -v --html=tests/validation/reports/report.html --self-contained-html
```

## Reports

Reports are generated automatically in `tests/validation/reports/`:
- `validation_report_*.html` - Visual HTML report
- `validation_results_*.csv` - Machine-readable CSV
- `validation_results_*.json` - Structured JSON data

## Documentation

See [VALIDATION_GUIDE.md](../../../docs/VALIDATION_GUIDE.md) for complete documentation.

## Test Tickers

**Quick Test** (3 stocks):
- HDFCBANK.NS (Banking)
- TCS.NS (IT)
- RELIANCE.NS (Conglomerate)

**Daily Test** (12 stocks):
- Banks: HDFCBANK.NS, ICICIBANK.NS, AXISBANK.NS, SBIN.NS
- IT: TCS.NS, INFY.NS, WIPRO.NS
- FMCG: HINDUNILVR.NS, ITC.NS
- Auto: MARUTI.NS
- Telecom: BHARTIARTL.NS
- Conglomerate: RELIANCE.NS

## Validation Rules

Fields are validated with configurable tolerance levels:

| Field | Tolerance | Critical |
|-------|-----------|----------|
| Current Price | ±2% | ✅ |
| Market Cap | ±5% | ✅ |
| D/E Ratio | ±5% | ✅ |
| ROE | ±10% | ✅ |
| Revenue | ±2% | ✅ |
| PE Ratio | ±10% | ❌ |
| Operating Margin | ±15% | ❌ |

## CI/CD

Daily validation runs automatically via GitHub Actions at 2 AM UTC.

Manual trigger:
```bash
gh workflow run daily_validation.yml
```

## Troubleshooting

**Playwright not found:**
```bash
playwright install chromium
```

**API not running:**
```bash
# Start the API first
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Clear cache:**
```bash
rm -rf tests/validation/.cache/*
```

## Architecture

```
tests/validation/
├── run_validation.py          # CLI script
├── test_api_validation.py     # pytest tests
├── ground_truth_scraper.py    # Screener.in scraper
├── validation_rules.py        # Tolerance rules
├── test_data.py               # Ticker configurations
├── reporter.py                # Report generation
└── reports/                   # Generated reports
```

## License

Proprietary - EquiSense AI


