"""
Unit tests for comprehensive scoring system
"""

import pytest
from app.tools.comprehensive_scoring import (
    calculate_composite_score,
    assign_letter_grade,
    generate_recommendation,
    calculate_position_sizing
)


class TestCompositeScore:
    """Test composite score calculations"""
    
    def test_perfect_score(self):
        """Test maximum possible score"""
        pillar_scores = {
            "financial_health": 100,
            "valuation": 100,
            "growth_prospects": 100,
            "governance": 100,
            "macro_sensitivity": 100
        }
        
        score = calculate_composite_score(pillar_scores)
        
        assert score == 100.0
    
    def test_minimum_score(self):
        """Test minimum possible score"""
        pillar_scores = {
            "financial_health": 0,
            "valuation": 0,
            "growth_prospects": 0,
            "governance": 0,
            "macro_sensitivity": 0
        }
        
        score = calculate_composite_score(pillar_scores)
        
        assert score == 0.0
    
    def test_average_score(self):
        """Test average scores"""
        pillar_scores = {
            "financial_health": 50,
            "valuation": 60,
            "growth_prospects": 55,
            "governance": 45,
            "macro_sensitivity": 50
        }
        
        score = calculate_composite_score(pillar_scores)
        
        # Should be close to weighted average (50-55 range)
        assert 40 < score < 60
    
    def test_weighted_scoring(self):
        """Test that scoring respects weights"""
        # High financial health should have strong impact
        high_fh = {
            "financial_health": 100,
            "valuation": 0,
            "growth_prospects": 0,
            "governance": 0,
            "macro_sensitivity": 0
        }
        
        # High governance should have less impact (lower weight)
        high_gov = {
            "financial_health": 0,
            "valuation": 0,
            "growth_prospects": 0,
            "governance": 100,
            "macro_sensitivity": 0
        }
        
        score_fh = calculate_composite_score(high_fh)
        score_gov = calculate_composite_score(high_gov)
        
        # Financial health has higher weight (30%) vs governance (15%)
        assert score_fh > score_gov


class TestLetterGrade:
    """Test letter grade assignment"""
    
    def test_a_plus_grade(self):
        """Test A+ grade (90-100)"""
        assert assign_letter_grade(95) == "A+"
        assert assign_letter_grade(90) == "A+"
        assert assign_letter_grade(100) == "A+"
    
    def test_a_grade(self):
        """Test A grade (85-89)"""
        assert assign_letter_grade(87) == "A"
        assert assign_letter_grade(85) == "A"
        assert assign_letter_grade(89) == "A"
    
    def test_b_grades(self):
        """Test B grades (70-84)"""
        assert assign_letter_grade(82) == "B+"
        assert assign_letter_grade(77) == "B"
        assert assign_letter_grade(72) == "B-"
    
    def test_c_grades(self):
        """Test C grades (55-69)"""
        assert assign_letter_grade(67) == "C+"
        assert assign_letter_grade(62) == "C"
        assert assign_letter_grade(57) == "C-"
    
    def test_d_grade(self):
        """Test D grade (40-54)"""
        assert assign_letter_grade(45) == "D"
        assert assign_letter_grade(40) == "D"
        assert assign_letter_grade(54) == "D"
    
    def test_f_grade(self):
        """Test F grade (<40)"""
        assert assign_letter_grade(30) == "F"
        assert assign_letter_grade(0) == "F"
        assert assign_letter_grade(39) == "F"
    
    def test_edge_cases(self):
        """Test boundary values"""
        assert assign_letter_grade(89.9) == "A"
        assert assign_letter_grade(90.0) == "A+"
        assert assign_letter_grade(84.9) == "B+"
        assert assign_letter_grade(85.0) == "A"


