"""
Unit tests for comprehensive scoring system
"""

import pytest
from app.tools.comprehensive_scoring import (
    score_stock_comprehensively,
    _score_to_grade,
    ComprehensiveScoringEngine,
    ScoringWeights
)

class TestCompositeScore:
    """Test composite score calculations"""

    @pytest.mark.asyncio
    async def test_perfect_score(self):
        """Test maximum possible score"""
        pillar_scores = {
            "financial_health": 100,
            "valuation": 100,
            "growth_prospects": 100,
            "governance": 100,
            "macro_sensitivity": 100
        }

        engine = ComprehensiveScoringEngine()
        result = await engine.score_ticker("TEST", current_price=100)

        assert result.overall_score == 100.0

    @pytest.mark.asyncio
    async def test_minimum_score(self):
        """Test minimum possible score"""
        pillar_scores = {
            "financial_health": 0,
            "valuation": 0,
            "growth_prospects": 0,
            "governance": 0,
            "macro_sensitivity": 0
        }

        engine = ComprehensiveScoringEngine()
        result = await engine.score_ticker("TEST", current_price=0)

        assert result.overall_score == 0.0

    @pytest.mark.asyncio
    async def test_average_score(self):
        """Test average scores"""
        pillar_scores = {
            "financial_health": 50,
            "valuation": 60,
            "growth_prospects": 55,
            "governance": 45,
            "macro_sensitivity": 50
        }

        engine = ComprehensiveScoringEngine()
        result = await engine.score_ticker("TEST", current_price=50)

        assert 40 < result.overall_score < 60

    @pytest.mark.asyncio
    async def test_weighted_scoring(self):
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

        engine = ComprehensiveScoringEngine()
        score_fh = (await engine.score_ticker("TEST", current_price=100)).overall_score
        score_gov = (await engine.score_ticker("TEST", current_price=100)).overall_score

        # Financial health has higher weight (30%) vs governance (15%)
        assert score_fh > score_gov

class TestLetterGrade:
    """Test letter grade assignment"""

    def test_a_plus_grade(self):
        """Test A+ grade (90-100)"""
        assert _score_to_grade(95) == "A+"
        assert _score_to_grade(90) == "A+"
        assert _score_to_grade(100) == "A+"

    def test_a_grade(self):
        """Test A grade (85-89)"""
        assert _score_to_grade(87) == "A"
        assert _score_to_grade(85) == "A"
        assert _score_to_grade(89) == "A"

    def test_b_grades(self):
        """Test B grades (70-84)"""
        assert _score_to_grade(82) == "B+"
        assert _score_to_grade(77) == "B"
        assert _score_to_grade(72) == "B-"

    def test_c_grades(self):
        """Test C grades (55-69)"""
        assert _score_to_grade(67) == "C+"
        assert _score_to_grade(62) == "C"
        assert _score_to_grade(57) == "C-"

    def test_d_grade(self):
        """Test D grade (40-54)"""
        assert _score_to_grade(45) == "D"
        assert _score_to_grade(40) == "D"
        assert _score_to_grade(54) == "D"

    def test_f_grade(self):
        """Test F grade (<40)"""
        assert _score_to_grade(30) == "F"
        assert _score_to_grade(0) == "F"
        assert _score_to_grade(39) == "F"

    def test_edge_cases(self):
        """Test boundary values"""
        assert _score_to_grade(89.9) == "A"
        assert _score_to_grade(90.0) == "A+"
        assert _score_to_grade(84.9) == "B+"
        assert _score_to_grade(85.0) == "A"

