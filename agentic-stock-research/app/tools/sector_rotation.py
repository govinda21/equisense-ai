from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import yfinance as yf

from app.logging import get_logger

logger = get_logger()


class SectorRotationAnalyzer:
    """Analyzes sector rotation patterns and momentum"""
    
    def __init__(self):
        self.sector_etfs = {
            # US Sectors
            "XLK": "Technology",
            "XLF": "Financials", 
            "XLV": "Healthcare",
            "XLE": "Energy",
            "XLI": "Industrials",
            "XLY": "Consumer Discretionary",
            "XLP": "Consumer Staples",
            "XLU": "Utilities",
            "XLB": "Materials",
            "XLRE": "Real Estate",
            "XLC": "Communication Services",
            
            # Indian Sectors (Nifty sector indices) - Using correct Yahoo Finance symbols
            "^CNXIT": "IT",
            "^CNXFMCG": "FMCG", 
            "^CNXPHARMA": "Pharma",
            "^CNXAUTO": "Auto",
            "^NSEBANK": "Banking",
            "^CNXENERGY": "Energy",
            "^CNXMETAL": "Metals",
            "^CNXREALTY": "Real Estate",
            # Note: NIFTYPSU, NIFTYMEDIA, NIFTYPVT, NIFTYPSUBANK don't have valid Yahoo Finance symbols
            # Using available indices only
        }
    
    async def analyze_sector_rotation(self, ticker: str, days_back: int = 90) -> Dict[str, Any]:
        """
        Analyze sector rotation patterns for a given ticker
        
        Args:
            ticker: Stock ticker symbol
            days_back: Number of days to analyze
            
        Returns:
            Dictionary containing sector rotation analysis
        """
        try:
            logger.info(f"Starting sector rotation analysis for {ticker}")
            
            # Determine market (US vs India)
            market = self._determine_market(ticker)
            relevant_etfs = self._get_relevant_etfs(market)
            
            # Get sector performance data
            sector_performance = await self._get_sector_performance(relevant_etfs, days_back)
            
            # Analyze rotation patterns
            rotation_analysis = self._analyze_rotation_patterns(sector_performance)
            
            # Get individual stock sector
            stock_sector = await self._get_stock_sector(ticker)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                ticker, stock_sector, sector_performance, rotation_analysis
            )
            
            result = {
                "ticker": ticker,
                "market": market,
                "stock_sector": stock_sector,
                "analysis_period_days": days_back,
                "sector_performance": sector_performance,
                "rotation_patterns": rotation_analysis,
                "recommendations": recommendations,
                "timestamp": datetime.now().isoformat(),
                "status": "success",
                
                # UI-compatible fields
                "overall_score": self._calculate_overall_score(sector_performance, rotation_analysis),
                "recommendation": recommendations["rotation_signal"],
                "sector_performance": {
                    "current_phase": rotation_analysis["rotation_phase"],
                    "momentum_score": self._calculate_momentum_score(sector_performance)
                },
                "rotation_signals": self._generate_rotation_signals(sector_performance, rotation_analysis),
                "key_insights": recommendations["key_insights"]
            }
            
            logger.info(f"Sector rotation analysis completed for {ticker}")
            return result
            
        except Exception as e:
            logger.error(f"Error in sector rotation analysis for {ticker}: {e}")
            return {
                "ticker": ticker,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _determine_market(self, ticker: str) -> str:
        """Determine if ticker is US or Indian market"""
        ticker_upper = ticker.upper()
        if ticker_upper.endswith(('.NS', '.BO')):
            return "India"
        return "US"
    
    def _get_relevant_etfs(self, market: str) -> Dict[str, str]:
        """Get relevant sector ETFs based on market"""
        if market == "India":
            return {k: v for k, v in self.sector_etfs.items() if k.startswith('^')}
        else:
            return {k: v for k, v in self.sector_etfs.items() if not k.startswith('^')}
    
    async def _get_sector_performance(self, etfs: Dict[str, str], days_back: int) -> Dict[str, Any]:
        """Get sector performance data"""
        def _fetch_data():
            sector_data = {}
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)
            
            for etf, sector_name in etfs.items():
                try:
                    ticker_obj = yf.Ticker(etf)
                    hist = ticker_obj.history(start=start_date, end=end_date)
                    
                    if len(hist) > 0:
                        # Calculate returns
                        start_price = hist['Close'].iloc[0]
                        end_price = hist['Close'].iloc[-1]
                        total_return = (end_price - start_price) / start_price
                        
                        # Calculate volatility
                        daily_returns = hist['Close'].pct_change().dropna()
                        volatility = daily_returns.std() * (252 ** 0.5)  # Annualized
                        
                        # Calculate momentum (20-day vs 50-day)
                        if len(hist) >= 50:
                            sma_20 = hist['Close'].rolling(20).mean().iloc[-1]
                            sma_50 = hist['Close'].rolling(50).mean().iloc[-1]
                            momentum = (sma_20 - sma_50) / sma_50
                        else:
                            momentum = 0
                        
                        sector_data[sector_name] = {
                            "etf": etf,
                            "total_return": total_return,
                            "volatility": volatility,
                            "momentum": momentum,
                            "current_price": end_price,
                            "data_points": len(hist)
                        }
                        
                except Exception as e:
                    logger.warning(f"Failed to fetch data for {etf}: {e}")
                    continue
            
            return sector_data
        
        return await asyncio.to_thread(_fetch_data)
    
    def _analyze_rotation_patterns(self, sector_performance: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze sector rotation patterns"""
        if not sector_performance:
            return {"error": "No sector data available"}
        
        # Sort sectors by performance
        sorted_by_return = sorted(
            sector_performance.items(), 
            key=lambda x: x[1]["total_return"], 
            reverse=True
        )
        
        sorted_by_momentum = sorted(
            sector_performance.items(),
            key=lambda x: x[1]["momentum"],
            reverse=True
        )
        
        # Identify rotation phases
        top_performers = [sector for sector, _ in sorted_by_return[:3]]
        bottom_performers = [sector for sector, _ in sorted_by_return[-3:]]
        
        top_momentum = [sector for sector, _ in sorted_by_momentum[:3]]
        bottom_momentum = [sector for sector, _ in sorted_by_momentum[-3:]]
        
        # Calculate market breadth
        positive_sectors = sum(1 for data in sector_performance.values() if data["total_return"] > 0)
        total_sectors = len(sector_performance)
        market_breadth = positive_sectors / total_sectors if total_sectors > 0 else 0
        
        # Determine rotation phase
        rotation_phase = self._determine_rotation_phase(
            top_performers, top_momentum, market_breadth
        )
        
        return {
            "rotation_phase": rotation_phase,
            "market_breadth": market_breadth,
            "top_performers": top_performers,
            "bottom_performers": bottom_performers,
            "top_momentum": top_momentum,
            "bottom_momentum": bottom_momentum,
            "sector_count": total_sectors,
            "positive_sectors": positive_sectors,
            "correlation_analysis": self._analyze_sector_correlations(sector_performance)
        }
    
    def _determine_rotation_phase(self, top_performers: List[str], top_momentum: List[str], market_breadth: float) -> str:
        """Determine the current rotation phase"""
        # Check for defensive rotation
        defensive_sectors = ["Utilities", "Consumer Staples", "Healthcare", "Real Estate"]
        cyclical_sectors = ["Technology", "Financials", "Industrials", "Materials", "Energy"]
        
        top_performers_defensive = sum(1 for sector in top_performers if sector in defensive_sectors)
        top_momentum_defensive = sum(1 for sector in top_momentum if sector in defensive_sectors)
        
        if market_breadth < 0.3:
            return "Risk-Off (Defensive Rotation)"
        elif market_breadth > 0.7 and top_performers_defensive < 2:
            return "Risk-On (Cyclical Rotation)"
        elif top_momentum_defensive >= 2:
            return "Defensive Rotation"
        elif market_breadth > 0.5:
            return "Mixed Rotation"
        else:
            return "Uncertain Rotation"
    
    async def _get_stock_sector(self, ticker: str) -> Dict[str, Any]:
        """Get the sector information for the stock"""
        def _fetch():
            try:
                ticker_obj = yf.Ticker(ticker)
                info = ticker_obj.info
                
                return {
                    "sector": info.get("sector", "Unknown"),
                    "industry": info.get("industry", "Unknown"),
                    "market_cap": info.get("marketCap", 0),
                    "sector_weight": info.get("sectorWeight", 0)
                }
            except Exception as e:
                logger.warning(f"Failed to get sector info for {ticker}: {e}")
                return {"sector": "Unknown", "industry": "Unknown"}
        
        return await asyncio.to_thread(_fetch)
    
    def _generate_recommendations(self, ticker: str, stock_sector: Dict[str, Any], 
                                sector_performance: Dict[str, Any], 
                                rotation_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate sector rotation recommendations"""
        stock_sector_name = stock_sector.get("sector", "Unknown")
        
        # Check if stock's sector is performing well
        sector_data = sector_performance.get(stock_sector_name, {})
        sector_return = sector_data.get("total_return", 0)
        sector_momentum = sector_data.get("momentum", 0)
        
        # Generate recommendations
        recommendations = {
            "sector_outlook": "Neutral",
            "rotation_signal": "Hold",
            "key_insights": [],
            "action_items": []
        }
        
        # Sector performance analysis
        if sector_return > 0.05:  # 5%+ return
            recommendations["sector_outlook"] = "Positive"
            recommendations["key_insights"].append(f"{stock_sector_name} sector outperforming with {sector_return*100:.1f}% return")
        elif sector_return < -0.05:  # -5%+ return
            recommendations["sector_outlook"] = "Negative"
            recommendations["key_insights"].append(f"{stock_sector_name} sector underperforming with {sector_return*100:.1f}% return")
        else:
            recommendations["key_insights"].append(f"{stock_sector_name} sector showing neutral performance ({sector_return*100:+.1f}%)")
        
        # Momentum analysis
        if sector_momentum > 0.02:  # 2%+ momentum
            recommendations["rotation_signal"] = "Buy"
            recommendations["key_insights"].append(f"{stock_sector_name} showing strong momentum ({sector_momentum*100:+.1f}%)")
        elif sector_momentum < -0.02:  # -2%+ momentum
            recommendations["rotation_signal"] = "Sell"
            recommendations["key_insights"].append(f"{stock_sector_name} showing negative momentum ({sector_momentum*100:+.1f}%)")
        else:
            recommendations["key_insights"].append(f"{stock_sector_name} momentum neutral ({sector_momentum*100:+.1f}%)")
        
        # Rotation phase recommendations with sector-specific guidance
        rotation_phase = rotation_analysis.get("rotation_phase", "Uncertain Rotation")
        if "Risk-Off" in rotation_phase:
            recommendations["action_items"].append("Consider defensive positioning in Utilities, Consumer Staples")
            recommendations["action_items"].append("Reduce exposure to cyclical sectors (Energy, Materials)")
            recommendations["action_items"].append("Monitor for sector rotation opportunities")
        elif "Risk-On" in rotation_phase:
            recommendations["action_items"].append("Consider cyclical exposure in Energy, Materials, Industrials")
            recommendations["action_items"].append("Monitor Technology and Consumer Discretionary for momentum continuation")
            recommendations["action_items"].append("Watch for rotation into growth sectors")
        elif "Mixed" in rotation_phase:
            recommendations["action_items"].append("Focus on sector-specific opportunities")
            recommendations["action_items"].append("Monitor individual sector momentum trends")
            recommendations["action_items"].append("Consider diversified sector allocation")
        
        # Market breadth insights
        market_breadth = rotation_analysis.get("market_breadth", 0)
        if market_breadth > 0.7:
            recommendations["key_insights"].append("Broad market strength supporting sector rotation")
        elif market_breadth < 0.3:
            recommendations["key_insights"].append("Narrow market leadership - selective opportunities")
        
        return recommendations
    
    def _calculate_overall_score(self, sector_performance: Dict[str, Any], rotation_analysis: Dict[str, Any]) -> float:
        """Calculate overall sector rotation score (0-100)"""
        try:
            # Base score from market breadth
            market_breadth = rotation_analysis.get("market_breadth", 0.5)
            base_score = market_breadth * 50  # 0-50 points
            
            # Momentum bonus
            positive_sectors = rotation_analysis.get("positive_sectors", 0)
            total_sectors = rotation_analysis.get("sector_count", 1)
            momentum_score = (positive_sectors / total_sectors) * 30  # 0-30 points
            
            # Rotation phase bonus
            rotation_phase = rotation_analysis.get("rotation_phase", "Uncertain Rotation")
            phase_score = 0
            if "Risk-On" in rotation_phase:
                phase_score = 20
            elif "Defensive" in rotation_phase:
                phase_score = 15
            elif "Mixed" in rotation_phase:
                phase_score = 10
            else:
                phase_score = 5
            
            total_score = base_score + momentum_score + phase_score
            return min(100, max(0, total_score))
            
        except Exception as e:
            logger.warning(f"Error calculating overall score: {e}")
            return 50.0
    
    def _analyze_sector_correlations(self, sector_performance: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze sector correlations and rotation patterns"""
        try:
            if len(sector_performance) < 2:
                return {"correlation_strength": "insufficient_data"}
            
            # Group sectors by performance characteristics
            cyclical_sectors = []
            defensive_sectors = []
            growth_sectors = []
            
            for sector, data in sector_performance.items():
                return_val = data.get("total_return", 0)
                momentum_val = data.get("momentum", 0)
                
                # Classify sectors based on performance patterns
                if sector in ["Energy", "Materials", "Industrials", "Financials"]:
                    cyclical_sectors.append((sector, return_val, momentum_val))
                elif sector in ["Utilities", "Consumer Staples", "Healthcare", "Real Estate"]:
                    defensive_sectors.append((sector, return_val, momentum_val))
                elif sector in ["Technology", "Consumer Discretionary", "Communication Services"]:
                    growth_sectors.append((sector, return_val, momentum_val))
            
            # Calculate correlation strength
            correlation_strength = "moderate"
            
            # Check for strong correlations within groups
            if cyclical_sectors:
                cyclical_returns = [r[1] for r in cyclical_sectors]
                cyclical_std = self._calculate_std(cyclical_returns)
                if cyclical_std < 0.02:  # Low standard deviation = high correlation
                    correlation_strength = "strong"
            
            if defensive_sectors:
                defensive_returns = [r[1] for r in defensive_sectors]
                defensive_std = self._calculate_std(defensive_returns)
                if defensive_std < 0.02:
                    correlation_strength = "strong"
            
            return {
                "correlation_strength": correlation_strength,
                "cyclical_sectors": len(cyclical_sectors),
                "defensive_sectors": len(defensive_sectors),
                "growth_sectors": len(growth_sectors),
                "rotation_pattern": self._identify_rotation_pattern(cyclical_sectors, defensive_sectors, growth_sectors)
            }
            
        except Exception as e:
            logger.warning(f"Error analyzing sector correlations: {e}")
            return {"correlation_strength": "error"}
    
    def _calculate_std(self, values: List[float]) -> float:
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5
    
    def _identify_rotation_pattern(self, cyclical: List, defensive: List, growth: List) -> str:
        """Identify the rotation pattern based on sector group performance"""
        try:
            # Calculate average returns for each group
            cyclical_avg = sum(r[1] for r in cyclical) / len(cyclical) if cyclical else 0
            defensive_avg = sum(r[1] for r in defensive) / len(defensive) if defensive else 0
            growth_avg = sum(r[1] for r in growth) / len(growth) if growth else 0
            
            # Determine rotation pattern
            if cyclical_avg > defensive_avg and cyclical_avg > growth_avg:
                return "cyclical_leadership"
            elif defensive_avg > cyclical_avg and defensive_avg > growth_avg:
                return "defensive_leadership"
            elif growth_avg > cyclical_avg and growth_avg > defensive_avg:
                return "growth_leadership"
            else:
                return "mixed_rotation"
                
        except Exception as e:
            logger.warning(f"Error identifying rotation pattern: {e}")
            return "uncertain"

    def _calculate_momentum_score(self, sector_performance: Dict[str, Any]) -> float:
        """Calculate momentum score with trend analysis (0-1)"""
        try:
            momentum_values = []
            trend_strength = []
            
            for sector, data in sector_performance.items():
                momentum = data.get("momentum", 0)
                momentum_values.append(momentum)
                
                # Analyze trend strength based on recent performance
                recent_return = data.get("recent_return", 0)
                if abs(recent_return) > 0.02:  # 2%+ recent movement
                    trend_strength.append(abs(recent_return))
            
            if not momentum_values:
                return 0.5
            
            # Calculate average momentum
            avg_momentum = sum(momentum_values) / len(momentum_values)
            
            # Adjust for trend strength
            if trend_strength:
                avg_trend_strength = sum(trend_strength) / len(trend_strength)
                # Boost momentum score if trends are strong
                momentum_adjustment = min(0.2, avg_trend_strength * 2)
                avg_momentum += momentum_adjustment
            
            # Convert to 0-1 scale (momentum is typically -0.1 to +0.1)
            normalized_momentum = (avg_momentum + 0.1) / 0.2  # Shift and scale
            return max(0, min(1, normalized_momentum))
            
        except Exception as e:
            logger.warning(f"Error calculating momentum score: {e}")
            return 0.5
    
    def _generate_rotation_signals(self, sector_performance: Dict[str, Any], rotation_analysis: Dict[str, Any]) -> List[str]:
        """Generate specific, actionable rotation signals for UI display"""
        signals = []
        
        try:
            # Top performers with specific returns
            top_performers = rotation_analysis.get("top_performers", [])
            if top_performers:
                for sector in top_performers[:3]:
                    sector_data = sector_performance.get(sector, {})
                    return_pct = sector_data.get("total_return", 0) * 100
                    signals.append(f"{sector} sector up {return_pct:.1f}% - leading market")
            
            # Top momentum with specific momentum scores
            top_momentum = rotation_analysis.get("top_momentum", [])
            if top_momentum:
                for sector in top_momentum[:3]:
                    sector_data = sector_performance.get(sector, {})
                    momentum_pct = sector_data.get("momentum", 0) * 100
                    signals.append(f"{sector} momentum {momentum_pct:+.1f}% - accelerating trend")
            
            # Rotation phase with specific implications
            rotation_phase = rotation_analysis.get("rotation_phase", "Uncertain Rotation")
            if "Risk-Off" in rotation_phase:
                signals.append("Risk-off rotation: Defensive sectors favored")
            elif "Risk-On" in rotation_phase:
                signals.append("Risk-on rotation: Cyclical sectors gaining momentum")
            elif "Mixed" in rotation_phase:
                signals.append("Mixed rotation: Sector-specific opportunities")
            else:
                signals.append(f"Current phase: {rotation_phase}")
            
            # Market breadth with specific implications
            market_breadth = rotation_analysis.get("market_breadth", 0.5)
            if market_breadth > 0.7:
                signals.append("Broad market strength: Diversified sector participation")
            elif market_breadth < 0.3:
                signals.append("Narrow leadership: Focus on outperforming sectors")
            else:
                signals.append("Moderate breadth: Balanced sector performance")
            
            # Add sector count for context
            sector_count = len(sector_performance)
            if sector_count > 0:
                signals.append(f"Analyzing {sector_count} sectors for rotation patterns")
            
            # Add timing indicators
            timing_signals = self._generate_timing_indicators(sector_performance, rotation_analysis)
            signals.extend(timing_signals)
            
        except Exception as e:
            logger.warning(f"Error generating rotation signals: {e}")
            signals = ["Sector rotation analysis in progress"]
        
        return signals[:5]  # Limit to 5 signals

    def _generate_timing_indicators(self, sector_performance: Dict[str, Any], rotation_analysis: Dict[str, Any]) -> List[str]:
        """Generate timing indicators for sector rotation entry/exit signals"""
        timing_signals = []
        
        try:
            # Check for early rotation signals
            top_momentum = rotation_analysis.get("top_momentum", [])
            if top_momentum:
                for sector in top_momentum[:2]:  # Top 2 momentum sectors
                    sector_data = sector_performance.get(sector, {})
                    momentum = sector_data.get("momentum", 0)
                    recent_return = sector_data.get("recent_return", 0)
                    
                    # Early entry signal
                    if momentum > 0.01 and recent_return > 0.01:  # Strong momentum + recent gains
                        timing_signals.append(f"Early entry signal: {sector} momentum building")
                    
                    # Late entry warning
                    elif momentum > 0.02 and recent_return > 0.05:  # Very strong momentum + high recent gains
                        timing_signals.append(f"Late entry warning: {sector} may be overextended")
            
            # Check for exit signals
            bottom_performers = rotation_analysis.get("bottom_performers", [])
            if bottom_performers:
                for sector in bottom_performers[:2]:  # Bottom 2 performers
                    sector_data = sector_performance.get(sector, {})
                    momentum = sector_data.get("momentum", 0)
                    recent_return = sector_data.get("recent_return", 0)
                    
                    # Exit signal
                    if momentum < -0.01 and recent_return < -0.01:  # Negative momentum + recent losses
                        timing_signals.append(f"Exit signal: {sector} momentum deteriorating")
            
            # Market breadth timing
            market_breadth = rotation_analysis.get("market_breadth", 0.5)
            if market_breadth > 0.8:
                timing_signals.append("Market breadth extreme: Consider profit-taking")
            elif market_breadth < 0.2:
                timing_signals.append("Market breadth extreme: Look for reversal opportunities")
            
        except Exception as e:
            logger.warning(f"Error generating timing indicators: {e}")
        
        return timing_signals[:2]  # Limit to 2 timing signals


async def analyze_sector_rotation(ticker: str, days_back: int = 90) -> Dict[str, Any]:
    """
    Main function to analyze sector rotation for a ticker
    
    Args:
        ticker: Stock ticker symbol
        days_back: Number of days to analyze
        
    Returns:
        Dictionary containing sector rotation analysis
    """
    analyzer = SectorRotationAnalyzer()
    return await analyzer.analyze_sector_rotation(ticker, days_back)
