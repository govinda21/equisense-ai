"""
Validation rules engine with tolerance checks and comparison logic
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


# Validation tolerance rules
VALIDATION_RULES = {
    # Price data - strict tolerance (market data changes frequently)
    "current_price": {"tolerance_pct": 2.0, "critical": True, "description": "Stock current price"},
    "market_cap": {"tolerance_pct": 5.0, "critical": True, "description": "Market capitalization"},
    
    # Financial ratios - moderate tolerance (calculation differences)
    "pe_ratio": {"tolerance_pct": 10.0, "critical": False, "description": "Price to Earnings ratio"},
    "pb_ratio": {"tolerance_pct": 10.0, "critical": False, "description": "Price to Book ratio"},
    "debt_to_equity": {"tolerance_pct": 5.0, "critical": True, "description": "Debt to Equity ratio"},
    
    # Profitability metrics - moderate tolerance
    "roe": {"tolerance_pct": 10.0, "critical": True, "description": "Return on Equity"},
    "roce": {"tolerance_pct": 10.0, "critical": False, "description": "Return on Capital Employed"},
    "roic": {"tolerance_pct": 10.0, "critical": False, "description": "Return on Invested Capital"},
    "operating_margin": {"tolerance_pct": 15.0, "critical": False, "description": "Operating Profit Margin"},
    "net_margin": {"tolerance_pct": 15.0, "critical": False, "description": "Net Profit Margin"},
    "ebitda_margin": {"tolerance_pct": 15.0, "critical": False, "description": "EBITDA Margin"},
    
    # Income statement - strict tolerance (reported values)
    "revenue": {"tolerance_pct": 2.0, "critical": True, "description": "Total Revenue"},
    "net_profit": {"tolerance_pct": 5.0, "critical": True, "description": "Net Profit"},
    "ebitda": {"tolerance_pct": 5.0, "critical": False, "description": "EBITDA"},
    
    # Balance sheet
    "total_assets": {"tolerance_pct": 5.0, "critical": False, "description": "Total Assets"},
    "total_debt": {"tolerance_pct": 5.0, "critical": True, "description": "Total Debt"},
    "equity": {"tolerance_pct": 5.0, "critical": True, "description": "Total Equity"},
    
    # Coverage ratios - wider tolerance (complex calculations)
    "interest_coverage": {"tolerance_pct": 20.0, "critical": False, "description": "Interest Coverage Ratio"},
    
    # Cash flow metrics
    "fcf_yield": {"tolerance_pct": 15.0, "critical": False, "description": "Free Cash Flow Yield"},
    "operating_cash_flow": {"tolerance_pct": 10.0, "critical": False, "description": "Operating Cash Flow"},
}


@dataclass
class ValidationResult:
    """Result of a single field validation"""
    ticker: str
    field: str
    api_value: Optional[float]
    ground_truth: Optional[float]
    diff_pct: Optional[float]
    tolerance_pct: float
    passed: bool
    critical: bool
    description: str
    message: str


class ValidationEngine:
    """Engine for validating API data against ground truth"""
    
    def __init__(self, rules: Dict[str, Dict] = None):
        self.rules = rules or VALIDATION_RULES
    
    def validate_numeric(
        self, 
        ticker: str,
        field: str, 
        api_value: Optional[float], 
        ground_truth: Optional[float]
    ) -> ValidationResult:
        """
        Validate a numeric field within tolerance
        
        Args:
            ticker: Stock ticker
            field: Field name
            api_value: Value from API
            ground_truth: Value from ground truth source
            
        Returns:
            ValidationResult object
        """
        rule = self.rules.get(field, {"tolerance_pct": 10.0, "critical": False, "description": field})
        tolerance_pct = rule["tolerance_pct"]
        critical = rule["critical"]
        description = rule["description"]
        
        # Handle None values
        if api_value is None and ground_truth is None:
            return ValidationResult(
                ticker=ticker,
                field=field,
                api_value=None,
                ground_truth=None,
                diff_pct=None,
                tolerance_pct=tolerance_pct,
                passed=True,
                critical=critical,
                description=description,
                message="Both values are None (skipped)"
            )
        
        if api_value is None:
            return ValidationResult(
                ticker=ticker,
                field=field,
                api_value=None,
                ground_truth=ground_truth,
                diff_pct=None,
                tolerance_pct=tolerance_pct,
                passed=False,
                critical=critical,
                description=description,
                message="API value is None"
            )
        
        if ground_truth is None:
            return ValidationResult(
                ticker=ticker,
                field=field,
                api_value=api_value,
                ground_truth=None,
                diff_pct=None,
                tolerance_pct=tolerance_pct,
                passed=True,  # Can't validate without ground truth
                critical=critical,
                description=description,
                message="Ground truth not available (skipped)"
            )
        
        # Calculate percentage difference
        if ground_truth == 0:
            # Avoid division by zero
            if api_value == 0:
                diff_pct = 0.0
            else:
                # If ground truth is 0 but API isn't, it's a significant difference
                diff_pct = 100.0
        else:
            diff_pct = abs((api_value - ground_truth) / ground_truth) * 100
        
        # Check if within tolerance
        passed = diff_pct <= tolerance_pct
        
        if passed:
            message = f"PASS: Diff {diff_pct:.2f}% within tolerance {tolerance_pct}%"
        else:
            message = f"FAIL: Diff {diff_pct:.2f}% exceeds tolerance {tolerance_pct}%"
        
        return ValidationResult(
            ticker=ticker,
            field=field,
            api_value=api_value,
            ground_truth=ground_truth,
            diff_pct=diff_pct,
            tolerance_pct=tolerance_pct,
            passed=passed,
            critical=critical,
            description=description,
            message=message
        )
    
    def validate_all_fields(
        self,
        ticker: str,
        api_data: Dict[str, Any],
        ground_truth: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Validate all fields in API data against ground truth
        
        Args:
            ticker: Stock ticker
            api_data: Data from API
            ground_truth: Ground truth data
            
        Returns:
            List of ValidationResult objects
        """
        results = []
        
        # Get all fields that should be validated
        fields_to_validate = set(api_data.keys()) | set(ground_truth.keys())
        
        for field in fields_to_validate:
            if field in self.rules:
                api_value = api_data.get(field)
                gt_value = ground_truth.get(field)
                
                result = self.validate_numeric(ticker, field, api_value, gt_value)
                results.append(result)
                
                # Log critical failures immediately
                if not result.passed and result.critical:
                    logger.error(
                        f"CRITICAL FAILURE: {ticker} {field} - "
                        f"API: {result.api_value}, Ground Truth: {result.ground_truth}, "
                        f"Diff: {result.diff_pct:.2f}%"
                    )
        
        return results
    
    def get_summary_stats(self, results: List[ValidationResult]) -> Dict[str, Any]:
        """
        Generate summary statistics from validation results
        
        Args:
            results: List of validation results
            
        Returns:
            Dictionary with summary stats
        """
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        critical_failures = sum(1 for r in results if not r.passed and r.critical)
        
        pass_rate = (passed / total * 100) if total > 0 else 0.0
        
        return {
            "total_fields": total,
            "passed": passed,
            "failed": failed,
            "critical_failures": critical_failures,
            "pass_rate": pass_rate,
            "critical_pass": critical_failures == 0
        }


def format_value(value: Optional[float], is_percentage: bool = False, is_currency: bool = False) -> str:
    """Format a numeric value for display"""
    if value is None:
        return "N/A"
    
    if is_percentage:
        return f"{value:.2f}%"
    elif is_currency:
        if value >= 1e9:
            return f"₹{value/1e9:.2f}B"
        elif value >= 1e6:
            return f"₹{value/1e6:.2f}M"
        elif value >= 1e3:
            return f"₹{value/1e3:.2f}K"
        else:
            return f"₹{value:.2f}"
    else:
        return f"{value:.4f}"


def get_status_emoji(result: ValidationResult) -> str:
    """Get emoji for validation result status"""
    if result.passed:
        return "✅"
    elif result.critical:
        return "❌"
    else:
        return "⚠️"


