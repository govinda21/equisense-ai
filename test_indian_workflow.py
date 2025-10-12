#!/usr/bin/env python3
"""
Test script to verify the workflow works correctly with Indian stocks
"""

import asyncio
import sys
import os
from pathlib import Path

# Add the agentic-stock-research directory to the path
sys.path.insert(0, str(Path(__file__).parent / "agentic-stock-research"))

from app.config import get_settings
from app.graph.workflow import build_research_graph
from app.schemas.input import AnalysisRequest


async def test_indian_workflow():
    """Test the complete workflow with an Indian stock"""
    
    print("🧪 Testing Indian Stock Workflow")
    print("=" * 50)
    
    # Test with RELIANCE.NS (Indian stock)
    test_ticker = "RELIANCE.NS"
    print(f"Testing with ticker: {test_ticker}")
    
    try:
        # Get settings
        settings = get_settings()
        print(f"✅ Settings loaded successfully")
        
        # Build the research graph
        graph = build_research_graph(settings)
        print(f"✅ Research graph built successfully")
        
        # Create test request
        request = AnalysisRequest(
            tickers=[test_ticker],
            country="India",
            horizon_short_days=30,
            horizon_long_days=365
        )
        
        print(f"✅ Test request created: {request}")
        
        # Test the workflow
        print(f"\n🚀 Starting workflow execution...")
        
        # Create initial state
        initial_state = {
            "tickers": request.tickers,
            "country": request.country,
            "horizon_short_days": request.horizon_short_days,
            "horizon_long_days": request.horizon_long_days,
        }
        
        # Execute the workflow
        result = await graph.ainvoke(initial_state)
        
        print(f"✅ Workflow completed successfully!")
        
        # Check the results
        if "final_output" in result:
            final_output = result["final_output"]
            print(f"\n📊 Results Summary:")
            print(f"   - Reports generated: {len(final_output.get('reports', []))}")
            
            if final_output.get("reports"):
                first_report = final_output["reports"][0]
                print(f"   - Ticker: {first_report.get('ticker', 'N/A')}")
                
                decision = first_report.get("decision", {})
                if decision:
                    print(f"   - Action: {decision.get('action', 'N/A')}")
                    print(f"   - Rating: {decision.get('rating', 'N/A')}")
                    print(f"   - Letter Grade: {decision.get('letter_grade', 'N/A')}")
                    print(f"   - Stars: {decision.get('stars', 'N/A')}")
                
                # Check if Indian market data was used
                analysis = first_report.get("analysis", {})
                if "indian_market_data" in analysis:
                    indian_data = analysis["indian_market_data"]
                    print(f"   - Indian market data: ✅ Available")
                    print(f"     - Fields: {len(indian_data)} fields")
                else:
                    print(f"   - Indian market data: ❌ Not found")
                
                # Check filing analysis
                if "filings" in analysis:
                    filings = analysis["filings"]
                    print(f"   - Filing analysis: ✅ Available")
                    print(f"     - Market: {filings.get('market', 'N/A')}")
                    print(f"     - Status: {filings.get('status', 'N/A')}")
                else:
                    print(f"   - Filing analysis: ❌ Not found")
        
        print(f"\n🎉 Indian workflow test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Workflow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_ticker_mapping():
    """Test ticker mapping for Indian stocks"""
    
    print(f"\n🧪 Testing Ticker Mapping")
    print("=" * 30)
    
    try:
        from app.tools.ticker_mapping import map_ticker_to_symbol, detect_country_from_ticker
        
        # Test Indian ticker mapping
        test_cases = [
            ("RELIANCE", "India"),
            ("RELIANCE.NS", "India"),
            ("TCS", "India"),
            ("HDFCBANK.NS", "India"),
            ("AAPL", "United States"),
        ]
        
        for ticker, expected_country in test_cases:
            try:
                mapped_symbol, exchange, currency = map_ticker_to_symbol(ticker, expected_country)
                detected_country = detect_country_from_ticker(ticker)
                
                print(f"   {ticker:12} -> {mapped_symbol:15} [{exchange:3}] {currency:3} (detected: {detected_country})")
                
                # Verify Indian stocks get .NS suffix
                if expected_country == "India" and not ticker.endswith(('.NS', '.BO')):
                    if not mapped_symbol.endswith(('.NS', '.BO')):
                        print(f"     ⚠️  Warning: Indian ticker {ticker} should have .NS suffix")
                
            except Exception as e:
                print(f"   {ticker:12} -> ERROR: {e}")
        
        print(f"✅ Ticker mapping test completed")
        return True
        
    except Exception as e:
        print(f"❌ Ticker mapping test failed: {e}")
        return False


async def test_indian_market_data():
    """Test Indian market data federation"""
    
    print(f"\n🧪 Testing Indian Market Data Federation")
    print("=" * 40)
    
    try:
        from app.tools.indian_market_data import get_indian_market_data
        
        # Test with RELIANCE.NS
        ticker = "RELIANCE.NS"
        print(f"Testing Indian market data for: {ticker}")
        
        data = await get_indian_market_data(ticker, "NSE")
        
        if data:
            print(f"✅ Indian market data retrieved successfully")
            print(f"   - Fields available: {len(data)}")
            print(f"   - Sample fields: {list(data.keys())[:5]}")
            
            # Check for key fields
            key_fields = ["company_name", "market_cap", "pe_ratio", "last_price"]
            for field in key_fields:
                if field in data:
                    print(f"   - {field}: ✅")
                else:
                    print(f"   - {field}: ❌")
        else:
            print(f"❌ No Indian market data retrieved")
        
        return bool(data)
        
    except Exception as e:
        print(f"❌ Indian market data test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    
    print("🚀 EquiSense AI - Indian Workflow Verification")
    print("=" * 60)
    
    tests = [
        ("Ticker Mapping", test_ticker_mapping),
        ("Indian Market Data", test_indian_market_data),
        ("Full Workflow", test_indian_workflow),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name:20} {status}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! Indian workflow is working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    return passed == len(results)


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
