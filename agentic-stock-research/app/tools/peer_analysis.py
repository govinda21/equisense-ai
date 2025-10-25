from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
import asyncio
import yfinance as yf
import pandas as pd
import numpy as np
from dataclasses import dataclass

from app.tools.finance import fetch_info
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValuationMetrics:
    """Structured valuation metrics for peer comparison"""
    ticker: str
    market_cap: Optional[float] = None
    enterprise_value: Optional[float] = None
    trailing_pe: Optional[float] = None
    forward_pe: Optional[float] = None
    price_to_book: Optional[float] = None
    price_to_sales: Optional[float] = None
    ev_to_ebitda: Optional[float] = None
    ev_to_revenue: Optional[float] = None
    ev_to_ebit: Optional[float] = None
    peg_ratio: Optional[float] = None
    price_to_cash_flow: Optional[float] = None
    dividend_yield: Optional[float] = None
    beta: Optional[float] = None


@dataclass
class PeerComparison:
    """Structured peer comparison results"""
    metric: str
    target_value: Optional[float]
    peer_average: Optional[float]
    peer_median: Optional[float]
    peer_min: Optional[float]
    peer_max: Optional[float]
    percentile_rank: Optional[int]
    z_score: Optional[float]
    relative_position: str  # "Cheap", "Fair", "Expensive", "N/A"


