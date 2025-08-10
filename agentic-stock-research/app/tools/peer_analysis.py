from __future__ import annotations

from typing import Any, Dict, List, Optional
import asyncio
import yfinance as yf
import pandas as pd

from app.tools.finance import fetch_info


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

    def _fetch_peer_data() -> Dict[str, Any]:
        try:
            # Get company info to identify sector/industry
            company_info = yf.Ticker(ticker).info or {}
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
                    peer_info = yf.Ticker(peer).info or {}
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
            
            # Perform comparison analysis
            comparison = _compare_with_peers(target_metrics, peer_data, ticker)
            
            return {
                "sector": sector,
                "industry": industry,
                "peers_identified": list(peer_data.keys()),
                "target_metrics": target_metrics,
                "peer_metrics": peer_data,
                "comparison_metrics": comparison["metrics"],
                "relative_position": comparison["position"],
                "strengths": comparison["strengths"],
                "weaknesses": comparison["weaknesses"],
                "summary": comparison["summary"]
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
    
    def _extract_metrics(info: Dict[str, Any]) -> Dict[str, Optional[float]]:
        """Extract key financial metrics from company info"""
        return {
            "marketCap": _safe_float(info.get("marketCap")),
            "enterpriseValue": _safe_float(info.get("enterpriseValue")),
            "trailingPE": _safe_float(info.get("trailingPE")),
            "forwardPE": _safe_float(info.get("forwardPE")),
            "priceToBook": _safe_float(info.get("priceToBook")),
            "evToEbitda": _safe_float(info.get("enterpriseToEbitda")),
            "evToRevenue": _safe_float(info.get("enterpriseToRevenue")),
            "profitMargins": _safe_float(info.get("profitMargins")),
            "operatingMargins": _safe_float(info.get("operatingMargins")),
            "grossMargins": _safe_float(info.get("grossMargins")),
            "returnOnEquity": _safe_float(info.get("returnOnEquity")),
            "returnOnAssets": _safe_float(info.get("returnOnAssets")),
            "revenueGrowth": _safe_float(info.get("revenueGrowth")),
            "earningsGrowth": _safe_float(info.get("earningsGrowth")),
            "debtToEquity": _safe_float(info.get("debtToEquity")),
            "currentRatio": _safe_float(info.get("currentRatio")),
            "beta": _safe_float(info.get("beta")),
            "dividendYield": _safe_float(info.get("dividendYield")),
        }
    
    def _compare_with_peers(target: Dict[str, Optional[float]], 
                           peers: Dict[str, Dict[str, Optional[float]]], 
                           ticker: str) -> Dict[str, Any]:
        """Compare target company metrics with peer averages"""
        
        # Calculate peer averages for each metric
        peer_averages = {}
        for metric in target.keys():
            values = [peer.get(metric) for peer in peers.values() if peer.get(metric) is not None]
            if values:
                peer_averages[metric] = sum(values) / len(values)
            else:
                peer_averages[metric] = None
        
        # Compare target vs peer averages
        comparison_metrics = {}
        strengths = []
        weaknesses = []
        
        for metric, target_val in target.items():
            peer_avg = peer_averages.get(metric)
            if target_val is not None and peer_avg is not None:
                ratio = target_val / peer_avg if peer_avg != 0 else None
                comparison_metrics[metric] = {
                    "target": target_val,
                    "peer_average": peer_avg,
                    "ratio_to_peers": ratio,
                    "percentile": _calculate_percentile(target_val, [p.get(metric) for p in peers.values()])
                }
                
                # Identify strengths and weaknesses
                if ratio:
                    if metric in ["returnOnEquity", "returnOnAssets", "profitMargins", "operatingMargins", "grossMargins", "revenueGrowth", "earningsGrowth", "currentRatio"]:
                        if ratio > 1.1:  # 10% better than peers
                            strengths.append(f"Superior {metric.replace('_', ' ')}")
                        elif ratio < 0.9:  # 10% worse than peers
                            weaknesses.append(f"Below-average {metric.replace('_', ' ')}")
                    elif metric in ["trailingPE", "forwardPE", "priceToBook", "evToEbitda", "evToRevenue", "debtToEquity", "beta"]:
                        if ratio < 0.9:  # Lower is generally better for valuation metrics
                            strengths.append(f"Attractive {metric.replace('_', ' ')} valuation")
                        elif ratio > 1.1:
                            weaknesses.append(f"Premium {metric.replace('_', ' ')} valuation")
        
        # Determine overall relative position
        if len(strengths) > len(weaknesses):
            position = "Above-average performer relative to peers"
        elif len(weaknesses) > len(strengths):
            position = "Below-average performer relative to peers"
        else:
            position = "In-line with peer group performance"
        
        # Generate summary
        peer_names = list(peers.keys())
        summary = f"{ticker} compared to {len(peer_names)} peers ({', '.join(peer_names[:3])}{'...' if len(peer_names) > 3 else ''}). "
        summary += f"Key strengths: {', '.join(strengths[:3]) if strengths else 'None identified'}. "
        summary += f"Areas for improvement: {', '.join(weaknesses[:3]) if weaknesses else 'None identified'}."
        
        return {
            "metrics": comparison_metrics,
            "position": position,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "summary": summary
        }
    
    def _calculate_percentile(value: float, peer_values: List[Optional[float]]) -> Optional[int]:
        """Calculate percentile rank of value among peers"""
        valid_values = [v for v in peer_values if v is not None]
        if not valid_values or value is None:
            return None
        
        valid_values.append(value)
        valid_values.sort()
        rank = valid_values.index(value)
        percentile = int((rank / (len(valid_values) - 1)) * 100)
        return percentile

    return await asyncio.to_thread(_fetch_peer_data)
