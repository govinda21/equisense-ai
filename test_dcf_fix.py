"""
Comprehensive DCF Valuation Test Suite
Tests the improved DCF implementation for 90%+ success rate
"""

import asyncio
import sys
from pathlib import Path

# Add the agentic-stock-research directory to path
sys.path.insert(0, str(Path(__file__).parent / "agentic-stock-research"))

from app.tools.dcf_valuation import perform_dcf_valuation, RISK_FREE_RATES, SECTOR_TERMINAL_GROWTH


# Test tickers across different markets and sectors
TEST_CASES = [
    # Indian stocks
    {"ticker": "RELIANCE.NS", "name": "Reliance Industries", "country": "IN", "sector": "Energy"},
    {"ticker": "TCS.NS", "name": "TCS", "country": "IN", "sector": "Technology"},
    {"ticker": "HDFCBANK.NS", "name": "HDFC Bank", "country": "IN", "sector": "Financial Services"},
    {"ticker": "INFY.NS", "name": "Infosys", "country": "IN", "sector": "Technology"},
    {"ticker": "ITC.NS", "name": "ITC", "country": "IN", "sector": "Consumer Defensive"},
    
    # US stocks
    {"ticker": "AAPL", "name": "Apple", "country": "US", "sector": "Technology"},
    {"ticker": "MSFT", "name": "Microsoft", "country": "US", "sector": "Technology"},
    {"ticker": "JPM", "name": "JPMorgan", "country": "US", "sector": "Financial Services"},
    {"ticker": "JNJ", "name": "Johnson & Johnson", "country": "US", "sector": "Healthcare"},
    {"ticker": "PG", "name": "Procter & Gamble", "country": "US", "sector": "Consumer Defensive"},
    
    # Edge cases - smaller/volatile stocks
    {"ticker": "TATAMOTORS.NS", "name": "Tata Motors", "country": "IN", "sector": "Consumer Cyclical"},
    {"ticker": "YESBANK.NS", "name": "Yes Bank", "country": "IN", "sector": "Financial Services"},
]


async def test_dcf_valuation(test_case: dict) -> dict:
    """Test DCF valuation for a single ticker"""
    ticker = test_case["ticker"]
    name = test_case["name"]
    
    print(f"\n{'='*80}")
    print(f"Testing: {name} ({ticker})")
    print(f"Expected Country: {test_case['country']}, Sector: {test_case['sector']}")
    print(f"{'='*80}")
    
    try:
        result = await perform_dcf_valuation(ticker, current_price=None)
        
        # Check if DCF succeeded
        if "error" in result:
            print(f"❌ FAILED: {result['error']}")
            return {
                "ticker": ticker,
                "name": name,
                "status": "failed",
                "error": result["error"]
            }
        
        # Validate results
        intrinsic_value = result.get("intrinsic_value")
        wacc = result.get("key_assumptions", {}).get("wacc")
        terminal_growth = result.get("key_assumptions", {}).get("terminal_growth")
        
        print(f"✅ SUCCESS")
        print(f"   Intrinsic Value: ${intrinsic_value:,.2f}" if intrinsic_value else "   Intrinsic Value: N/A")
        print(f"   WACC: {wacc:.2%}" if wacc else "   WACC: N/A")
        print(f"   Terminal Growth: {terminal_growth:.2%}" if terminal_growth else "   Terminal Growth: N/A")
        
        # Check scenarios
        scenarios = result.get("scenario_results", [])
        print(f"   Scenarios: {len(scenarios)}/3 completed")
        for scenario in scenarios:
            scenario_name = scenario.get("scenario")
            scenario_value = scenario.get("result", {}).get("intrinsic_value_per_share", 0)
            print(f"      - {scenario_name}: ${scenario_value:,.2f}")
        
        # Validate reasonableness
        warnings = []
        if intrinsic_value and intrinsic_value < 0:
            warnings.append("Negative intrinsic value")
        if intrinsic_value and intrinsic_value > 1e6:
            warnings.append("Unreasonably high intrinsic value")
        if wacc and (wacc < 0.05 or wacc > 0.30):
            warnings.append(f"WACC outside normal range: {wacc:.2%}")
        if terminal_growth and (terminal_growth < 0.01 or terminal_growth > 0.05):
            warnings.append(f"Terminal growth outside normal range: {terminal_growth:.2%}")
        if wacc and terminal_growth and terminal_growth >= wacc:
            warnings.append("Terminal growth >= WACC (Gordon Growth violation)")
        
        if warnings:
            print(f"   ⚠️  Warnings: {', '.join(warnings)}")
        
        return {
            "ticker": ticker,
            "name": name,
            "status": "success",
            "intrinsic_value": intrinsic_value,
            "wacc": wacc,
            "terminal_growth": terminal_growth,
            "scenarios_completed": len(scenarios),
            "warnings": warnings
        }
        
    except Exception as e:
        print(f"❌ EXCEPTION: {str(e)}")
        import traceback
        traceback.print_exc()
        
        return {
            "ticker": ticker,
            "name": name,
            "status": "exception",
            "error": str(e)
        }


