"""
Test script to trace EXACT ROE data for HDFCBANK.NS
"""
import asyncio
import yfinance as yf
from app.tools.fundamentals import compute_fundamentals
from app.tools.comprehensive_scoring import score_stock_comprehensively

async def test_hdfc_roe():
    ticker = "HDFCBANK.NS"
    
    print("\n" + "="*80)
    print(f"ROE DATA FLOW TRACE FOR {ticker}")
    print("="*80)
    
    # Step 1: Raw yfinance data
    print("\n[STEP 1] Raw yfinance data:")
    t = yf.Ticker(ticker)
    info = t.info or {}
    roe_raw = info.get("returnOnEquity")
    print(f"  - info.get('returnOnEquity') = {roe_raw} (type: {type(roe_raw).__name__})")
    
    if roe_raw:
        print(f"  - As percentage: {roe_raw * 100:.2f}%")
    
    # Step 2: After compute_fundamentals
    print("\n[STEP 2] After compute_fundamentals() validation:")
    fund = await compute_fundamentals(ticker)
    roe_fund = fund.get("roe")
    print(f"  - fund.get('roe') = {roe_fund} (type: {type(roe_fund).__name__ if roe_fund else 'None'})")
    
    # Step 3: In scoring engine
    print("\n[STEP 3] In comprehensive scoring:")
    score_result = await score_stock_comprehensively(ticker, current_price=None)
    
    # Get financial health pillar
    financial_health = None
    for pillar in score_result.pillar_scores:
        if "financial" in pillar.pillar.lower():
            financial_health = pillar
            break
    
    if financial_health:
        print(f"  - Financial Health Score: {financial_health.score:.1f}/100")
        print(f"  - Positive Factors: {financial_health.positive_factors}")
        print(f"  - Negative Factors: {financial_health.negative_factors}")
    
    # Step 4: Final check
    print("\n[STEP 4] Expected vs Actual:")
    actual_roe_web = "17-19%"  # From web search
    print(f"  - Expected (from web): {actual_roe_web}")
    print(f"  - System value: {roe_fund}%")
    print(f"  - Match: {'✅ YES' if roe_fund and 17 <= roe_fund <= 19 else '❌ NO'}")
    
    print("\n" + "="*80)
    print("DATA FLOW DIAGNOSIS:")
    print("="*80)
    
    if not roe_raw:
        print("❌ PROBLEM: yfinance returned None/null for returnOnEquity")
        print("   This means Yahoo Finance doesn't have ROE data for this ticker")
        print("   Solution: Need to calculate from financial statements")
    elif roe_fund is None:
        print("❌ PROBLEM: DataValidator rejected the value")
    elif roe_fund < 1:
        print(f"❌ PROBLEM: ROE stored as fraction ({roe_fund}) not percentage")
    elif roe_fund > 100:
        print(f"❌ PROBLEM: ROE multiplied by 100 too many times ({roe_fund})")
    else:
        print(f"✅ ROE value looks reasonable: {roe_fund}%")
    
    print("="*80 + "\n")

if __name__ == "__main__":
    asyncio.run(test_hdfc_roe())

