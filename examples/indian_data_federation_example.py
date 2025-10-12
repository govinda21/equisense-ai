"""
Example usage of Indian Market Data Federation System

Demonstrates how to use the multi-source Indian market data system
to fetch company data with automatic fallback and reconciliation.

Usage:
    python examples/indian_data_federation_example.py
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'agentic-stock-research'))

from app.tools.indian_market_data_v2 import (
    IndianMarketDataFederator,
    fetch_indian_market_data
)


async def example_1_simple_usage():
    """Example 1: Simple single-ticker fetch"""
    print("\n" + "="*80)
    print("EXAMPLE 1: Simple Single-Ticker Fetch")
    print("="*80 + "\n")
    
    ticker = "RELIANCE.NS"
    print(f"Fetching data for {ticker}...")
    
    data = await fetch_indian_market_data(ticker)
    
    if data:
        print(f"\n✓ Successfully fetched data for {ticker}")
        print(f"  Fields available: {list(data.keys())}")
        
        if "company_name" in data:
            print(f"  Company: {data['company_name']}")
        if "last_price" in data:
            print(f"  Price: ₹{data['last_price']:,.2f}")
        if "market_cap" in data:
            print(f"  Market Cap: ₹{data['market_cap']:,.0f}")
    else:
        print(f"\n✗ No data available for {ticker}")


async def example_2_detailed_usage():
    """Example 2: Detailed usage with source tracking"""
    print("\n" + "="*80)
    print("EXAMPLE 2: Detailed Usage with Source Tracking")
    print("="*80 + "\n")
    
    # Create federator instance
    federator = IndianMarketDataFederator(
        bse_api_key=os.getenv("BSE_API_KEY"),
        use_cache=True
    )
    
    try:
        tickers = ["TCS.NS", "INFY.NS", "HDFCBANK.NS"]
        
        for ticker in tickers:
            print(f"\nFetching {ticker}...")
            
            # Get reconciled data
            result = await federator.get_company_data(ticker, max_sources=3)
            
            print(f"  Quality Score: {result.quality_score:.2f}")
            print(f"  Sources Used: {', '.join([s.value for s in result.sources_used])}")
            print(f"  Primary Source: {result.primary_source.value}")
            print(f"  Fields Retrieved: {len(result.data)}")
            
            if result.conflicts:
                print(f"  ⚠️  Conflicts Detected: {len(result.conflicts)}")
                for conflict in result.conflicts[:2]:  # Show first 2
                    print(f"    - {conflict['field']}: {conflict['difference_pct']:.1%} difference")
            
            # Sample data fields
            if result.data:
                print(f"  Data Sample:")
                for key in list(result.data.keys())[:5]:
                    print(f"    - {key}: {result.data[key]}")
    
    finally:
        await federator.close()


async def example_3_health_monitoring():
    """Example 3: Monitor data source health"""
    print("\n" + "="*80)
    print("EXAMPLE 3: Data Source Health Monitoring")
    print("="*80 + "\n")
    
    federator = IndianMarketDataFederator()
    
    try:
        # Fetch some data first to generate statistics
        test_tickers = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS"]
        
        print("Fetching test data to generate statistics...")
        for ticker in test_tickers:
            await federator.get_company_data(ticker, max_sources=2)
        
        # Get health status
        health = await federator.get_health_status()
        
        print(f"\nHealth Status (as of {health['timestamp']}):\n")
        print(f"{'Source':<20} {'Success Rate':<15} {'Total Requests':<15} {'Reliability'}")
        print("-" * 80)
        
        for source in health['sources']:
            print(
                f"{source['type']:<20} "
                f"{source['success_rate']:.1%}{'':11} "
                f"{source['total_requests']:<15} "
                f"{source['reliability_weight']:.2f}"
            )
    
    finally:
        await federator.close()


async def example_4_multiple_tickers_parallel():
    """Example 4: Fetch multiple tickers in parallel"""
    print("\n" + "="*80)
    print("EXAMPLE 4: Multiple Tickers in Parallel")
    print("="*80 + "\n")
    
    federator = IndianMarketDataFederator()
    
    try:
        tickers = [
            "RELIANCE.NS",
            "TCS.NS",
            "HDFCBANK.NS",
            "INFY.NS",
            "ITC.NS"
        ]
        
        print(f"Fetching {len(tickers)} tickers in parallel...\n")
        
        # Fetch all tickers in parallel
        tasks = [
            federator.get_company_data(ticker, max_sources=2)
            for ticker in tickers
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Summarize results
        print(f"{'Ticker':<15} {'Quality':<10} {'Sources':<10} {'Fields'}")
        print("-" * 60)
        
        for ticker, result in zip(tickers, results):
            print(
                f"{ticker:<15} "
                f"{result.quality_score:.2f}{'':6} "
                f"{len(result.sources_used):<10} "
                f"{len(result.data)}"
            )
        
        # Calculate average quality
        avg_quality = sum(r.quality_score for r in results) / len(results)
        print(f"\nAverage Data Quality: {avg_quality:.2f}")
    
    finally:
        await federator.close()


async def example_5_error_handling():
    """Example 5: Error handling and graceful degradation"""
    print("\n" + "="*80)
    print("EXAMPLE 5: Error Handling & Graceful Degradation")
    print("="*80 + "\n")
    
    federator = IndianMarketDataFederator()
    
    try:
        # Try an invalid ticker
        print("Attempting to fetch invalid ticker...")
        result = await federator.get_company_data("INVALID_TICKER_XYZ.NS")
        
        if result.quality_score == 0.0:
            print("✓ Gracefully handled invalid ticker - no crash!")
            print(f"  Returned empty data with quality score: {result.quality_score}")
        else:
            print(f"✓ Partial data retrieved with quality: {result.quality_score:.2f}")
    
    finally:
        await federator.close()


async def main():
    """Run all examples"""
    print("\n")
    print("╔" + "="*78 + "╗")
    print("║" + " "*15 + "Indian Market Data Federation - Examples" + " "*22 + "║")
    print("╚" + "="*78 + "╝")
    
    try:
        await example_1_simple_usage()
        await example_2_detailed_usage()
        await example_3_health_monitoring()
        await example_4_multiple_tickers_parallel()
        await example_5_error_handling()
        
        print("\n" + "="*80)
        print("All examples completed successfully!")
        print("="*80 + "\n")
    
    except KeyboardInterrupt:
        print("\n\nExamples interrupted by user.")
    except Exception as e:
        print(f"\n\n❌ Error running examples: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Run all examples
    asyncio.run(main())

