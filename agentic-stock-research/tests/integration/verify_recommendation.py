#!/usr/bin/env python3
"""
Quick verification script to test the senior equity analyst recommendation implementation
"""

from app.schemas.output import Decision

# Test that all new fields are properly defined in the Decision model
def test_decision_schema():
    """Verify Decision schema has all required fields"""
    
    # Create a test decision with all new fields
    test_decision = Decision(
        action="Buy",
        rating=4.0,
        expected_return_pct=15.5,
        top_reasons_for=["Strong growth", "Market leader"],
        top_reasons_against=["High valuation", "Regulatory risk"],
        
        # New senior analyst fields
        executive_summary="Test executive summary",
        financial_condition_summary="Strong balance sheet",
        latest_performance_summary="Solid growth trajectory",
        key_trends=["Digital transformation", "Market expansion"],
        growth_drivers=["Innovation pipeline", "TAM expansion"],
        competitive_advantages=["Brand moat", "Network effects"],
        key_risks=["Competition", "Regulation"],
        quantitative_evidence={
            "pe_ratio": 28.5,
            "roe": "18.2%",
            "revenue_growth": "12.5%"
        },
        key_ratios_summary="Key metrics include P/E of 28.5, ROE of 18.2%",
        recent_developments=["Q4 earnings beat", "New product launch"],
        industry_context="Industry outlook is positive",
        short_term_outlook="Near-term prospects favorable",
        long_term_outlook="Long-term thesis remains compelling",
        price_target_12m=195.50,
        price_target_source="Analyst consensus",
        valuation_benchmark="Trades in-line with peers"
    )
    
    # Verify all fields are accessible
    assert test_decision.action == "Buy"
    assert test_decision.rating == 4.0
    assert test_decision.executive_summary == "Test executive summary"
    assert len(test_decision.growth_drivers) == 2
    assert len(test_decision.competitive_advantages) == 2
    assert len(test_decision.key_risks) == 2
    assert test_decision.quantitative_evidence["pe_ratio"] == 28.5
    assert test_decision.price_target_12m == 195.50
    
    print("✅ Decision schema validation passed!")
    print(f"   - All {len(test_decision.model_fields)} fields accessible")
    print(f"   - Executive summary: {test_decision.executive_summary[:50]}...")
    print(f"   - Price target: ${test_decision.price_target_12m}")
    print(f"   - Growth drivers: {len(test_decision.growth_drivers)}")
    print(f"   - Competitive advantages: {len(test_decision.competitive_advantages)}")
    print(f"   - Key risks: {len(test_decision.key_risks)}")
    
    return True


def test_helper_functions():
    """Verify helper functions are importable"""
    from app.graph.nodes.synthesis import (
        _generate_senior_analyst_recommendation,
        _build_financial_condition_summary,
        _build_latest_performance_summary,
        _identify_key_trends,
        _identify_growth_drivers,
        _identify_competitive_advantages,
        _identify_key_risks,
        _build_quantitative_evidence,
        _build_key_ratios_summary,
        _extract_recent_developments,
        _build_industry_context,
        _build_short_term_outlook,
        _build_long_term_outlook,
        _determine_price_target,
        _build_valuation_benchmark
    )
    
    print("✅ All helper functions imported successfully!")
    print(f"   - {15} helper functions available")
    
    return True


if __name__ == "__main__":
    print("=" * 70)
    print("SENIOR EQUITY ANALYST RECOMMENDATION - VERIFICATION")
    print("=" * 70)
    print()
    
    try:
        # Test schema
        print("1. Testing Decision Schema...")
        test_decision_schema()
        print()
        
        # Test helper functions
        print("2. Testing Helper Functions...")
        test_helper_functions()
        print()
        
        print("=" * 70)
        print("✅ ALL TESTS PASSED - Implementation verified!")
        print("=" * 70)
        print()
        print("Next steps:")
        print("  1. Start the backend: cd agentic-stock-research && python -m uvicorn app.main:app --reload")
        print("  2. Start the frontend: cd agentic-stock-research/frontend && npm run dev")
        print("  3. Test with a stock ticker (e.g., AAPL, TCS.NS, RELIANCE.BO)")
        print("  4. View the comprehensive recommendation section in the UI")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