async def main():
    """Run comprehensive DCF test suite"""
    print("="*80)
    print("DCF VALUATION FIX - COMPREHENSIVE TEST SUITE")
    print("="*80)
    print(f"\nTesting {len(TEST_CASES)} tickers across different markets and sectors...")
    print(f"\nTarget: 90%+ success rate")
    print(f"\nRisk-Free Rates: {RISK_FREE_RATES}")
    print(f"\nSector Terminal Growth Rates (sample): {dict(list(SECTOR_TERMINAL_GROWTH.items())[:5])}")
    
    # Run all tests
    results = []
    for test_case in TEST_CASES:
        result = await test_dcf_valuation(test_case)
        results.append(result)
        await asyncio.sleep(1)  # Rate limiting
    
    # Calculate statistics
    print("\n\n" + "="*80)
    print("TEST RESULTS SUMMARY")
    print("="*80)
    
    total = len(results)
    successes = sum(1 for r in results if r["status"] == "success")
    failures = sum(1 for r in results if r["status"] == "failed")
    exceptions = sum(1 for r in results if r["status"] == "exception")
    
    success_rate = (successes / total * 100) if total > 0 else 0
    
    print(f"\nTotal Tests: {total}")
    print(f"✅ Successes: {successes} ({success_rate:.1f}%)")
    print(f"❌ Failures: {failures} ({failures/total*100:.1f}%)")
    print(f"💥 Exceptions: {exceptions} ({exceptions/total*100:.1f}%)")
    
    # Success rate evaluation
    print(f"\n{'='*80}")
    if success_rate >= 90:
        print(f"🎉 TARGET ACHIEVED! Success rate: {success_rate:.1f}% >= 90%")
    elif success_rate >= 75:
        print(f"⚠️  CLOSE TO TARGET! Success rate: {success_rate:.1f}% (target: 90%)")
    else:
        print(f"❌ BELOW TARGET! Success rate: {success_rate:.1f}% (target: 90%)")
    print(f"{'='*80}")
    
    # List failures for debugging
    if failures > 0 or exceptions > 0:
        print("\n\nFAILED/EXCEPTION CASES:")
        print("-" * 80)
        for r in results:
            if r["status"] in ["failed", "exception"]:
                print(f"\n{r['name']} ({r['ticker']})")
                print(f"  Status: {r['status']}")
                print(f"  Error: {r.get('error', 'N/A')}")
    
    # List warnings
    warned = [r for r in results if r.get("warnings")]
    if warned:
        print("\n\nCASES WITH WARNINGS:")
        print("-" * 80)
        for r in warned:
            print(f"\n{r['name']} ({r['ticker']})")
            for warning in r["warnings"]:
                print(f"  - {warning}")
    
    print("\n\n" + "="*80)
    print("TEST SUITE COMPLETED")
    print("="*80)
    
    return success_rate >= 90


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

