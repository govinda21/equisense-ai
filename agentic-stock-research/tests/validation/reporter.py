"""
HTML and CSV report generator for validation results
"""

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Template

from tests.validation.validation_rules import ValidationResult, get_status_emoji, format_value


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>API Validation Report - {{ report_date }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        h1 { font-size: 2.5em; margin-bottom: 10px; }
        .subtitle { opacity: 0.9; font-size: 1.1em; }
        
        .summary-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .summary-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .summary-card h3 { font-size: 0.9em; color: #666; margin-bottom: 10px; text-transform: uppercase; }
        .summary-card .value { font-size: 2.5em; font-weight: bold; }
        .summary-card.pass .value { color: #10b981; }
        .summary-card.fail .value { color: #ef4444; }
        .summary-card.warning .value { color: #f59e0b; }
        
        table {
            width: 100%;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        th {
            background: #f8f9fa;
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #495057;
            border-bottom: 2px solid #dee2e6;
        }
        td {
            padding: 12px 15px;
            border-bottom: 1px solid #dee2e6;
        }
        tr:last-child td { border-bottom: none; }
        tr:hover { background: #f8f9fa; }
        
        .status-pass { color: #10b981; font-weight: bold; }
        .status-fail { color: #ef4444; font-weight: bold; }
        .status-warning { color: #f59e0b; font-weight: bold; }
        
        .ticker-group {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .ticker-group h2 {
            margin-bottom: 15px;
            color: #495057;
            font-size: 1.5em;
        }
        
        .badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            font-weight: 600;
        }
        .badge-critical { background: #fee2e2; color: #dc2626; }
        .badge-normal { background: #dbeafe; color: #2563eb; }
        
        footer {
            text-align: center;
            padding: 30px;
            color: #6b7280;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎯 API Validation Report</h1>
            <div class="subtitle">Generated on {{ report_date }}</div>
        </header>
        
        <div class="summary-grid">
            <div class="summary-card pass">
                <h3>Pass Rate</h3>
                <div class="value">{{ summary.pass_rate|round(1) }}%</div>
            </div>
            <div class="summary-card">
                <h3>Total Fields</h3>
                <div class="value">{{ summary.total_fields }}</div>
            </div>
            <div class="summary-card {% if summary.critical_failures > 0 %}fail{% else %}pass{% endif %}">
                <h3>Critical Failures</h3>
                <div class="value">{{ summary.critical_failures }}</div>
            </div>
            <div class="summary-card {% if summary.failed > 0 %}warning{% endif %}">
                <h3>Total Failures</h3>
                <div class="value">{{ summary.failed }}</div>
            </div>
        </div>
        
        {% for ticker, ticker_results in results_by_ticker.items() %}
        <div class="ticker-group">
            <h2>{{ ticker }}</h2>
            <table>
                <thead>
                    <tr>
                        <th>Status</th>
                        <th>Field</th>
                        <th>API Value</th>
                        <th>Ground Truth</th>
                        <th>Difference</th>
                        <th>Tolerance</th>
                        <th>Type</th>
                    </tr>
                </thead>
                <tbody>
                    {% for result in ticker_results %}
                    <tr>
                        <td><span class="status-{% if result.passed %}pass{% elif result.critical %}fail{% else %}warning{% endif %}">
                            {{ result.status_emoji }}
                        </span></td>
                        <td>{{ result.description }}</td>
                        <td>{{ result.api_value_str }}</td>
                        <td>{{ result.ground_truth_str }}</td>
                        <td>{{ result.diff_str }}</td>
                        <td>±{{ result.tolerance_pct }}%</td>
                        <td>
                            {% if result.critical %}
                            <span class="badge badge-critical">CRITICAL</span>
                            {% else %}
                            <span class="badge badge-normal">NORMAL</span>
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endfor %}
        
        <footer>
            <p>EquiSense AI - API Validation Suite v1.0</p>
            <p>Generated by automated testing framework</p>
        </footer>
    </div>
</body>
</html>
"""


class ValidationReporter:
    """Generate HTML and CSV reports from validation results"""
    
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_html_report(self, results: List[ValidationResult], filename: str = None) -> Path:
        """
        Generate HTML report from validation results
        
        Args:
            results: List of validation results
            filename: Optional filename (default: validation_report_{date}.html)
            
        Returns:
            Path to generated report
        """
        if not filename:
            filename = f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        # Group results by ticker
        results_by_ticker = {}
        for result in results:
            if result.ticker not in results_by_ticker:
                results_by_ticker[result.ticker] = []
            results_by_ticker[result.ticker].append(result)
        
        # Calculate summary stats
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed
        critical_failures = sum(1 for r in results if not r.passed and r.critical)
        pass_rate = (passed / total * 100) if total > 0 else 0.0
        
        summary = {
            "total_fields": total,
            "passed": passed,
            "failed": failed,
            "critical_failures": critical_failures,
            "pass_rate": pass_rate
        }
        
        # Prepare template data
        template_data = {
            "report_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "summary": summary,
            "results_by_ticker": {}
        }
        
        # Format results for template
        for ticker, ticker_results in results_by_ticker.items():
            formatted_results = []
            for r in ticker_results:
                formatted_results.append({
                    "passed": r.passed,
                    "critical": r.critical,
                    "status_emoji": get_status_emoji(r),
                    "description": r.description,
                    "api_value_str": format_value(r.api_value) if r.api_value is not None else "N/A",
                    "ground_truth_str": format_value(r.ground_truth) if r.ground_truth is not None else "N/A",
                    "diff_str": f"{r.diff_pct:.2f}%" if r.diff_pct is not None else "N/A",
                    "tolerance_pct": r.tolerance_pct
                })
            template_data["results_by_ticker"][ticker] = formatted_results
        
        # Render template
        template = Template(HTML_TEMPLATE)
        html_content = template.render(**template_data)
        
        # Save report
        report_path = self.output_dir / filename
        with open(report_path, "w") as f:
            f.write(html_content)
        
        print(f"✅ HTML report generated: {report_path}")
        return report_path
    
    def generate_csv_report(self, results: List[ValidationResult], filename: str = None) -> Path:
        """
        Generate CSV report from validation results
        
        Args:
            results: List of validation results
            filename: Optional filename (default: validation_results_{date}.csv)
            
        Returns:
            Path to generated CSV
        """
        if not filename:
            filename = f"validation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        csv_path = self.output_dir / filename
        
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            
            # Header
            writer.writerow([
                "Timestamp",
                "Ticker",
                "Field",
                "Description",
                "API Value",
                "Ground Truth",
                "Difference %",
                "Tolerance %",
                "Status",
                "Critical",
                "Message"
            ])
            
            # Data rows
            timestamp = datetime.now().isoformat()
            for r in results:
                writer.writerow([
                    timestamp,
                    r.ticker,
                    r.field,
                    r.description,
                    r.api_value if r.api_value is not None else "",
                    r.ground_truth if r.ground_truth is not None else "",
                    f"{r.diff_pct:.2f}" if r.diff_pct is not None else "",
                    r.tolerance_pct,
                    "PASS" if r.passed else "FAIL",
                    "YES" if r.critical else "NO",
                    r.message
                ])
        
        print(f"✅ CSV report generated: {csv_path}")
        return csv_path
    
    def generate_json_report(self, results: List[ValidationResult], filename: str = None) -> Path:
        """
        Generate JSON report from validation results
        
        Args:
            results: List of validation results
            filename: Optional filename
            
        Returns:
            Path to generated JSON
        """
        if not filename:
            filename = f"validation_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        json_path = self.output_dir / filename
        
        # Convert results to dictionaries
        results_data = []
        for r in results:
            results_data.append({
                "ticker": r.ticker,
                "field": r.field,
                "description": r.description,
                "api_value": r.api_value,
                "ground_truth": r.ground_truth,
                "diff_pct": r.diff_pct,
                "tolerance_pct": r.tolerance_pct,
                "passed": r.passed,
                "critical": r.critical,
                "message": r.message
            })
        
        report_data = {
            "timestamp": datetime.now().isoformat(),
            "total_validations": len(results),
            "passed": sum(1 for r in results if r.passed),
            "failed": sum(1 for r in results if not r.passed),
            "critical_failures": sum(1 for r in results if not r.passed and r.critical),
            "results": results_data
        }
        
        with open(json_path, "w") as f:
            json.dump(report_data, f, indent=2)
        
        print(f"✅ JSON report generated: {json_path}")
        return json_path


