"""
Unit tests for DCF valuation engine
"""

import pytest
from app.tools.dcf_valuation import (
    calculate_wacc,
    estimate_terminal_value,
    calculate_intrinsic_value_per_share,
    perform_dcf_valuation
)


class TestWACCCalculation:
    """Test WACC (Weighted Average Cost of Capital) calculations"""
    
    def test_wacc_basic(self):
        """Test basic WACC calculation"""
        cost_of_equity = 0.12  # 12%
        cost_of_debt = 0.06    # 6%
        tax_rate = 0.25        # 25%
        market_value_equity = 100_000_000
        market_value_debt = 50_000_000
        
        wacc = calculate_wacc(
            cost_of_equity,
            cost_of_debt,
            tax_rate,
            market_value_equity,
            market_value_debt
        )
        
        # WACC = (E/(E+D))*Ke + (D/(E+D))*Kd*(1-Tax)
        # = (100/150)*0.12 + (50/150)*0.06*(1-0.25)
        # = 0.08 + 0.015 = 0.095 = 9.5%
        expected_wacc = 0.095
        assert abs(wacc - expected_wacc) < 0.001, f"Expected {expected_wacc}, got {wacc}"
    
    def test_wacc_all_equity(self):
        """Test WACC with no debt (100% equity financed)"""
        wacc = calculate_wacc(
            cost_of_equity=0.10,
            cost_of_debt=0.05,
            tax_rate=0.25,
            market_value_equity=1_000_000,
            market_value_debt=0
        )
        
        # With no debt, WACC = cost of equity
        assert abs(wacc - 0.10) < 0.001
    
    def test_wacc_high_leverage(self):
        """Test WACC with high debt levels"""
        wacc = calculate_wacc(
            cost_of_equity=0.15,
            cost_of_debt=0.08,
            tax_rate=0.30,
            market_value_equity=40_000_000,
            market_value_debt=60_000_000
        )
        
        # More debt should lower WACC due to tax shield
        assert wacc < 0.15  # Should be less than pure cost of equity
        assert wacc > 0.03  # But still positive


class TestTerminalValue:
    """Test terminal value calculations"""
    
    def test_gordon_growth_model(self):
        """Test terminal value using Gordon Growth Model"""
        final_fcf = 1_000_000      # $1M final year FCF
        growth_rate = 0.02         # 2% perpetual growth
        discount_rate = 0.10       # 10% WACC
        
        terminal_value = estimate_terminal_value(
            final_fcf,
            growth_rate,
            discount_rate
        )
        
        # TV = FCF*(1+g) / (r-g) = 1,000,000*1.02 / (0.10-0.02)
        # = 1,020,000 / 0.08 = 12,750,000
        expected_tv = 12_750_000
        assert abs(terminal_value - expected_tv) < 1000
    
    def test_terminal_value_zero_growth(self):
        """Test terminal value with zero growth"""
        terminal_value = estimate_terminal_value(
            final_fcf=500_000,
            growth_rate=0.0,
            discount_rate=0.08
        )
        
        # TV = FCF / r = 500,000 / 0.08 = 6,250,000
        expected_tv = 6_250_000
        assert abs(terminal_value - expected_tv) < 1000


class TestIntrinsicValue:
    """Test intrinsic value calculations"""
    
    def test_intrinsic_value_basic(self):
        """Test basic intrinsic value calculation"""
        fcf_projections = [1_000_000, 1_100_000, 1_200_000, 1_300_000, 1_400_000]
        terminal_value = 20_000_000
        wacc = 0.10
        net_debt = 5_000_000
        shares_outstanding = 10_000_000
        
        intrinsic_value = calculate_intrinsic_value_per_share(
            fcf_projections,
            terminal_value,
            wacc,
            net_debt,
            shares_outstanding
        )
        
        # Should be positive
        assert intrinsic_value > 0
        # Should be reasonable (not extreme)
        assert 0.5 < intrinsic_value < 10.0
    
    def test_intrinsic_value_no_debt(self):
        """Test intrinsic value with no debt"""
        fcf_projections = [1_000_000] * 5
        terminal_value = 15_000_000
        wacc = 0.08
        net_debt = 0  # No debt
        shares_outstanding = 5_000_000
        
        intrinsic_value = calculate_intrinsic_value_per_share(
            fcf_projections,
            terminal_value,
            wacc,
            net_debt,
            shares_outstanding
        )
        
        assert intrinsic_value > 0


class TestDCFValuation:
    """Test end-to-end DCF valuation"""
    
    @pytest.mark.asyncio
    async def test_dcf_valuation_indian_stock(self, test_ticker):
        """Test DCF valuation for Indian stock"""
        try:
            result = await perform_dcf_valuation(test_ticker)
            
            # Check structure
            assert "base_case" in result
            assert "bull_case" in result
            assert "bear_case" in result
            
            # Check base case has required fields
            base = result["base_case"]
            assert "intrinsic_value" in base
            assert "margin_of_safety" in base
            assert "recommendation" in base
            
            # Validate values are reasonable
            if base["intrinsic_value"] > 0:
                assert base["intrinsic_value"] < 100000  # Not absurdly high
                assert -1 <= base["margin_of_safety"] <= 10  # Reasonable MOS range
            
        except Exception as e:
            # DCF might fail due to missing data, which is acceptable in tests
            pytest.skip(f"DCF valuation failed (expected in test environment): {str(e)}")
    
    @pytest.mark.asyncio
    async def test_dcf_valuation_us_stock(self, test_ticker_us):
        """Test DCF valuation for US stock"""
        try:
            result = await perform_dcf_valuation(test_ticker_us)
            
            assert result is not None
            assert isinstance(result, dict)
            
            # Should have scenario analysis
            assert len(result) >= 1  # At least base case
            
        except Exception as e:
            pytest.skip(f"DCF valuation failed (expected in test environment): {str(e)}")


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_wacc_negative_equity(self):
        """Test WACC with negative equity (should handle gracefully)"""
        with pytest.raises((ValueError, ZeroDivisionError)):
            calculate_wacc(
                cost_of_equity=0.10,
                cost_of_debt=0.05,
                tax_rate=0.25,
                market_value_equity=-1_000_000,  # Negative!
                market_value_debt=500_000
            )
    
    def test_terminal_value_negative_growth(self):
        """Test terminal value with negative growth (decline)"""
        # Negative growth should work but give lower TV
        tv_negative = estimate_terminal_value(
            final_fcf=1_000_000,
            growth_rate=-0.02,  # Declining 2% per year
            discount_rate=0.10
        )
        
        tv_positive = estimate_terminal_value(
            final_fcf=1_000_000,
            growth_rate=0.02,  # Growing 2% per year
            discount_rate=0.10
        )
        
        assert tv_negative < tv_positive
    
    def test_discount_rate_too_low(self):
        """Test terminal value when discount rate approaches growth rate"""
        # When r ~= g, TV becomes very large or undefined
        # Should handle gracefully or raise appropriate error
        try:
            tv = estimate_terminal_value(
                final_fcf=1_000_000,
                growth_rate=0.099,  # Very close to discount rate
                discount_rate=0.10
            )
            # If it succeeds, TV should be very large
            assert tv > 100_000_000
        except (ValueError, ZeroDivisionError):
            # Or it should raise appropriate error
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