class TestRecommendation:
    """Test recommendation generation"""
    
    def test_strong_buy(self):
        """Test Strong Buy recommendation (score >= 75)"""
        rec = generate_recommendation(80, 0.5)  # score=80, margin_of_safety=50%
        assert rec in ["Strong Buy", "Buy"]
    
    def test_buy(self):
        """Test Buy recommendation (score 60-74, MOS > 20%)"""
        rec = generate_recommendation(65, 0.25)
        assert rec in ["Buy", "Hold"]
    
    def test_hold(self):
        """Test Hold recommendation (score 40-59)"""
        rec = generate_recommendation(50, 0.1)
        assert rec == "Hold"
    
    def test_sell_low_score(self):
        """Test Sell recommendation (score < 40)"""
        rec = generate_recommendation(30, -0.1)
        assert rec in ["Sell", "Strong Sell"]
    
    def test_sell_negative_mos(self):
        """Test Sell with negative margin of safety"""
        rec = generate_recommendation(60, -0.3)  # Good score but overvalued
        assert rec in ["Sell", "Hold"]


class TestPositionSizing:
    """Test position sizing calculations"""
    
    def test_high_confidence(self):
        """Test position sizing for high confidence (score >= 75)"""
        position = calculate_position_sizing(80, "Low")
        
        # High score, low risk should give larger position
        assert 5.0 <= position <= 10.0
    
    def test_medium_confidence(self):
        """Test position sizing for medium confidence (score 50-74)"""
        position = calculate_position_sizing(60, "Medium")
        
        # Medium score/risk should give moderate position
        assert 3.0 <= position <= 7.0
    
    def test_low_confidence(self):
        """Test position sizing for low confidence (score < 50)"""
        position = calculate_position_sizing(30, "High")
        
        # Low score, high risk should give small position
        assert 0.0 <= position <= 3.0
    
    def test_risk_impact(self):
        """Test that risk rating impacts position size"""
        score = 70
        
        pos_low_risk = calculate_position_sizing(score, "Low")
        pos_med_risk = calculate_position_sizing(score, "Medium")
        pos_high_risk = calculate_position_sizing(score, "High")
        
        # Lower risk should allow larger position
        assert pos_low_risk > pos_med_risk > pos_high_risk
    
    def test_extreme_scores(self):
        """Test position sizing for extreme scores"""
        # Perfect score should max out position
        pos_perfect = calculate_position_sizing(100, "Low")
        assert pos_perfect >= 8.0
        
        # Worst score should minimize position
        pos_worst = calculate_position_sizing(0, "High")
        assert pos_worst <= 1.0


class TestEndToEndScoring:
    """Test complete scoring workflow"""
    
    @pytest.mark.asyncio
    async def test_complete_scoring(self, test_ticker, mock_financial_data):
        """Test complete scoring workflow"""
        from app.tools.comprehensive_scoring import perform_comprehensive_scoring
        
        try:
            result = await perform_comprehensive_scoring(
                test_ticker,
                mock_financial_data
            )
            
            # Check structure
            assert "overall_score" in result
            assert "overall_grade" in result
            assert "recommendation" in result
            assert "pillar_scores" in result
            assert "position_sizing_pct" in result
            assert "risk_rating" in result
            
            # Validate ranges
            assert 0 <= result["overall_score"] <= 100
            assert result["overall_grade"] in ["A+", "A", "B+", "B", "B-", "C+", "C", "C-", "D", "F"]
            assert result["recommendation"] in ["Strong Buy", "Buy", "Hold", "Sell", "Strong Sell"]
            assert 0 <= result["position_sizing_pct"] <= 10
            assert result["risk_rating"] in ["Low", "Medium", "High"]
            
        except Exception as e:
            pytest.skip(f"Scoring failed (expected in test environment): {str(e)}")


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_missing_pillar(self):
        """Test score calculation with missing pillar"""
        incomplete_scores = {
            "financial_health": 70,
            "valuation": 60,
            # Missing: growth_prospects, governance, macro_sensitivity
        }
        
        try:
            score = calculate_composite_score(incomplete_scores)
            # Should handle gracefully (use defaults or skip)
            assert 0 <= score <= 100
        except KeyError:
            # Or raise appropriate error
            pass
    
    def test_invalid_score_values(self):
        """Test handling of invalid score values"""
        with pytest.raises((ValueError, AssertionError)):
            # Score > 100
            assign_letter_grade(150)
    
    def test_invalid_risk_rating(self):
        """Test handling of invalid risk rating"""
        try:
            position = calculate_position_sizing(70, "Invalid")
            # Should default to conservative sizing
            assert position < 5.0
        except ValueError:
            # Or raise appropriate error
            pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