async def analyze_peers(ticker: str) -> Dict[str, Any]:
    """
    Analyze direct and indirect competitors for the given ticker.
    Compare valuation metrics, growth rates, margins, and market positioning.
    """
    
    def _safe_float(x: Any) -> Optional[float]:
        try:
            if x is None:
                return None
            f = float(x)
            if f != f:  # Check for NaN
                return None
            return f
        except Exception:
            return None

    async def _fetch_peer_data() -> Dict[str, Any]:
        try:
            # Get company info to identify sector/industry using rate-limited client
            from app.tools.finance import fetch_info
            company_info = await fetch_info(ticker)
            sector = company_info.get("sector", "Unknown")
            industry = company_info.get("industry", "Unknown")
            market_cap = _safe_float(company_info.get("marketCap"))
            
            # Define peer mappings based on common sectors/industries
            peer_mappings = {
                # Technology
                "AAPL": ["MSFT", "GOOGL", "AMZN", "META", "NVDA"],
                "MSFT": ["AAPL", "GOOGL", "AMZN", "META", "ORCL"],
                "GOOGL": ["AAPL", "MSFT", "AMZN", "META", "NFLX"],
                "AMZN": ["AAPL", "MSFT", "GOOGL", "META", "WMT"],
                "META": ["AAPL", "MSFT", "GOOGL", "SNAP", "TWTR"],
                "NVDA": ["AMD", "INTC", "QCOM", "AAPL", "MSFT"],
                "TSLA": ["GM", "F", "NIO", "RIVN", "LCID"],
                
                # Financial Services
                "JPM": ["BAC", "WFC", "C", "GS", "MS"],
                "BAC": ["JPM", "WFC", "C", "USB", "PNC"],
                "WFC": ["JPM", "BAC", "C", "USB", "PNC"],
                
                # Healthcare
                "JNJ": ["PFE", "MRK", "ABT", "TMO", "UNH"],
                "PFE": ["JNJ", "MRK", "ABT", "BMY", "LLY"],
                
                # Consumer
                "KO": ["PEP", "MNST", "DPS", "KDP", "CCEP"],
                "PEP": ["KO", "MNST", "DPS", "KDP", "CCEP"],
                "WMT": ["TGT", "COST", "AMZN", "HD", "LOW"],
                
                # Indian stocks
                "RELIANCE.NS": ["TCS.NS", "INFY.NS", "HDFCBANK.NS", "ICICIBANK.NS"],
                "TCS.NS": ["INFY.NS", "WIPRO.NS", "HCLTECH.NS", "TECHM.NS"],
                "HDFCBANK.NS": ["ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS", "KOTAKBANK.NS"],
                "BAJFINANCE.NS": ["HDFCBANK.NS", "ICICIBANK.NS", "SBIN.NS", "AXISBANK.NS"],
                "JIOFIN.NS": ["HDFCBANK.NS", "ICICIBANK.NS", "BAJFINANCE.NS", "AXISBANK.NS"],
            }
            
            # Get peers from mapping or try to identify by sector
            peers = peer_mappings.get(ticker.upper(), [])
            
            # If no predefined peers, try to find similar companies by market cap range
            if not peers and market_cap:
                # This is a simplified approach - in production, you'd use more sophisticated peer identification
                if "Technology" in sector:
                    peers = ["AAPL", "MSFT", "GOOGL", "META", "NVDA"][:3]
                elif "Financial" in sector:
                    peers = ["JPM", "BAC", "WFC", "C", "GS"][:3]
                elif "Healthcare" in sector:
                    peers = ["JNJ", "PFE", "MRK", "ABT", "UNH"][:3]
                elif "Consumer" in sector:
                    peers = ["KO", "PEP", "WMT", "TGT", "COST"][:3]
                else:
                    peers = ["SPY"]  # Fallback to market benchmark
            
            # Remove the target ticker from peers if present
            peers = [p for p in peers if p.upper() != ticker.upper()][:5]  # Limit to 5 peers
            
            if not peers:
                return {
                    "sector": sector,
                    "industry": industry,
                    "peers_identified": [],
                    "comparison_metrics": {},
                    "relative_position": "Unable to identify comparable peers",
                    "summary": "Insufficient peer data available for comparison"
                }
            
            # Fetch peer data
            peer_data = {}
            target_metrics = _extract_metrics(company_info)
            
            for peer in peers:
                try:
                    peer_info = await fetch_info(peer)
                    peer_metrics = _extract_metrics(peer_info)
                    if peer_metrics:
                        peer_data[peer] = peer_metrics
                except Exception:
                    continue
            
            if not peer_data:
                return {
                    "sector": sector,
                    "industry": industry,
                    "peers_identified": peers,
                    "comparison_metrics": {},
                    "relative_position": "Unable to fetch peer data",
                    "summary": "Peer data retrieval failed"
                }
            
            # Perform enhanced comparison analysis
            comparison = _compare_with_peers(target_metrics, peer_data, ticker)
            
            return {
                "sector": sector,
                "industry": industry,
                "peers_identified": list(peer_data.keys()),
                "target_metrics": target_metrics.__dict__,
                "peer_metrics": {k: v.__dict__ for k, v in peer_data.items()},
                "valuation_metrics": comparison["valuation_metrics"],
                "valuation_score": comparison["valuation_score"],
                "relative_position": comparison["relative_position"],
                "strengths": comparison["strengths"],
                "weaknesses": comparison["weaknesses"],
                "valuation_summary": comparison["valuation_summary"],
                "summary": comparison["summary"],
                "peer_count": comparison["peer_count"]
            }
            
        except Exception as e:
            return {
                "sector": "Unknown",
                "industry": "Unknown", 
                "peers_identified": [],
                "comparison_metrics": {},
                "relative_position": f"Analysis failed: {str(e)}",
                "summary": "Peer analysis could not be completed"
            }
    
    def _extract_metrics(info: Dict[str, Any]) -> ValuationMetrics:
        """Extract comprehensive valuation metrics from company info"""
        return ValuationMetrics(
            ticker=info.get("symbol", ""),
            market_cap=_safe_float(info.get("marketCap")),
            enterprise_value=_safe_float(info.get("enterpriseValue")),
            trailing_pe=_safe_float(info.get("trailingPE")),
            forward_pe=_safe_float(info.get("forwardPE")),
            price_to_book=_safe_float(info.get("priceToBook")),
            price_to_sales=_safe_float(info.get("priceToSalesTrailing12Months")),
            ev_to_ebitda=_safe_float(info.get("enterpriseToEbitda")),
            ev_to_revenue=_safe_float(info.get("enterpriseToRevenue")),
            ev_to_ebit=_safe_float(info.get("enterpriseToEbit")),
            peg_ratio=_safe_float(info.get("pegRatio")),
            price_to_cash_flow=_safe_float(info.get("priceToCashflowTrailing12Months")),
            dividend_yield=_safe_float(info.get("dividendYield")),
            beta=_safe_float(info.get("beta"))
        )
    
    def _compare_with_peers(target: ValuationMetrics, 
                           peers: Dict[str, ValuationMetrics], 
                           ticker: str) -> Dict[str, Any]:
        """Enhanced peer comparison with comprehensive relative valuation analysis"""
        
        # Define key valuation metrics for comparison
        valuation_metrics = [
            'trailing_pe', 'forward_pe', 'price_to_book', 'price_to_sales',
            'ev_to_ebitda', 'ev_to_revenue', 'ev_to_ebit', 'peg_ratio',
            'price_to_cash_flow', 'dividend_yield', 'beta'
        ]
        
        comparison_results = {}
        strengths = []
        weaknesses = []
        valuation_summary = []
        
        for metric in valuation_metrics:
            target_val = getattr(target, metric)
            peer_values = [getattr(peer, metric) for peer in peers.values() 
                          if getattr(peer, metric) is not None]
            
            if target_val is not None and peer_values:
                peer_values.append(target_val)
                peer_values.sort()
                
                # Calculate statistics
                peer_avg = np.mean(peer_values[:-1])  # Exclude target from average
                peer_median = np.median(peer_values[:-1])
                peer_min = min(peer_values[:-1])
                peer_max = max(peer_values[:-1])
                peer_std = np.std(peer_values[:-1]) if len(peer_values) > 2 else 0
                
                # Calculate percentile rank
                percentile = _calculate_percentile(target_val, peer_values[:-1])
                
                # Calculate Z-score
                z_score = (target_val - peer_avg) / peer_std if peer_std > 0 else 0
                
                # Determine relative position
                relative_position = _determine_relative_position(
                    metric, target_val, peer_avg, percentile
                )
                
                comparison_results[metric] = PeerComparison(
                    metric=metric,
                    target_value=target_val,
                    peer_average=peer_avg,
                    peer_median=peer_median,
                    peer_min=peer_min,
                    peer_max=peer_max,
                    percentile_rank=percentile,
                    z_score=z_score,
                    relative_position=relative_position
                )
                
                # Generate insights
                _generate_valuation_insights(
                    metric, target_val, peer_avg, percentile, 
                    strengths, weaknesses, valuation_summary
                )
        
        # Calculate overall valuation score
        valuation_score = _calculate_valuation_score(comparison_results)
        
        # Determine overall relative position
        position = _determine_overall_position(valuation_score, len(strengths), len(weaknesses))
        
        # Generate comprehensive summary
        summary = _generate_comprehensive_summary(
            ticker, peers, comparison_results, strengths, weaknesses, valuation_score
        )
        
        return {
            "valuation_metrics": {k: v.__dict__ for k, v in comparison_results.items()},
            "valuation_score": valuation_score,
            "relative_position": position,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "valuation_summary": valuation_summary,
            "summary": summary,
            "peer_count": len(peers)
        }
    
    def _determine_relative_position(metric: str, target_val: float, peer_avg: float, percentile: int) -> str:
        """Determine if target is cheap, fair, or expensive relative to peers"""
        
        # For valuation metrics, lower is generally better (cheaper)
        cheap_metrics = ['trailing_pe', 'forward_pe', 'price_to_book', 'price_to_sales', 
                        'ev_to_ebitda', 'ev_to_revenue', 'ev_to_ebit', 'peg_ratio', 'price_to_cash_flow']
        
        # For yield metrics, higher is generally better
        yield_metrics = ['dividend_yield']
        
        if metric in cheap_metrics:
            if percentile <= 25:
                return "Cheap"
            elif percentile <= 75:
                return "Fair"
            else:
                return "Expensive"
        elif metric in yield_metrics:
            if percentile >= 75:
                return "Cheap"
            elif percentile >= 25:
                return "Fair"
            else:
                return "Expensive"
        else:  # Beta - neutral interpretation
            if percentile <= 25:
                return "Low Risk"
            elif percentile <= 75:
                return "Moderate Risk"
            else:
                return "High Risk"
    
    def _generate_valuation_insights(metric: str, target_val: float, peer_avg: float, 
                                   percentile: int, strengths: List[str], 
                                   weaknesses: List[str], valuation_summary: List[str]):
        """Generate insights for each valuation metric"""
        
        metric_names = {
            'trailing_pe': 'Trailing P/E',
            'forward_pe': 'Forward P/E',
            'price_to_book': 'Price-to-Book',
            'price_to_sales': 'Price-to-Sales',
            'ev_to_ebitda': 'EV/EBITDA',
            'ev_to_revenue': 'EV/Revenue',
            'ev_to_ebit': 'EV/EBIT',
            'peg_ratio': 'PEG Ratio',
            'price_to_cash_flow': 'Price-to-Cash Flow',
            'dividend_yield': 'Dividend Yield',
            'beta': 'Beta'
        }
        
        metric_name = metric_names.get(metric, metric.replace('_', ' ').title())
        
        # Generate insights based on percentile
        if percentile <= 25:
            if metric in ['trailing_pe', 'forward_pe', 'price_to_book', 'price_to_sales', 
                         'ev_to_ebitda', 'ev_to_revenue', 'ev_to_ebit', 'peg_ratio', 'price_to_cash_flow']:
                strengths.append(f"Attractive {metric_name} valuation ({percentile}th percentile)")
                valuation_summary.append(f"{metric_name}: Undervalued vs peers")
            elif metric == 'dividend_yield':
                strengths.append(f"High {metric_name} ({percentile}th percentile)")
                valuation_summary.append(f"{metric_name}: Above-average yield")
            elif metric == 'beta':
                strengths.append(f"Low volatility ({percentile}th percentile)")
                valuation_summary.append(f"{metric_name}: Defensive profile")
        elif percentile >= 75:
            if metric in ['trailing_pe', 'forward_pe', 'price_to_book', 'price_to_sales', 
                         'ev_to_ebitda', 'ev_to_revenue', 'ev_to_ebit', 'peg_ratio', 'price_to_cash_flow']:
                weaknesses.append(f"Premium {metric_name} valuation ({percentile}th percentile)")
                valuation_summary.append(f"{metric_name}: Overvalued vs peers")
            elif metric == 'dividend_yield':
                weaknesses.append(f"Low {metric_name} ({percentile}th percentile)")
                valuation_summary.append(f"{metric_name}: Below-average yield")
            elif metric == 'beta':
                weaknesses.append(f"High volatility ({percentile}th percentile)")
                valuation_summary.append(f"{metric_name}: Aggressive profile")
        else:
            valuation_summary.append(f"{metric_name}: In-line with peers")
    
    def _calculate_valuation_score(comparison_results: Dict[str, PeerComparison]) -> float:
        """Calculate overall valuation score (0-100, higher = more attractive)"""
        
        if not comparison_results:
            return 50.0
        
        scores = []
        weights = {
            'trailing_pe': 0.15,
            'forward_pe': 0.15,
            'price_to_book': 0.10,
            'price_to_sales': 0.10,
            'ev_to_ebitda': 0.15,
            'ev_to_revenue': 0.10,
            'peg_ratio': 0.10,
            'price_to_cash_flow': 0.10,
            'dividend_yield': 0.05
        }
        
        for metric, comparison in comparison_results.items():
            if comparison.percentile_rank is not None:
                weight = weights.get(metric, 0.05)
                
                # For valuation metrics, lower percentile = higher score
                if metric in ['trailing_pe', 'forward_pe', 'price_to_book', 'price_to_sales', 
                             'ev_to_ebitda', 'ev_to_revenue', 'ev_to_ebit', 'peg_ratio', 'price_to_cash_flow']:
                    score = (100 - comparison.percentile_rank) * weight
                # For yield metrics, higher percentile = higher score
                elif metric == 'dividend_yield':
                    score = comparison.percentile_rank * weight
                else:
                    # Neutral scoring for other metrics
                    score = 50 * weight
                
                scores.append(score)
        
        return sum(scores) if scores else 50.0
    
    def _determine_overall_position(valuation_score: float, strength_count: int, weakness_count: int) -> str:
        """Determine overall relative position based on valuation score and strength/weakness count"""
        
        if valuation_score >= 70:
            return "Significantly Undervalued"
        elif valuation_score >= 60:
            return "Moderately Undervalued"
        elif valuation_score >= 40:
            return "Fairly Valued"
        elif valuation_score >= 30:
            return "Moderately Overvalued"
        else:
            return "Significantly Overvalued"
    
    def _generate_comprehensive_summary(ticker: str, peers: Dict[str, ValuationMetrics], 
                                       comparison_results: Dict[str, PeerComparison],
                                       strengths: List[str], weaknesses: List[str], 
                                       valuation_score: float) -> str:
        """Generate comprehensive peer comparison summary"""
        
        peer_names = list(peers.keys())
        peer_count = len(peer_names)
        
        # Determine valuation attractiveness
        if valuation_score >= 60:
            attractiveness = "attractive"
        elif valuation_score >= 40:
            attractiveness = "fair"
        else:
            attractiveness = "expensive"
        
        summary = f"{ticker} shows {attractiveness} valuation relative to {peer_count} peers "
        summary += f"({', '.join(peer_names[:3])}{'...' if peer_count > 3 else ''}). "
        
        # Add key insights
        if strengths:
            summary += f"Key strengths: {', '.join(strengths[:3])}. "
        if weaknesses:
            summary += f"Areas of concern: {', '.join(weaknesses[:3])}. "
        
        # Add percentile insights
        cheap_metrics = [m for m, c in comparison_results.items() 
                        if c.percentile_rank is not None and c.percentile_rank <= 25]
        expensive_metrics = [m for m, c in comparison_results.items() 
                           if c.percentile_rank is not None and c.percentile_rank >= 75]
        
        if cheap_metrics:
            summary += f"Trading at discount on: {', '.join(cheap_metrics[:2])}. "
        if expensive_metrics:
            summary += f"Trading at premium on: {', '.join(expensive_metrics[:2])}."
        
        return summary

    def _calculate_percentile(value: float, peer_values: List[float]) -> int:
        """Calculate percentile rank of value among peers"""
        if not peer_values or value is None:
            return 50  # Default to median if no data
        
        # Add target value to the list for ranking
        all_values = peer_values + [value]
        all_values.sort()
        
        # Find rank of target value
        rank = all_values.index(value)
        percentile = int((rank / (len(all_values) - 1)) * 100)
        
        return percentile

    return await _fetch_peer_data()
