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

function parseNewsSentiment(summary: string): React.ReactNode {
  if (!summary) return null;

  const lines = summary.split('\n').filter(line => line.trim());
  const elements: React.ReactNode[] = [];
  
  let currentSection = '';
  let currentItems: string[] = [];
  
  for (const line of lines) {
    if (line.startsWith('**') && line.endsWith('**')) {
      // Flush previous section
      if (currentSection && currentItems.length > 0) {
        elements.push(
          <div key={currentSection} className="space-y-2">
            <h4 className="font-semibold text-slate-800">{currentSection}</h4>
            <ul className="space-y-1">
              {currentItems.map((item, index) => (
                <li key={index} className="text-sm text-slate-700 flex items-start">
                  <span className="mr-2">•</span>
                  <span className="flex-1">{parseNewsItem(item)}</span>
                </li>
              ))}
            </ul>
          </div>
        );
      }
      
      // Start new section
      currentSection = line.replace(/\*\*/g, '');
      currentItems = [];
    } else if (line.startsWith('•')) {
      currentItems.push(line.substring(1).trim());
    } else if (line.trim()) {
      // Handle overall sentiment or other content
      if (currentSection === 'Overall Sentiment') {
        elements.push(
          <div key="overall-sentiment" className="bg-slate-50 rounded-lg p-3">
            <div className="text-sm font-medium text-slate-800">{line}</div>
          </div>
        );
      } else if (line.trim()) {
        currentItems.push(line.trim());
      }
    }
  }
  
  // Flush last section
  if (currentSection && currentItems.length > 0) {
    elements.push(
      <div key={currentSection} className="space-y-2">
        <h4 className="font-semibold text-slate-800">{currentSection}</h4>
        <ul className="space-y-1">
          {currentItems.map((item, index) => (
            <li key={index} className="text-sm text-slate-700 flex items-start">
              <span className="mr-2">•</span>
              <span className="flex-1">{parseNewsItem(item)}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  
  return elements.length > 0 ? elements : (
    <div className="bg-slate-50 rounded-lg p-3">
      <div className="text-sm text-slate-700">{summary}</div>
    </div>
  );
}

function parseNewsItem(item: string): React.ReactNode {
  // Parse news item with date and freshness indicators
  const parts = item.split(' — ');
  if (parts.length < 2) return item;
  
  const headline = parts[0];
  const rest = parts.slice(1).join(' — ');
  
  // Extract date and sentiment info
  const dateMatch = rest.match(/\(([^)]+)\)/);
  const date = dateMatch ? dateMatch[1] : '';
  const sentimentPart = rest.replace(/\([^)]+\)/, '').trim();
  
  // Check for freshness warnings
  const hasOldYearWarning = item.includes('⚠️ (Old - 1+ year)');
  const hasOldMonthsWarning = item.includes('⚠️ (Old - 6+ months)');
  
  return (
    <div className="space-y-1">
      <div className="font-medium">{headline}</div>
      <div className="flex items-center gap-2 text-xs">
        <span className={`px-2 py-1 rounded text-xs font-medium ${
          sentimentPart.includes('Positive') ? 'bg-green-100 text-green-800' :
          sentimentPart.includes('Negative') ? 'bg-red-100 text-red-800' :
          'bg-gray-100 text-gray-800'
        }`}>
          {sentimentPart.split(';')[0]}
        </span>
        {date && (
          <span className="text-slate-500">
            📅 {date}
          </span>
        )}
        {hasOldYearWarning && (
          <span className="text-red-600 font-medium">⚠️ Old News (1+ year)</span>
        )}
        {hasOldMonthsWarning && (
          <span className="text-orange-600 font-medium">⚠️ Old News (6+ months)</span>
        )}
      </div>
      <div className="text-slate-600 text-xs">
        {sentimentPart.split(';')[1]?.trim()}
      </div>
    </div>
  );
}

export function ResultSummaryGrid({ report }: { report: any }) {
  const labels: string[] = report?.technicals?.details?.labels ?? []
  const closes: number[] = report?.technicals?.details?.closes ?? []
  const ticker: string | undefined = report?.ticker
  const signals = report?.technicals?.details?.signals
  const indicators = report?.technicals?.details?.indicators
  const comp = report?.comprehensive_fundamentals
  const deepFinancialAnalysis = report?.fundamentals?.details?.deep_financial_analysis
  const dcfValuation = report?.fundamentals?.details?.dcf_valuation
  
  // Available analysis sections (only show if data exists)
  const filings = report?.filings
  const earningsCall = report?.earnings_call_analysis
  const strategicConviction = report?.strategic_conviction
  const sectorRotation = report?.sector_rotation
  const insiderTracking = report?.insider_tracking

  // Debug logging
  console.log('ResultSummaryGrid - report:', report)
  console.log('ResultSummaryGrid - earningsCall:', earningsCall)
  console.log('ResultSummaryGrid - earningsCall.status:', earningsCall?.status)
  console.log('ResultSummaryGrid - earningsCall.status === "success":', earningsCall?.status === 'success')
  console.log('ResultSummaryGrid - earningsCall exists:', earningsCall != null)

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
          
            {/* Confidence and Conviction */}
            <div className="text-left sm:text-right">
              <div className="text-sm text-slate-600 mb-1">Confidence</div>
              <div className="text-lg font-semibold text-slate-900">
                {report?.decision?.confidence_score ? `${report.decision.confidence_score.toFixed(0)}%` : 'N/A'}
              </div>
              <div className="text-xs text-slate-500">
                {report?.decision?.conviction_level || 'Moderate'}
              </div>
            </div>
          </div>
          
          {/* Executive Summary */}
          {(report?.decision?.executive_summary || report?.decision?.professional_rationale) && (
            <div className="bg-white rounded-lg p-4 border border-blue-100">
              <div className="text-sm font-semibold text-slate-900 mb-2">Executive Summary</div>
          <div className="text-sm text-slate-700 leading-relaxed">
                {(() => {
                  const execSummary = report?.decision?.executive_summary || '';
                  const profAnalysis = report?.decision?.professional_rationale || '';
                  
                  // If both exist, combine them intelligently
                  if (execSummary && profAnalysis) {
                    // Remove redundant phrases and combine smoothly
                    let combined = execSummary;
                    
                    // Remove common redundant phrases from professional analysis
                    let cleanProfAnalysis = profAnalysis
                      .replace(/Given trading above intrinsic value \([^)]+\) and /g, '')
                      .replace(/Given [^,]+, /g, '')
                      .replace(/the near-term outlook appears challenging\. /g, '')
                      .replace(/Profit-taking may be warranted while monitoring for potential re-entry opportunities\./g, '');
                    
                    // Clean up any remaining redundancy
                    cleanProfAnalysis = cleanProfAnalysis.trim();
                    
                    // Combine with proper flow
                    if (cleanProfAnalysis && !execSummary.includes(cleanProfAnalysis)) {
                      combined += ' ' + cleanProfAnalysis;
                    }
                    
                    return combined;
                  }
                  
                  // Return whichever exists
                  return execSummary || profAnalysis;
            })()}
          </div>
        </div>
          )}
      </div>

        {/* Key Metrics Grid - Mobile Responsive */}
        <div className="grid grid-cols-1 xs:grid-cols-2 sm:grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4 mb-4 sm:mb-6">
          {/* 1. CMP (Current Market Price) */}
          {report?.analyst_recommendations?.details?.current_price && (
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4 text-center">
              <div className="text-xs text-gray-600 uppercase font-medium mb-1">CMP</div>
              <div className="text-xl font-bold text-gray-900">
                {formatAmountByCurrency(report.analyst_recommendations.details.current_price, ticker)}
              </div>
            </div>
          )}

          {/* 2. Price Target */}
          {report?.decision?.price_target_12m && (
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
              <div className="text-xs text-green-600 uppercase font-medium mb-1">Price Target</div>
              <div className="text-xl font-bold text-green-900">
                {formatAmountByCurrency(report.decision.price_target_12m, ticker)}
              </div>
              <div className="text-xs text-green-600">{report.decision.price_target_source}</div>
      </div>
          )}
          
          {/* 3. Expected Return */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
            <div className="text-xs text-blue-600 uppercase font-medium mb-1">Expected Return</div>
            <div className={`text-xl font-bold ${
              (report.decision.expected_return_pct || 0) > 0 ? 'text-green-600' : 'text-red-600'
            }`}>
              {report.decision.expected_return_pct > 0 ? '+' : ''}{report.decision.expected_return_pct?.toFixed(1) || '0'}%
            </div>
          </div>

          {/* 4. DCF Scenarios */}
          <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
            <div className="text-xs text-purple-600 uppercase font-medium mb-2 text-center">DCF Scenarios</div>
            {dcfValuation?.dcf_applicable === false ? (
              <div className="text-center">
                <div className="text-sm text-orange-600 font-medium mb-2">⚠️ DCF Not Applicable</div>
                <div className="text-xs text-gray-600 mb-2">{dcfValuation.reason}</div>
                <div className="text-xs text-gray-500">{dcfValuation.valuation_method}</div>
              </div>
            ) : dcfValuation?.scenario_results && dcfValuation.scenario_results.length > 0 ? (
              <div className="space-y-1">
                {dcfValuation.scenario_results.map((scenario: any, index: number) => (
                  <div key={index} className="flex justify-between items-center text-sm">
                    <span className={`font-medium ${
                      scenario.scenario === 'Bull' ? 'text-green-700' : 
                      scenario.scenario === 'Base' ? 'text-blue-700' : 'text-red-700'
                    }`}>
                      {scenario.scenario} ({(scenario.probability * 100).toFixed(0)}%)
                    </span>
                    <span className="font-bold text-purple-900">
                      {formatAmountByCurrency(scenario.result.intrinsic_value_per_share, ticker)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-gray-500 text-center">DCF scenarios not available</div>
            )}
          </div>

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
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <div className="text-sm text-blue-600 font-medium mb-2">Analyst Target</div>
              <div className="text-xl font-bold text-blue-900">
                {formatAmountByCurrency(report?.analyst_recommendations?.details?.target_prices?.mean, ticker)}
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

      {/* DEEP FINANCIAL ANALYSIS - Full Width */}
      {deepFinancialAnalysis && deepFinancialAnalysis.ticker && (
        <div className="card p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-slate-900">Deep Financial Analysis</h2>
            <div className="text-sm text-slate-500">
              {deepFinancialAnalysis.analysis_period_years} Years Analysis
          </div>
            </div>
          
          {/* Financial Trends Grid */}
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 mb-6">
            {/* Revenue Analysis */}
            {deepFinancialAnalysis?.income_statement_trends?.total_revenue && (
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                <h4 className="font-semibold text-blue-900 mb-3">Revenue Analysis</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-blue-700">Latest:</span>
                    <span className="font-medium">{formatAmountByCurrency(deepFinancialAnalysis.income_statement_trends.total_revenue.latest, ticker)}</span>
            </div>
                  <div className="flex justify-between">
                    <span className="text-blue-700">5Y CAGR:</span>
                    <span className="font-medium">{(deepFinancialAnalysis.income_statement_trends.total_revenue.cagr_5y * 100).toFixed(1)}%</span>
          </div>
                  <div className="flex justify-between">
                    <span className="text-blue-700">10Y CAGR:</span>
                    <span className="font-medium">{(deepFinancialAnalysis.income_statement_trends.total_revenue.cagr_10y * 100).toFixed(1)}%</span>
                  </div>
                  </div>
                </div>
              )}

            {/* Profitability Analysis */}
            {deepFinancialAnalysis?.financial_ratios?.gross_margin && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <h4 className="font-semibold text-green-900 mb-3">Profitability</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-green-700">Gross Margin:</span>
                    <span className="font-medium">{(deepFinancialAnalysis.financial_ratios.gross_margin.latest * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-green-700">Avg Margin:</span>
                    <span className="font-medium">{(deepFinancialAnalysis.financial_ratios.gross_margin.average * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-green-700">Trend:</span>
                    <span className={`font-medium ${deepFinancialAnalysis.financial_ratios.gross_margin.trend === 'increasing' ? 'text-green-600' : deepFinancialAnalysis.financial_ratios.gross_margin.trend === 'decreasing' ? 'text-red-600' : 'text-gray-600'}`}>
                      {deepFinancialAnalysis.financial_ratios.gross_margin.trend}
                    </span>
                  </div>
                  </div>
                </div>
              )}

            {/* Growth Analysis */}
            {deepFinancialAnalysis?.growth_metrics?.revenue_growth && (
              <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                <h4 className="font-semibold text-purple-900 mb-3">Growth Metrics</h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-purple-700">YoY Growth:</span>
                    <span className="font-medium">{(deepFinancialAnalysis.growth_metrics.revenue_growth.yoy_growth * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-purple-700">3Y CAGR:</span>
                    <span className="font-medium">{(deepFinancialAnalysis.growth_metrics.revenue_growth.cagr_3y * 100).toFixed(1)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-purple-700">5Y CAGR:</span>
                    <span className="font-medium">{(deepFinancialAnalysis.growth_metrics.revenue_growth.cagr_5y * 100).toFixed(1)}%</span>
                  </div>
                </div>
            </div>
          )}
          </div>

          {/* Key Financial Ratios */}
          {deepFinancialAnalysis.financial_ratios && Object.keys(deepFinancialAnalysis.financial_ratios).length > 0 && (
            <div className="mb-6">
              <h4 className="font-semibold text-slate-900 mb-4">Key Financial Ratios</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
                {Object.entries(deepFinancialAnalysis.financial_ratios).slice(0, 12).map(([ratio, data]: [string, any]) => (
                  <div key={ratio} className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-center">
                    <div className="text-xs text-slate-500 uppercase font-medium mb-1">
                      {ratio.replace(/_/g, ' ')}
                    </div>
                    <div className="text-lg font-bold text-slate-900">
                      {data.latest ? (ratio.includes('margin') || ratio.includes('ratio') ? (data.latest * 100).toFixed(1) + '%' : data.latest.toFixed(2)) : '—'}
                    </div>
                    <div className="text-xs text-slate-600">
                      {data.trend || 'N/A'}
                    </div>
                  </div>
                ))}
              </div>
        </div>
      )}

          {/* Enhanced Earnings Quality & Balance Sheet Forensics */}
          {deepFinancialAnalysis.earnings_quality && Object.keys(deepFinancialAnalysis.earnings_quality).length > 0 && (
            <div className="mb-6">
              <h4 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
                <span className="text-2xl mr-2">🔍</span>
                Earnings Quality & Balance Sheet Forensics
              </h4>
              
              {/* Overall Quality Scores */}
              <div className="grid md:grid-cols-2 gap-4 mb-6">
                {deepFinancialAnalysis.earnings_quality.overall_quality_score && (
                  <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4">
                    <h5 className="font-medium text-blue-900 mb-2 flex items-center">
                      <span className="text-lg mr-2">📊</span>
                      Overall Earnings Quality
                    </h5>
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-blue-700">Score:</span>
                        <span className="font-bold text-lg">{deepFinancialAnalysis.earnings_quality.overall_quality_score.score?.toFixed(1) || 'N/A'}/100</span>
          </div>
                      <div className="flex justify-between items-center">
                        <span className="text-blue-700">Grade:</span>
                        <span className={`font-bold text-lg px-2 py-1 rounded ${
                          deepFinancialAnalysis.earnings_quality.overall_quality_score.grade === 'A' ? 'bg-green-100 text-green-800' :
                          deepFinancialAnalysis.earnings_quality.overall_quality_score.grade === 'B' ? 'bg-blue-100 text-blue-800' :
                          deepFinancialAnalysis.earnings_quality.overall_quality_score.grade === 'C' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {deepFinancialAnalysis.earnings_quality.overall_quality_score.grade}
                        </span>
            </div>
            </div>
            </div>
                )}
                
                {deepFinancialAnalysis.balance_sheet_strength?.overall_strength_score && (
                  <div className="bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg p-4">
                    <h5 className="font-medium text-green-900 mb-2 flex items-center">
                      <span className="text-lg mr-2">🏦</span>
                      Balance Sheet Strength
                    </h5>
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-green-700">Score:</span>
                        <span className="font-bold text-lg">{deepFinancialAnalysis.balance_sheet_strength.overall_strength_score.score?.toFixed(1) || 'N/A'}/100</span>
            </div>
                      <div className="flex justify-between items-center">
                        <span className="text-green-700">Grade:</span>
                        <span className={`font-bold text-lg px-2 py-1 rounded ${
                          deepFinancialAnalysis.balance_sheet_strength.overall_strength_score.grade === 'A' ? 'bg-green-100 text-green-800' :
                          deepFinancialAnalysis.balance_sheet_strength.overall_strength_score.grade === 'B' ? 'bg-blue-100 text-blue-800' :
                          deepFinancialAnalysis.balance_sheet_strength.overall_strength_score.grade === 'C' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {deepFinancialAnalysis.balance_sheet_strength.overall_strength_score.grade}
                        </span>
                </div>
                      <div className="flex justify-between items-center">
                        <span className="text-green-700">Strength:</span>
                        <span className={`font-medium px-2 py-1 rounded text-sm ${
                          deepFinancialAnalysis.balance_sheet_strength.overall_strength_score.strength_level === 'strong' ? 'bg-green-100 text-green-800' :
                          deepFinancialAnalysis.balance_sheet_strength.overall_strength_score.strength_level === 'moderate' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {deepFinancialAnalysis.balance_sheet_strength.overall_strength_score.strength_level}
                        </span>
                </div>
                </div>
                </div>
            )}
          </div>

              {/* CFO vs Net Income Analysis */}
              {deepFinancialAnalysis.earnings_quality.cfo_to_net_income && (
                <div className="bg-amber-50 border border-amber-200 rounded-lg p-4 mb-4">
                  <h5 className="font-medium text-amber-900 mb-3 flex items-center">
                    <span className="text-lg mr-2">💰</span>
                    CFO vs Net Income Analysis
                  </h5>
                  <div className="grid md:grid-cols-3 gap-4">
                    <div className="space-y-1 text-sm">
                      <div className="flex justify-between">
                        <span className="text-amber-700">Latest Ratio:</span>
                        <span className="font-medium">{deepFinancialAnalysis.earnings_quality.cfo_to_net_income.latest_ratio?.toFixed(2) || 'N/A'}</span>
              </div>
                      <div className="flex justify-between">
                        <span className="text-amber-700">Average Ratio:</span>
                        <span className="font-medium">{deepFinancialAnalysis.earnings_quality.cfo_to_net_income.average_ratio?.toFixed(2) || 'N/A'}</span>
                      </div>
                    </div>
                    <div className="space-y-1 text-sm">
                      <div className="flex justify-between">
                        <span className="text-amber-700">Quality Score:</span>
                        <span className={`font-medium ${
                          deepFinancialAnalysis.earnings_quality.cfo_to_net_income.quality_score === 'excellent' ? 'text-green-600' : 
                          deepFinancialAnalysis.earnings_quality.cfo_to_net_income.quality_score === 'good' ? 'text-blue-600' : 
                          deepFinancialAnalysis.earnings_quality.cfo_to_net_income.quality_score === 'fair' ? 'text-yellow-600' : 
                          'text-red-600'
                        }`}>
                          {deepFinancialAnalysis.earnings_quality.cfo_to_net_income.quality_score}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-amber-700">Consistency:</span>
                        <span className={`font-medium ${
                          deepFinancialAnalysis.earnings_quality.cfo_to_net_income.consistency_score === 'excellent' ? 'text-green-600' : 
                          deepFinancialAnalysis.earnings_quality.cfo_to_net_income.consistency_score === 'good' ? 'text-blue-600' : 
                          deepFinancialAnalysis.earnings_quality.cfo_to_net_income.consistency_score === 'fair' ? 'text-yellow-600' : 
                          'text-red-600'
                        }`}>
                          {deepFinancialAnalysis.earnings_quality.cfo_to_net_income.consistency_score}
                        </span>
                      </div>
                    </div>
                    <div className="space-y-1 text-sm">
                      <div className="flex justify-between">
                        <span className="text-amber-700">Trend:</span>
                        <span className={`font-medium ${
                          deepFinancialAnalysis.earnings_quality.cfo_to_net_income.trend === 'increasing' ? 'text-green-600' : 
                          deepFinancialAnalysis.earnings_quality.cfo_to_net_income.trend === 'stable' ? 'text-blue-600' : 
                          'text-red-600'
                        }`}>
                          {deepFinancialAnalysis.earnings_quality.cfo_to_net_income.trend}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-amber-700">Volatility:</span>
                        <span className="font-medium">{deepFinancialAnalysis.earnings_quality.cfo_to_net_income.volatility?.toFixed(3) || 'N/A'}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Earnings Manipulation Indicators */}
              {deepFinancialAnalysis.earnings_quality.manipulation_indicators && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
                  <h5 className="font-medium text-red-900 mb-3 flex items-center">
                    <span className="text-lg mr-2">⚠️</span>
                    Earnings Manipulation Risk Assessment
                  </h5>
                  <div className="grid md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-red-700">Risk Level:</span>
                        <span className={`font-bold px-2 py-1 rounded ${
                          deepFinancialAnalysis.earnings_quality.manipulation_indicators.overall_risk_score?.risk_level === 'low' ? 'bg-green-100 text-green-800' :
                          deepFinancialAnalysis.earnings_quality.manipulation_indicators.overall_risk_score?.risk_level === 'medium' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {deepFinancialAnalysis.earnings_quality.manipulation_indicators.overall_risk_score?.risk_level || 'Unknown'}
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-red-700">Risk Score:</span>
                        <span className="font-medium">{deepFinancialAnalysis.earnings_quality.manipulation_indicators.overall_risk_score?.risk_score?.toFixed(2) || 'N/A'}</span>
                      </div>
                    </div>
                    <div className="space-y-2">
                      <div className="flex justify-between items-center">
                        <span className="text-red-700">Assessment:</span>
                        <span className={`font-medium px-2 py-1 rounded text-sm ${
                          deepFinancialAnalysis.earnings_quality.manipulation_indicators.overall_risk_score?.overall_assessment === 'clean' ? 'bg-green-100 text-green-800' :
                          deepFinancialAnalysis.earnings_quality.manipulation_indicators.overall_risk_score?.overall_assessment === 'monitor' ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {deepFinancialAnalysis.earnings_quality.manipulation_indicators.overall_risk_score?.overall_assessment || 'Unknown'}
                        </span>
                      </div>
                      <div className="flex justify-between items-center">
                        <span className="text-red-700">Risk Factors:</span>
                        <span className="font-medium">{deepFinancialAnalysis.earnings_quality.manipulation_indicators.overall_risk_score?.risk_factors_count || 0}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Balance Sheet Analysis */}
              {deepFinancialAnalysis.balance_sheet_strength && (
                <div className="grid md:grid-cols-2 gap-4">
                  {/* Debt Analysis */}
                  {deepFinancialAnalysis.balance_sheet_strength.debt_analysis && (
                    <div className="bg-indigo-50 border border-indigo-200 rounded-lg p-4">
                      <h5 className="font-medium text-indigo-900 mb-2 flex items-center">
                        <span className="text-lg mr-2">📈</span>
                        Debt Structure Analysis
                      </h5>
                      <div className="space-y-1 text-sm">
                        <div className="flex justify-between">
                          <span className="text-indigo-700">Debt/Equity Ratio:</span>
                          <span className="font-medium">{deepFinancialAnalysis.balance_sheet_strength.debt_analysis.debt_equity_ratio?.latest?.toFixed(2) || 'N/A'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-indigo-700">Debt/Asset Ratio:</span>
                          <span className="font-medium">{deepFinancialAnalysis.balance_sheet_strength.debt_analysis.debt_asset_ratio?.latest?.toFixed(2) || 'N/A'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-indigo-700">Debt Strength:</span>
                          <span className={`font-medium ${
                            deepFinancialAnalysis.balance_sheet_strength.debt_analysis.debt_equity_ratio?.strength_score === 'excellent' ? 'text-green-600' : 
                            deepFinancialAnalysis.balance_sheet_strength.debt_analysis.debt_equity_ratio?.strength_score === 'good' ? 'text-blue-600' : 
                            deepFinancialAnalysis.balance_sheet_strength.debt_analysis.debt_equity_ratio?.strength_score === 'fair' ? 'text-yellow-600' : 
                            'text-red-600'
                          }`}>
                            {deepFinancialAnalysis.balance_sheet_strength.debt_analysis.debt_equity_ratio?.strength_score}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Interest Coverage */}
                  {deepFinancialAnalysis.balance_sheet_strength.interest_coverage && (
                    <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
                      <h5 className="font-medium text-purple-900 mb-2 flex items-center">
                        <span className="text-lg mr-2">🛡️</span>
                        Interest Coverage Analysis
                      </h5>
                      <div className="space-y-1 text-sm">
                        <div className="flex justify-between">
                          <span className="text-purple-700">Latest Coverage:</span>
                          <span className="font-medium">{deepFinancialAnalysis.balance_sheet_strength.interest_coverage.latest?.toFixed(1) || 'N/A'}x</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-purple-700">Average Coverage:</span>
                          <span className="font-medium">{deepFinancialAnalysis.balance_sheet_strength.interest_coverage.average?.toFixed(1) || 'N/A'}x</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-purple-700">Minimum Coverage:</span>
                          <span className="font-medium">{deepFinancialAnalysis.balance_sheet_strength.interest_coverage.minimum?.toFixed(1) || 'N/A'}x</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-purple-700">Adequacy:</span>
                          <span className={`font-medium ${
                            deepFinancialAnalysis.balance_sheet_strength.interest_coverage.adequacy_score === 'excellent' ? 'text-green-600' : 
                            deepFinancialAnalysis.balance_sheet_strength.interest_coverage.adequacy_score === 'good' ? 'text-blue-600' : 
                            deepFinancialAnalysis.balance_sheet_strength.interest_coverage.adequacy_score === 'fair' ? 'text-yellow-600' : 
                            'text-red-600'
                          }`}>
                            {deepFinancialAnalysis.balance_sheet_strength.interest_coverage.adequacy_score}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Liquidity Analysis */}
                  {deepFinancialAnalysis.balance_sheet_strength.liquidity && (
                    <div className="bg-cyan-50 border border-cyan-200 rounded-lg p-4">
                      <h5 className="font-medium text-cyan-900 mb-2 flex items-center">
                        <span className="text-lg mr-2">💧</span>
                        Liquidity Analysis
                      </h5>
                      <div className="space-y-1 text-sm">
                        <div className="flex justify-between">
                          <span className="text-cyan-700">Current Ratio:</span>
                          <span className="font-medium">{deepFinancialAnalysis.balance_sheet_strength.liquidity.current_ratio?.latest?.toFixed(2) || 'N/A'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-cyan-700">Quick Ratio:</span>
                          <span className="font-medium">{deepFinancialAnalysis.balance_sheet_strength.liquidity.quick_ratio?.latest?.toFixed(2) || 'N/A'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-cyan-700">Cash Ratio:</span>
                          <span className="font-medium">{deepFinancialAnalysis.balance_sheet_strength.liquidity.cash_ratio?.latest?.toFixed(2) || 'N/A'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-cyan-700">Liquidity Strength:</span>
                          <span className={`font-medium ${
                            deepFinancialAnalysis.balance_sheet_strength.liquidity.current_ratio?.strength_score === 'excellent' ? 'text-green-600' : 
                            deepFinancialAnalysis.balance_sheet_strength.liquidity.current_ratio?.strength_score === 'good' ? 'text-blue-600' : 
                            deepFinancialAnalysis.balance_sheet_strength.liquidity.current_ratio?.strength_score === 'fair' ? 'text-yellow-600' : 
                            'text-red-600'
                          }`}>
                            {deepFinancialAnalysis.balance_sheet_strength.liquidity.current_ratio?.strength_score}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Cash Position */}
                  {deepFinancialAnalysis.balance_sheet_strength.cash_position && (
                    <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
                      <h5 className="font-medium text-emerald-900 mb-2 flex items-center">
                        <span className="text-lg mr-2">💵</span>
                        Cash Position Analysis
                      </h5>
                      <div className="space-y-1 text-sm">
                        <div className="flex justify-between">
                          <span className="text-emerald-700">Cash/Asset Ratio:</span>
                          <span className="font-medium">{(deepFinancialAnalysis.balance_sheet_strength.cash_position.cash_asset_ratio?.latest * 100)?.toFixed(1) || 'N/A'}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-emerald-700">Cash/Revenue Ratio:</span>
                          <span className="font-medium">{(deepFinancialAnalysis.balance_sheet_strength.cash_position.cash_revenue_ratio?.latest * 100)?.toFixed(1) || 'N/A'}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-emerald-700">Cash Trend:</span>
                          <span className={`font-medium ${
                            deepFinancialAnalysis.balance_sheet_strength.cash_position.cash_trend === 'increasing' ? 'text-green-600' : 
                            deepFinancialAnalysis.balance_sheet_strength.cash_position.cash_trend === 'stable' ? 'text-blue-600' : 
                            'text-red-600'
                          }`}>
                            {deepFinancialAnalysis.balance_sheet_strength.cash_position.cash_trend}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-emerald-700">Adequacy:</span>
                          <span className={`font-medium ${
                            deepFinancialAnalysis.balance_sheet_strength.cash_position.adequacy_score === 'excellent' ? 'text-green-600' : 
                            deepFinancialAnalysis.balance_sheet_strength.cash_position.adequacy_score === 'good' ? 'text-blue-600' : 
                            deepFinancialAnalysis.balance_sheet_strength.cash_position.adequacy_score === 'fair' ? 'text-yellow-600' : 
                            'text-red-600'
                          }`}>
                            {deepFinancialAnalysis.balance_sheet_strength.cash_position.adequacy_score}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          </div>
      )}

      {/* DCF Sensitivity Analysis */}
      {dcfValuation?.sensitivity_analysis && (
        <div className="card p-6">
          <h2 className="text-xl font-bold text-slate-900 mb-6">DCF Sensitivity Analysis</h2>
          
          {/* Terminal Value Methods Comparison */}
          {dcfValuation.sensitivity_analysis.terminal_value_methods && (
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-slate-800 mb-4 flex items-center">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                </svg>
                Terminal Value Methods Comparison
              </h3>
              <div className="grid md:grid-cols-3 gap-4">
                {Object.entries(dcfValuation.sensitivity_analysis.terminal_value_methods).map(([method, value]) => {
                  const methodInfo = {
                    'gordon_growth': {
                      name: 'Gordon Growth Model',
                      description: 'Perpetuity with constant growth',
                      icon: '📈',
                      color: 'blue'
                    },
                    'exit_multiple': {
                      name: 'Exit Multiple Method',
                      description: 'FCF multiple at exit',
                      icon: '🔢',
                      color: 'green'
                    },
                    'perpetuity_growth': {
                      name: 'Perpetuity Growth',
                      description: 'No growth perpetuity',
                      icon: '⚖️',
                      color: 'purple'
                    }
                  };
                  
                  const info = methodInfo[method as keyof typeof methodInfo] || {
                    name: method.replace('_', ' '),
                    description: 'Alternative valuation method',
                    icon: '💰',
                    color: 'gray'
                  };
                  
                  const colorClasses = {
                    'blue': 'bg-blue-50 border-blue-200 text-blue-900',
                    'green': 'bg-green-50 border-green-200 text-green-900',
                    'purple': 'bg-purple-50 border-purple-200 text-purple-900',
                    'gray': 'bg-gray-50 border-gray-200 text-gray-900'
                  };
                  
                  return (
                    <div key={method} className={`${colorClasses[info.color as keyof typeof colorClasses]} border rounded-lg p-4 text-center transition-all hover:shadow-md hover:scale-105`}>
                      <div className="text-2xl mb-2">{info.icon}</div>
                      <div className="text-sm font-semibold mb-1">{info.name}</div>
                      <div className="text-xs text-gray-600 mb-3">{info.description}</div>
                      <div className="text-lg font-bold">
                        {formatAmountByCurrency(value as number, ticker)}
              </div>
                    </div>
                  );
                })}
              </div>
              
              {/* Method Comparison Summary */}
              <div className="mt-4 p-3 bg-slate-100 border border-slate-300 rounded-lg">
                <div className="flex items-start">
                  <svg className="w-4 h-4 mr-2 mt-0.5 text-slate-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                  </svg>
                  <p className="text-xs text-slate-700">
                    <strong>Method Range:</strong> Different terminal value methods show a range of {Math.min(...Object.values(dcfValuation.sensitivity_analysis.terminal_value_methods).map(v => Number(v))).toFixed(0)} to {Math.max(...Object.values(dcfValuation.sensitivity_analysis.terminal_value_methods).map(v => Number(v))).toFixed(0)}, 
                    indicating moderate sensitivity to terminal value assumptions.
                  </p>
                </div>
              </div>
            </div>
          )}

          {/* Sensitivity Summary */}
          {dcfValuation.sensitivity_analysis.sensitivity_summary && (
            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-6">
              <h3 className="text-lg font-semibold text-blue-900 mb-4 flex items-center">
                <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
                </svg>
                Sensitivity Impact Analysis
              </h3>
              <div className="grid md:grid-cols-2 gap-4">
                {Object.entries(dcfValuation.sensitivity_analysis.sensitivity_summary).map(([key, description]) => {
                  const descriptionStr = String(description);
                  const impactLevel = descriptionStr.includes('High') ? 'high' : 
                                    descriptionStr.includes('Very High') ? 'very-high' : 
                                    descriptionStr.includes('Moderate') ? 'moderate' : 'low';
                  
                  const impactColors = {
                    'very-high': 'text-red-700 bg-red-100 border-red-200',
                    'high': 'text-orange-700 bg-orange-100 border-orange-200',
                    'moderate': 'text-yellow-700 bg-yellow-100 border-yellow-200',
                    'low': 'text-green-700 bg-green-100 border-green-200'
                  };
                  
                  const impactIcons = {
                    'very-high': '🔴',
                    'high': '🟠',
                    'moderate': '🟡',
                    'low': '🟢'
                  };
                  
                  return (
                    <div key={key} className={`p-4 rounded-lg border ${impactColors[impactLevel]} transition-all hover:shadow-md`}>
                      <div className="flex items-start justify-between mb-2">
                        <h4 className="font-semibold text-sm uppercase tracking-wide">
                          {key.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                        </h4>
                        <span className="text-lg">{impactIcons[impactLevel]}</span>
                      </div>
                      <p className="text-sm leading-relaxed">{descriptionStr}</p>
                    </div>
                  );
                })}
              </div>
              
              {/* Additional Context */}
              <div className="mt-4 p-3 bg-blue-100 border border-blue-300 rounded-lg">
                <div className="flex items-start">
                  <svg className="w-4 h-4 mr-2 mt-0.5 text-blue-600 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-xs text-blue-800">
                    <strong>Key Insight:</strong> Terminal growth assumptions have the highest impact on valuation. 
                    Small changes in long-term growth rates can significantly affect intrinsic value calculations.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Enhanced Relative Valuation Analysis */}
      {report?.peer_analysis?.details && (
        <div className="card p-6">
          <h2 className="text-xl font-bold text-slate-900 mb-6 flex items-center">
            <svg className="w-6 h-6 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
            </svg>
            Relative Valuation Analysis
          </h2>
          
          {/* Valuation Score and Position */}
          <div className="grid md:grid-cols-3 gap-4 mb-6">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-center">
              <div className="text-xs text-blue-600 uppercase font-medium mb-1">Valuation Score</div>
              <div className="text-2xl font-bold text-blue-900">
                {report.peer_analysis.details.valuation_score?.toFixed(1) || 'N/A'}
              </div>
              <div className="text-xs text-blue-600">out of 100</div>
            </div>
            
            <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-center">
              <div className="text-xs text-green-600 uppercase font-medium mb-1">Relative Position</div>
              <div className="text-lg font-bold text-green-900">
                {report.peer_analysis.details.relative_position || 'N/A'}
              </div>
            </div>
            
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 text-center">
              <div className="text-xs text-purple-600 uppercase font-medium mb-1">Peer Count</div>
              <div className="text-2xl font-bold text-purple-900">
                {report.peer_analysis.details.peer_count || 0}
              </div>
              <div className="text-xs text-purple-600">comparable companies</div>
            </div>
          </div>

          {/* Key Valuation Metrics */}
          {report.peer_analysis.details.valuation_metrics && (
            <div className="mb-6">
              <h3 className="text-lg font-semibold text-slate-800 mb-4">Key Valuation Metrics vs Peers</h3>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(report.peer_analysis.details.valuation_metrics).map(([metric, data]: [string, any]) => {
                  const metricNames: { [key: string]: string } = {
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
                  };
                  
                  const metricName = metricNames[metric] || metric.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase());
                  const percentile = data.percentile_rank;
                  const position = data.relative_position;
                  
                  // Determine color based on position
                  const getColorClasses = (pos: string) => {
                    if (pos === 'Cheap' || pos === 'Low Risk') return 'bg-green-50 border-green-200 text-green-900';
                    if (pos === 'Expensive' || pos === 'High Risk') return 'bg-red-50 border-red-200 text-red-900';
                    return 'bg-yellow-50 border-yellow-200 text-yellow-900';
                  };
                  
                  return (
                    <div key={metric} className={`${getColorClasses(position)} border rounded-lg p-3`}>
                      <div className="flex justify-between items-center mb-2">
                        <span className="text-sm font-semibold">{metricName}</span>
                        <span className="text-xs bg-white px-2 py-1 rounded-full">
                          {percentile}th percentile
                        </span>
                      </div>
                      <div className="text-lg font-bold mb-1">
                        {data.target_value?.toFixed(2) || 'N/A'}
                      </div>
                      <div className="text-xs opacity-75">
                        Peer avg: {data.peer_average?.toFixed(2) || 'N/A'} | {position}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Strengths and Weaknesses */}
          <div className="grid md:grid-cols-2 gap-6">
            {/* Strengths */}
            {report.peer_analysis.details.strengths && report.peer_analysis.details.strengths.length > 0 && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-green-900 mb-3 flex items-center">
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  Valuation Strengths
                </h3>
                <ul className="space-y-2">
                  {report.peer_analysis.details.strengths.slice(0, 5).map((strength: string, index: number) => (
                    <li key={index} className="flex items-start text-sm text-green-800">
                      <span className="mr-2 text-green-600">✓</span>
                      <span>{strength}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

            {/* Weaknesses */}
            {report.peer_analysis.details.weaknesses && report.peer_analysis.details.weaknesses.length > 0 && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                <h3 className="text-lg font-semibold text-red-900 mb-3 flex items-center">
                  <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16.5c-.77.833.192 2.5 1.732 2.5z" />
                  </svg>
                  Valuation Concerns
                </h3>
                <ul className="space-y-2">
                  {report.peer_analysis.details.weaknesses.slice(0, 5).map((weakness: string, index: number) => (
                    <li key={index} className="flex items-start text-sm text-red-800">
                      <span className="mr-2 text-red-600">⚠</span>
                      <span>{weakness}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          {/* Peer Summary */}
          {report.peer_analysis.details.summary && (
            <div className="mt-6 p-4 bg-slate-100 border border-slate-300 rounded-lg">
              <h3 className="text-lg font-semibold text-slate-800 mb-2">Peer Comparison Summary</h3>
              <p className="text-sm text-slate-700 leading-relaxed">
                {report.peer_analysis.details.summary}
              </p>
            </div>
          )}
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
              <TechnicalChart 
                labels={labels} 
                closes={closes} 
                indicators={indicators}
                signals={signals}
              />
            </div>
            
            {/* Technical Indicators */}
            <div className="space-y-4">
              {indicators && (
                <div className="grid grid-cols-1 xs:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
                  <div className="bg-slate-50 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">RSI (14)</div>
                    <div className={`text-lg font-semibold ${
                      indicators.rsi14 > 70 ? 'text-red-600' : 
                      indicators.rsi14 < 30 ? 'text-green-600' : 'text-slate-900'
                    }`}>
                      {indicators.rsi14?.toFixed(1) || '—'}
                    </div>
                    <div className="text-xs text-slate-500">
                      {indicators.rsi14 > 70 ? 'Overbought' : 
                       indicators.rsi14 < 30 ? 'Oversold' : 'Neutral'}
                    </div>
                  </div>
                  
                  <div className="bg-slate-50 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">MACD</div>
                    <div className={`text-lg font-semibold ${
                      indicators.macd?.hist > 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {indicators.macd?.macd?.toFixed(2) || '—'}
                    </div>
                    <div className="text-xs text-slate-500">
                      Hist: {indicators.macd?.hist?.toFixed(2) || '—'}
                    </div>
                  </div>
                  
                  <div className="bg-slate-50 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">SMA 20</div>
                    <div className="text-lg font-semibold text-slate-900">
                      {formatAmountByCurrency(indicators.sma20, ticker)}
                    </div>
                    <div className="text-xs text-slate-500">
                      {indicators.last_close > indicators.sma20 ? 'Above' : 'Below'}
                    </div>
                  </div>
                  
                  <div className="bg-slate-50 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">SMA 50</div>
                    <div className="text-lg font-semibold text-slate-900">
                      {formatAmountByCurrency(indicators.sma50, ticker)}
                    </div>
                    <div className="text-xs text-slate-500">
                      {indicators.last_close > indicators.sma50 ? 'Above' : 'Below'}
                    </div>
                  </div>
                  
                  <div className="bg-slate-50 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">SMA 200</div>
                    <div className="text-lg font-semibold text-slate-900">
                      {formatAmountByCurrency(indicators.sma200, ticker)}
                    </div>
                    <div className="text-xs text-slate-500">
                      {indicators.last_close > indicators.sma200 ? 'Above' : 'Below'}
                    </div>
                  </div>
                  
                  <div className="bg-slate-50 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">Bollinger Bands</div>
                    <div className="text-lg font-semibold text-slate-900">
                      {formatAmountByCurrency(indicators.bollinger?.upper, ticker)}
                    </div>
                    <div className="text-xs text-slate-500">
                      Upper Band
                    </div>
                  </div>
                  
                  <div className="bg-slate-50 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">Momentum (20d)</div>
                    <div className={`text-lg font-semibold ${
                      indicators.momentum20d > 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {(indicators.momentum20d * 100)?.toFixed(2) || '—'}%
                    </div>
                    <div className="text-xs text-slate-500">
                      {indicators.momentum20d > 0 ? 'Positive' : 'Negative'}
            </div>
          </div>
                  
                  <div className="bg-slate-50 rounded-lg p-3">
                    <div className="text-xs text-slate-500 mb-1">Current Price</div>
                    <div className="text-lg font-semibold text-slate-900">
                      {formatAmountByCurrency(indicators.last_close, ticker)}
                    </div>
                    <div className="text-xs text-slate-500">
                      Latest Close
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
          <div className="space-y-4">
            {report?.news_sentiment?.summary && (
              <div className="space-y-3">
                {parseNewsSentiment(report.news_sentiment.summary)}
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
      {(filings || earningsCall || strategicConviction || sectorRotation || insiderTracking) && (
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
              
              {earningsCall.status === 'success' ? (
                <div className="space-y-4">
                  {/* Analysis Summary */}
                  <div className="grid grid-cols-2 gap-4">
            <div>
                      <div className="text-xs text-slate-500 uppercase font-medium mb-1">Calls Analyzed</div>
                      <div className="text-lg font-semibold text-slate-900">{earningsCall.total_calls_analyzed || 0}</div>
            </div>
            <div>
                      <div className="text-xs text-slate-500 uppercase font-medium mb-1">Confidence</div>
                      <div className="text-lg font-semibold text-slate-900">
                        {earningsCall.confidence_score ? `${(earningsCall.confidence_score * 100).toFixed(0)}%` : '—'}
            </div>
          </div>
      </div>

                  {/* Management Sentiment */}
                  {earningsCall.management_sentiment && (
            <div>
                      <div className="text-sm font-medium text-slate-700 mb-2">Management Sentiment</div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <div className="text-xs text-slate-500">Overall Sentiment</div>
                          <div className={`text-sm font-medium ${
                            earningsCall.management_sentiment.overall_sentiment > 0.1 ? 'text-green-600' : 
                            earningsCall.management_sentiment.overall_sentiment < -0.1 ? 'text-red-600' : 'text-slate-600'
                          }`}>
                            {earningsCall.management_sentiment.overall_sentiment > 0.1 ? 'Positive' : 
                             earningsCall.management_sentiment.overall_sentiment < -0.1 ? 'Negative' : 'Neutral'}
            </div>
            </div>
              <div>
                          <div className="text-xs text-slate-500">Defensiveness</div>
                          <div className={`text-sm font-medium ${
                            earningsCall.management_sentiment.defensiveness_score > 0.3 ? 'text-red-600' : 
                            earningsCall.management_sentiment.defensiveness_score > 0.1 ? 'text-yellow-600' : 'text-green-600'
                          }`}>
                            {earningsCall.management_sentiment.defensiveness_score > 0.3 ? 'High' : 
                             earningsCall.management_sentiment.defensiveness_score > 0.1 ? 'Medium' : 'Low'}
              </div>
              </div>
          </div>
      </div>
                  )}

                  {/* Key Insights */}
                  {earningsCall.key_insights && (
            <div>
                      <div className="text-sm font-medium text-slate-700 mb-2">Key Insights</div>
                      <div className="space-y-2">
                        {earningsCall.key_insights.topics_discussed && earningsCall.key_insights.topics_discussed.length > 0 && (
            <div>
                            <div className="text-xs text-slate-500">Topics Discussed</div>
                            <div className="text-sm text-slate-600">
                              {earningsCall.key_insights.topics_discussed.slice(0, 3).join(', ')}
                              {earningsCall.key_insights.topics_discussed.length > 3 && '...'}
            </div>
              </div>
            )}
                        {earningsCall.key_insights.concerns_raised && earningsCall.key_insights.concerns_raised.length > 0 && (
            <div>
                            <div className="text-xs text-slate-500">Concerns Raised</div>
                            <div className="text-sm text-slate-600">
                              {earningsCall.key_insights.concerns_raised.slice(0, 2).join(', ')}
                              {earningsCall.key_insights.concerns_raised.length > 2 && '...'}
            </div>
              </div>
            )}
          </div>
                    </div>
                  )}

                  {/* Summary Insights */}
                  {earningsCall.summary_insights && (
              <div>
                      <div className="text-sm font-medium text-slate-700 mb-2">Summary</div>
                      <div className="text-sm text-slate-600">
                        {earningsCall.summary_insights.length > 150 ? 
                          `${earningsCall.summary_insights.substring(0, 150)}...` : 
                          earningsCall.summary_insights}
            </div>
              </div>
            )}
          </div>
        ) : (
                <div className="text-sm text-slate-500">
                  {earningsCall.summary_insights || (earningsCall.status === 'no_calls_found' ? 'No recent earnings calls found' : 'Analysis unavailable')}
                </div>
        )}
      </div>
          )}

          {/* Strategic Conviction */}
          {strategicConviction && (
      <div className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-semibold">Strategic Conviction</h3>
                <Icons.ChartBar className="w-5 h-5 text-slate-500" />
        </div>
              
              {strategicConviction.details ? (
                <div className="space-y-4">
                  {/* Overall Score */}
                  <div className="grid grid-cols-2 gap-4">
            <div>
                      <div className="text-xs text-slate-500 uppercase font-medium mb-1">Conviction Score</div>
                      <div className="text-lg font-semibold text-slate-900">
                        {strategicConviction.details.overall_conviction_score ? `${strategicConviction.details.overall_conviction_score.toFixed(1)}/100` : '—'}
            </div>
            </div>
            <div>
                      <div className="text-xs text-slate-500 uppercase font-medium mb-1">Recommendation</div>
                      <div className="text-lg font-semibold text-slate-900">
                        {strategicConviction.details.strategic_recommendation || strategicConviction.summary || '—'}
            </div>
          </div>
      </div>

                  {/* Business Quality */}
                  {strategicConviction.details.business_quality && (
            <div>
                      <div className="text-sm font-medium text-slate-700 mb-2">Business Quality</div>
                      <div className="grid grid-cols-2 gap-3">
              <div>
                          <div className="text-xs text-slate-500">Score</div>
                          <div className="text-sm font-medium text-slate-900">
                            {strategicConviction.details.business_quality.score ? `${strategicConviction.details.business_quality.score.toFixed(1)}/100` : '—'}
              </div>
            </div>
            <div>
                          <div className="text-xs text-slate-500">Market Position</div>
                          <div className="text-sm font-medium text-slate-900">
                            {strategicConviction.details.business_quality.market_position?.description || '—'}
            </div>
          </div>
      </div>

                      {/* Competitive Moats */}
                      {strategicConviction.details.business_quality.competitive_moats && strategicConviction.details.business_quality.competitive_moats.length > 0 && (
                        <div className="mt-3">
                          <div className="text-xs text-slate-500 mb-1">Key Competitive Advantages</div>
                          <div className="space-y-1">
                            {strategicConviction.details.business_quality.competitive_moats.slice(0, 2).map((moat: any, index: number) => (
                              <div key={index} className="text-sm text-slate-700">
                                • {moat.type}: {moat.evidence?.[0] || 'Strong competitive position'}
        </div>
                            ))}
            </div>
                        </div>
        )}
      </div>
                  )}

                  {/* Growth Runway */}
                  {strategicConviction.details.growth_runway && (
              <div>
                      <div className="text-sm font-medium text-slate-700 mb-2">Growth Runway</div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <div className="text-xs text-slate-500">TAM Growth</div>
                          <div className="text-sm font-medium text-slate-900">
                            {strategicConviction.details.growth_runway.tam_analysis?.estimated_cagr ? `${strategicConviction.details.growth_runway.tam_analysis.estimated_cagr}% CAGR` : '—'}
        </div>
              </div>
              <div>
                          <div className="text-xs text-slate-500">Runway</div>
                          <div className="text-sm font-medium text-slate-900">
                            {strategicConviction.details.growth_runway.growth_runway_years || '—'}
              </div>
                        </div>
            </div>
            </div>
                  )}

                  {/* Key Strengths */}
                  {strategicConviction.details.business_quality?.key_strengths && strategicConviction.details.business_quality.key_strengths.length > 0 && (
              <div>
                      <div className="text-xs text-slate-500 mb-1">Key Strengths</div>
                      <div className="space-y-1">
                        {strategicConviction.details.business_quality.key_strengths.slice(0, 3).map((strength: string, index: number) => (
                          <div key={index} className="text-sm text-green-700">• {strength}</div>
                        ))}
              </div>
            </div>
        )}

                  {/* Phase 6: Strategic & Business Analysis */}
                  <div className="border-t pt-4">
                    <h4 className="text-md font-semibold text-slate-800 mb-3 flex items-center">
                      <Icons.TrendingUp className="w-4 h-4 mr-2 text-blue-600" />
                      Strategic & Business Analysis
                    </h4>
                    
                    {/* Growth Drivers */}
                    {strategicConviction.details.growth_runway?.growth_drivers && (
                      <div className="mb-4">
                        <div className="text-sm font-medium text-slate-700 mb-2">Growth Drivers</div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {strategicConviction.details.growth_runway.growth_drivers.drivers?.slice(0, 4).map((driver: any, index: number) => (
                            <div key={index} className="bg-blue-50 p-3 rounded-lg">
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-sm font-medium text-blue-900">{driver.type}</span>
                                <span className="text-xs text-blue-600 font-medium">{driver.score}/100</span>
                              </div>
                              <div className="text-xs text-blue-700">{driver.description}</div>
                              {driver.drivers && driver.drivers.length > 0 && (
                                <div className="mt-1">
                                  {driver.drivers.slice(0, 2).map((d: string, i: number) => (
                                    <div key={i} className="text-xs text-blue-600">• {d}</div>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Segment Performance */}
                    {strategicConviction.details.growth_runway?.segment_performance && (
                      <div className="mb-4">
                        <div className="text-sm font-medium text-slate-700 mb-2">Segment Performance</div>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                          {strategicConviction.details.growth_runway.segment_performance.segments?.slice(0, 4).map((segment: any, index: number) => (
                            <div key={index} className="bg-green-50 p-3 rounded-lg">
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-sm font-medium text-green-900">{segment.name}</span>
                                <span className="text-xs text-green-600 font-medium">{segment.score}/100</span>
                              </div>
                              <div className="text-xs text-green-700 mb-1">{segment.description}</div>
                              <div className="text-xs text-green-600 font-medium">Growth: {segment.growth_rate}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Competitive Analysis */}
                    {strategicConviction.details.business_quality?.competitive_analysis && (
                      <div className="mb-4">
                        <div className="text-sm font-medium text-slate-700 mb-2">Competitive Landscape</div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          {/* Positioning */}
                          <div className="bg-purple-50 p-3 rounded-lg">
                            <div className="text-xs font-medium text-purple-900 mb-1">Market Position</div>
                            <div className="text-sm text-purple-800 font-medium">
                              {strategicConviction.details.business_quality.competitive_analysis.positioning?.position || '—'}
                            </div>
                            <div className="text-xs text-purple-600">
                              {strategicConviction.details.business_quality.competitive_analysis.positioning?.score || '—'}/100
                            </div>
                          </div>
                          
                          {/* Advantages */}
                          <div className="bg-orange-50 p-3 rounded-lg">
                            <div className="text-xs font-medium text-orange-900 mb-1">Competitive Advantages</div>
                            <div className="text-sm text-orange-800 font-medium">
                              {strategicConviction.details.business_quality.competitive_analysis.advantages?.advantage_strength || '—'}
                            </div>
                            <div className="text-xs text-orange-600">
                              {strategicConviction.details.business_quality.competitive_analysis.advantages?.score || '—'}/100
                            </div>
                          </div>
                          
                          {/* Threats */}
                          <div className="bg-red-50 p-3 rounded-lg">
                            <div className="text-xs font-medium text-red-900 mb-1">Competitive Threats</div>
                            <div className="text-sm text-red-800 font-medium">
                              {strategicConviction.details.business_quality.competitive_analysis.threats?.risk_level || '—'}
                            </div>
                            <div className="text-xs text-red-600">
                              Risk: {strategicConviction.details.business_quality.competitive_analysis.threats?.risk_score || '—'}/100
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Industry Outlook */}
                    {strategicConviction.details.business_quality?.industry_outlook && (
                      <div className="mb-4">
                        <div className="text-sm font-medium text-slate-700 mb-2">Industry Outlook</div>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                          {/* Growth Outlook */}
                          <div className="bg-indigo-50 p-3 rounded-lg">
                            <div className="text-xs font-medium text-indigo-900 mb-1">Growth Outlook</div>
                            <div className="text-sm text-indigo-800 font-medium">
                              {strategicConviction.details.business_quality.industry_outlook.growth_outlook?.outlook || '—'}
                            </div>
                            <div className="text-xs text-indigo-600">
                              {strategicConviction.details.business_quality.industry_outlook.growth_outlook?.growth_rate || '—'}% CAGR
                            </div>
                          </div>
                          
                          {/* Trends */}
                          <div className="bg-teal-50 p-3 rounded-lg">
                            <div className="text-xs font-medium text-teal-900 mb-1">Key Trends</div>
                            <div className="text-sm text-teal-800 font-medium">
                              {strategicConviction.details.business_quality.industry_outlook.trends?.trend_strength || '—'}
                            </div>
                            <div className="text-xs text-teal-600">
                              {strategicConviction.details.business_quality.industry_outlook.trends?.score || '—'}/100
                            </div>
                          </div>
                          
                          {/* Overall Outlook */}
                          <div className="bg-emerald-50 p-3 rounded-lg">
                            <div className="text-xs font-medium text-emerald-900 mb-1">Overall Outlook</div>
                            <div className="text-sm text-emerald-800 font-medium">
                              {strategicConviction.details.business_quality.industry_outlook.overall_outlook || '—'}
                            </div>
                            <div className="text-xs text-emerald-600">
                              {strategicConviction.details.business_quality.industry_outlook.score || '—'}/100
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
            </div>
          </div>
        ) : (
                <div className="text-sm text-slate-600">
                  Strategic analysis available
        </div>
        )}
      </div>
          )}

          {/* Sector Rotation Analysis */}
          {sectorRotation && (
      <div className="card p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-semibold">Sector Rotation Analysis</h3>
                <Icons.TrendingUp className="w-5 h-5 text-slate-500" />
        </div>
              
              {sectorRotation.details ? (
                <div className="space-y-4">
                  {/* Overall Score */}
                  <div className="grid grid-cols-2 gap-4">
            <div>
                      <div className="text-xs text-slate-500 uppercase font-medium mb-1">Rotation Score</div>
                      <div className="text-lg font-semibold text-slate-900">
                        {sectorRotation.details.overall_score ? `${sectorRotation.details.overall_score.toFixed(1)}/100` : '—'}
                      </div>
            </div>
            <div>
                      <div className="text-xs text-slate-500 uppercase font-medium mb-1">Recommendation</div>
                      <div className="text-lg font-semibold text-slate-900">
                        {sectorRotation.details.recommendation || sectorRotation.summary || '—'}
            </div>
                    </div>
                  </div>

                  {/* Sector Performance */}
                  {sectorRotation.details.sector_performance && (
            <div>
                      <div className="text-sm font-medium text-slate-700 mb-2">Sector Performance</div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <div className="text-xs text-slate-500">Current Phase</div>
                          <div className="text-sm font-medium text-slate-900">
                            {sectorRotation.details.sector_performance.current_phase || '—'}
                          </div>
            </div>
            <div>
                          <div className="text-xs text-slate-500">Momentum</div>
                          <div className={`text-sm font-medium ${
                            sectorRotation.details.sector_performance.momentum_score > 0.6 ? 'text-green-600' : 
                            sectorRotation.details.sector_performance.momentum_score > 0.4 ? 'text-yellow-600' : 'text-red-600'
                          }`}>
                            {sectorRotation.details.sector_performance.momentum_score > 0.6 ? 'Strong' : 
                             sectorRotation.details.sector_performance.momentum_score > 0.4 ? 'Moderate' : 'Weak'}
            </div>
          </div>
      </div>
        </div>
                    )}

                  {/* Rotation Signals */}
                  {sectorRotation.details.rotation_signals && (
                    <div>
                      <div className="text-sm font-medium text-slate-700 mb-2">Rotation Signals</div>
                      <div className="space-y-2">
                        {sectorRotation.details.rotation_signals.slice(0, 3).map((signal: any, index: number) => (
                          <div key={index} className="text-sm text-slate-700">
                            • {signal.signal_type}: {signal.description || 'Rotation signal detected'}
            </div>
                        ))}
            </div>
                    </div>
                  )}

                  {/* Key Insights */}
                  {sectorRotation.details.key_insights && (
                    <div>
                      <div className="text-sm font-medium text-slate-700 mb-2">Key Insights</div>
                  <div className="space-y-1">
                        {Array.isArray(sectorRotation.details.key_insights) ? (
                          sectorRotation.details.key_insights.map((insight: string, index: number) => (
                            <div key={index} className="text-sm text-slate-600">
                              • {insight}
                        </div>
                          ))
                        ) : (
                          <div className="text-sm text-slate-600">
                            {sectorRotation.details.key_insights.length > 150 ? 
                              `${sectorRotation.details.key_insights.substring(0, 150)}...` : 
                              sectorRotation.details.key_insights}
                      </div>
                        )}
                      </div>
                      </div>
                    )}
                  </div>
              ) : (
                <div className="text-sm text-slate-600">
                  Sector rotation analysis available
                      </div>
                    )}
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