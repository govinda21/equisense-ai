import { Icons } from './icons'
import { TechnicalChart } from './TechnicalChart'

function currencySymbolForTicker(ticker?: string): string {
  if (!ticker) return '$'
  const t = ticker.toUpperCase()
  if (t.endsWith('.NS') || t.endsWith('.BO')) return '₹'
  return '$'
}

function formatAmountByCurrency(value?: number, ticker?: string): string {
  // Return dash for undefined, null, NaN, or 0 values
  if (value === undefined || value === null || isNaN(Number(value)) || value === 0) return '—'
  const symbol = currencySymbolForTicker(ticker)
  const v = Number(value)
  // Heuristic: INR formatting (Crores/Lakhs) for NSE/BSE tickers
  if (symbol === '₹') {
    const abs = Math.abs(v)
    if (abs >= 1e7) return `₹${(v / 1e7).toFixed(1)} Cr`
    if (abs >= 1e5) return `₹${(v / 1e5).toFixed(1)} L`
    return `₹${v.toLocaleString()}`
  }
  // Default (USD-like) B/M formatting
  const abs = Math.abs(v)
  if (abs >= 1e12) return `${symbol}${(v / 1e12).toFixed(1)}T`
  if (abs >= 1e9) return `${symbol}${(v / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `${symbol}${(v / 1e6).toFixed(1)}M`
  return `${symbol}${v.toLocaleString()}`
}

function formatBuyZone(low?: number, high?: number, ticker?: string): string {
  // Return dash if both values are 0, undefined, or null
  if ((!low || low === 0) && (!high || high === 0)) return '—'
  return `${formatAmountByCurrency(low, ticker)} – ${formatAmountByCurrency(high, ticker)}`
}

export function ResultSummaryGrid({ report }: { report: any }) {
  const labels: string[] = report?.technicals?.details?.labels ?? []
  const closes: number[] = report?.technicals?.details?.closes ?? []
  const ticker: string | undefined = report?.ticker
  const signals = report?.technicals?.details?.signals
  const indicators = report?.technicals?.details?.indicators
  const comp = report?.comprehensive_fundamentals
  
  // Available analysis sections (only show if data exists)
  const filings = report?.filings
  const earningsCall = report?.earnings_call_analysis
  const strategicConviction = report?.strategic_conviction
  const insiderTracking = report?.insider_tracking

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* 1. PRIMARY RECOMMENDATION - Full Width */}
      <div className="card p-4 sm:p-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 sm:gap-0 mb-4">
          <h2 className="text-xl sm:text-2xl font-bold text-slate-900">Investment Recommendation</h2>
          <div className="flex items-center space-x-2 sm:space-x-4">
            <button
              onClick={async () => {
                try {
                  const response = await fetch('/api/generate-pdf', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ tickers: [report?.ticker] })
                  });
                  if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `${report?.ticker}_report.pdf`;
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    window.URL.revokeObjectURL(url);
                  }
                } catch (error) {
                  console.error('PDF generation failed:', error);
                  alert('PDF generation failed. Please try again.');
                }
              }}
              className="flex items-center space-x-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs sm:text-sm rounded-lg transition-colors"
            >
              <Icons.Download className="w-4 h-4" />
              <span>PDF</span>
            </button>
            <div className="flex items-center space-x-2">
              <Icons.Star className="w-5 h-5 sm:w-6 sm:h-6 text-yellow-500" />
              <span className="text-xs sm:text-sm text-slate-600">Professional Analysis</span>
            </div>
          </div>
        </div>
        
        {/* Recommendation Header */}
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4 sm:p-6 mb-4 sm:mb-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-4">
            <div className="flex items-center space-x-4">
              <div className="text-3xl sm:text-4xl font-bold text-blue-900">
                {report?.decision?.action || 'Hold'}
              </div>
              <div className="text-left sm:text-right">
                <div className="text-xl sm:text-2xl font-semibold text-blue-700">
                  {report?.decision?.rating?.toFixed(1) || '2.5'}/5.0
                </div>
                <div className="text-base sm:text-lg tracking-wider text-yellow-500">
                  {(() => {
                    const rating = report?.decision?.rating || 0;
                    const fullStars = Math.floor(rating);
                    const hasHalf = (rating - fullStars) >= 0.5;
                    let stars = "★".repeat(fullStars);
                    if (hasHalf && fullStars < 5) stars += "☆";
                    stars += "☆".repeat(5 - stars.length);
                    return stars;
                  })()}
                </div>
              </div>
            </div>
            <div className="text-left sm:text-right">
              <div className="text-sm text-slate-600 mb-1">Grade</div>
              <div className="text-2xl font-bold text-slate-900">
                {report?.decision?.letter_grade || 'C'}
              </div>
            </div>
          </div>
          
          {/* Executive Summary */}
          {report?.decision?.executive_summary && (
            <div className="bg-white rounded-lg p-4 border border-blue-100">
              <div className="text-sm font-semibold text-slate-900 mb-2">Executive Summary</div>
              <div className="text-sm text-slate-700 leading-relaxed">
                {report.decision.executive_summary}
              </div>
            </div>
          )}
        </div>

        {/* Key Metrics Grid - Mobile Responsive */}
        <div className="grid grid-cols-1 xs:grid-cols-2 sm:grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 mb-4 sm:mb-6">
          {report?.decision?.price_target_12m && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
              <div className="text-xs text-green-600 uppercase font-medium mb-1">Price Target</div>
              <div className="text-xl font-bold text-green-900">
                {formatAmountByCurrency(report.decision.price_target_12m, ticker)}
              </div>
              <div className="text-xs text-green-600">{report.decision.price_target_source}</div>
            </div>
          )}
          
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
            <div className="text-xs text-blue-600 uppercase font-medium mb-1">Expected Return</div>
            <div className={`text-xl font-bold ${
              (report.decision.expected_return_pct || 0) > 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {report.decision.expected_return_pct > 0 ? '+' : ''}{report.decision.expected_return_pct?.toFixed(1) || '0'}%
            </div>
          </div>

          {comp?.intrinsic_value && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 text-center">
              <div className="text-xs text-purple-600 uppercase font-medium mb-1">Intrinsic Value</div>
              <div className="text-xl font-bold text-purple-900">
                {formatAmountByCurrency(comp.intrinsic_value, ticker)}
              </div>
              <div className="text-xs text-purple-600">
                MoS: {comp.margin_of_safety ? (comp.margin_of_safety * 100).toFixed(0) + '%' : '—'}
              </div>
            </div>
          )}

          {comp?.target_price && (
            <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 text-center">
              <div className="text-xs text-orange-600 uppercase font-medium mb-1">Target Price</div>
              <div className="text-xl font-bold text-orange-900">
                {formatAmountByCurrency(comp.target_price, ticker)}
              </div>
              <div className="text-xs text-orange-600">
                Stop: {formatAmountByCurrency(comp.stop_loss, ticker)}
              </div>
            </div>
          )}
        </div>

        {/* Investment Thesis - Mobile Responsive */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3 sm:gap-4 mb-4 sm:mb-6">
          {/* Growth Drivers */}
          {report?.decision?.growth_drivers?.length > 0 && (
            <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
              <h4 className="font-semibold text-emerald-900 mb-3 flex items-center">
                <Icons.TrendingUp className="w-5 h-5 mr-2" />
                Growth Drivers
              </h4>
              <ul className="text-sm text-emerald-800 space-y-2">
                {report.decision.growth_drivers.slice(0, 3).map((driver: string, i: number) => (
                  <li key={i} className="flex items-start">
                    <span className="mr-2 text-emerald-600">•</span>
                    <span>{driver}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Competitive Advantages */}
          {report?.decision?.competitive_advantages?.length > 0 && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="font-semibold text-blue-900 mb-3 flex items-center">
                <Icons.Shield className="w-5 h-5 mr-2" />
                Competitive Advantages
              </h4>
              <ul className="text-sm text-blue-800 space-y-2">
                {report.decision.competitive_advantages.slice(0, 3).map((advantage: string, i: number) => (
                  <li key={i} className="flex items-start">
                    <span className="mr-2 text-blue-600">•</span>
                    <span>{advantage}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Key Risks */}
          {report?.decision?.key_risks?.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <h4 className="font-semibold text-red-900 mb-3 flex items-center">
                <Icons.AlertTriangle className="w-5 h-5 mr-2" />
                Key Risks
              </h4>
              <ul className="text-sm text-red-800 space-y-2">
                {report.decision.key_risks.slice(0, 3).map((risk: string, i: number) => (
                  <li key={i} className="flex items-start">
                    <span className="mr-2 text-red-600">•</span>
                    <span>{risk}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Outlook Section */}
        <div className="grid md:grid-cols-2 gap-4">
          {report?.decision?.short_term_outlook && (
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <h4 className="font-semibold text-blue-900 mb-2">Short-Term Outlook (3-6 Months)</h4>
              <p className="text-sm text-blue-800 leading-relaxed">
                {report.decision.short_term_outlook}
              </p>
            </div>
          )}
          
          {report?.decision?.long_term_outlook && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
              <h4 className="font-semibold text-purple-900 mb-2">Long-Term Outlook (12-36 Months)</h4>
              <p className="text-sm text-purple-800 leading-relaxed">
                {report.decision.long_term_outlook}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* 2. COMPREHENSIVE FUNDAMENTALS - Full Width */}
      {comp && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-slate-900">Comprehensive Fundamental Analysis</h2>
            <Icons.ChartPie className="w-6 h-6 text-slate-500" />
          </div>
          
          {/* Pillar Scores */}
          <div className="grid grid-cols-1 xs:grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3 sm:gap-4 mb-4 sm:mb-6">
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-center">
              <div className="text-xs text-slate-500 uppercase font-medium mb-2">Financial Health</div>
              <div className="text-2xl font-bold text-slate-900">{comp.financial_health_score?.toFixed(0) || '—'}</div>
              <div className="text-xs text-slate-600">Score</div>
            </div>
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-center">
              <div className="text-xs text-slate-500 uppercase font-medium mb-2">Valuation</div>
              <div className="text-2xl font-bold text-slate-900">{comp.valuation_score?.toFixed(0) || '—'}</div>
              <div className="text-xs text-slate-600">Score</div>
            </div>
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-center">
              <div className="text-xs text-slate-500 uppercase font-medium mb-2">Growth</div>
              <div className="text-2xl font-bold text-slate-900">{comp.growth_prospects_score?.toFixed(0) || '—'}</div>
              <div className="text-xs text-slate-600">Score</div>
            </div>
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-center">
              <div className="text-xs text-slate-500 uppercase font-medium mb-2">Governance</div>
              <div className="text-2xl font-bold text-slate-900">{comp.governance_score?.toFixed(0) || '—'}</div>
              <div className="text-xs text-slate-600">Score</div>
            </div>
            <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 text-center">
              <div className="text-xs text-slate-500 uppercase font-medium mb-2">Macro</div>
              <div className="text-2xl font-bold text-slate-900">{comp.macro_sensitivity_score?.toFixed(0) || '—'}</div>
              <div className="text-xs text-slate-600">Score</div>
            </div>
          </div>

          {/* Trading Recommendations */}
          <div className="grid md:grid-cols-3 gap-4 mb-6">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="text-sm text-blue-600 font-medium mb-2">Entry Zone</div>
              <div className="text-xl font-bold text-blue-900">
                {formatBuyZone(comp.entry_zone_low, comp.entry_zone_high, ticker)}
              </div>
            </div>
            <div className="bg-green-50 border border-green-200 rounded-lg p-4">
              <div className="text-sm text-green-600 font-medium mb-2">Target Price</div>
              <div className="text-xl font-bold text-green-900">
                {formatAmountByCurrency(comp.target_price, ticker)}
              </div>
            </div>
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <div className="text-sm text-red-600 font-medium mb-2">Stop Loss</div>
              <div className="text-xl font-bold text-red-900">
                {formatAmountByCurrency(comp.stop_loss, ticker)}
              </div>
            </div>
          </div>

          {/* Risk Assessment */}
          <div className="grid md:grid-cols-2 gap-4">
            <div>
              <div className="text-sm font-semibold text-slate-900 mb-3">Key Risks</div>
              <div className="space-y-2">
                {comp.key_risks?.slice(0, 3).map((risk: string, idx: number) => (
                  <div key={idx} className="text-sm text-red-700 flex items-start">
                    <Icons.AlertTriangle className="w-4 h-4 mr-2 mt-0.5 text-red-500" />
                    {risk}
                  </div>
                ))}
              </div>
            </div>
            <div>
              <div className="text-sm font-semibold text-slate-900 mb-3">Key Catalysts</div>
              <div className="space-y-2">
                {comp.key_catalysts?.slice(0, 3).map((catalyst: string, idx: number) => (
                  <div key={idx} className="text-sm text-green-700 flex items-start">
                    <Icons.Shield className="w-4 h-4 mr-2 mt-0.5 text-green-500" />
                    {catalyst}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 3. TECHNICAL ANALYSIS - Full Width */}
      {labels.length > 0 && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-slate-900">Technical Analysis</h2>
            <Icons.Technical className="w-6 h-6 text-slate-500" />
          </div>
          
          <div className="grid md:grid-cols-2 gap-6">
            {/* Chart */}
            <div>
              <TechnicalChart labels={labels} closes={closes} />
            </div>
            
            {/* Technical Indicators */}
            <div className="space-y-4">
              {indicators && (
                <div className="grid grid-cols-1 xs:grid-cols-2 gap-3 sm:gap-4">
                  <div className="bg-slate-50 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">RSI (14)</div>
                    <div className="text-lg font-semibold text-slate-900">
                      {indicators.rsi14?.toFixed(1) || '—'}
                    </div>
                  </div>
                  <div className="bg-slate-50 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">MACD</div>
                    <div className="text-lg font-semibold text-slate-900">
                      {indicators.macd?.macd?.toFixed(2) || '—'}
                    </div>
                  </div>
                  <div className="bg-slate-50 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">SMA 20</div>
                    <div className="text-lg font-semibold text-slate-900">
                      {formatAmountByCurrency(indicators.sma20, ticker)}
                    </div>
                  </div>
                  <div className="bg-slate-50 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">SMA 50</div>
                    <div className="text-lg font-semibold text-slate-900">
                      {formatAmountByCurrency(indicators.sma50, ticker)}
                    </div>
                  </div>
                </div>
              )}
              
              {signals && (
                <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                  <div className="text-sm font-semibold text-blue-900 mb-2">Technical Signals</div>
                  <div className="text-lg font-bold text-blue-700 capitalize">
                    {signals.regime || 'Neutral'}
                  </div>
                  <div className="text-sm text-blue-600">
                    Score: {(signals.score * 100).toFixed(0)}%
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 4. MARKET SENTIMENT - Two Columns */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* News Sentiment */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold">News Sentiment</h3>
            <Icons.Sentiment className="w-5 h-5 text-slate-500" />
          </div>
          <div className="space-y-3">
            {report?.news_sentiment?.summary && (
              <div className="bg-slate-50 rounded-lg p-3">
                <div className="text-sm text-slate-700 leading-relaxed">
                  {report.news_sentiment.summary}
                </div>
              </div>
            )}
            <div className="text-sm text-slate-600">
              Confidence: {(report?.news_sentiment?.confidence * 100)?.toFixed(0) || 0}%
            </div>
          </div>
        </div>

        {/* YouTube Sentiment */}
        <div className="card p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-lg font-semibold">YouTube Analysis</h3>
            <Icons.MessageCircle className="w-5 h-5 text-slate-500" />
          </div>
          <div className="space-y-3">
            {report?.youtube_sentiment?.summary && (
              <div className="bg-slate-50 rounded-lg p-3">
                <div className="text-sm text-slate-700 leading-relaxed">
                  {report.youtube_sentiment.summary}
                </div>
              </div>
            )}
            <div className="text-sm text-slate-600">
              Confidence: {(report?.youtube_sentiment?.confidence * 100)?.toFixed(0) || 0}%
            </div>
          </div>
        </div>
      </div>

      {/* 5. ADDITIONAL ANALYSIS SECTIONS - Only show if data exists */}
      {(filings || earningsCall || strategicConviction || insiderTracking) && (
        <div className="grid md:grid-cols-2 gap-6">
          {/* Filing Analysis */}
          {filings && (
            <div className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-semibold">Regulatory Filings</h3>
                <Icons.DocumentText className="w-5 h-5 text-slate-500" />
              </div>
              <div className="text-sm text-slate-600">
                Filing analysis available
              </div>
            </div>
          )}

          {/* Earnings Call Analysis */}
          {earningsCall && (
            <div className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-semibold">Earnings Call Analysis</h3>
                <Icons.Microphone className="w-5 h-5 text-slate-500" />
              </div>
              <div className="text-sm text-slate-600">
                Earnings call analysis available
              </div>
            </div>
          )}

          {/* Strategic Conviction */}
          {strategicConviction && (
            <div className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-semibold">Strategic Conviction</h3>
                <Icons.ChartBar className="w-5 h-5 text-slate-500" />
              </div>
              <div className="text-sm text-slate-600">
                Strategic analysis available
              </div>
            </div>
          )}

          {/* Insider Tracking */}
          {insiderTracking && (
            <div className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-semibold">Insider Trading</h3>
                <Icons.UserGroup className="w-5 h-5 text-slate-500" />
              </div>
              <div className="text-sm text-slate-600">
                Insider tracking available
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}