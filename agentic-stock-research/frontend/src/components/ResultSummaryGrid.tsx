import { Icons } from './icons'
import { TechnicalChart } from './TechnicalChart'

function currencySymbolForTicker(ticker?: string): string {
  if (!ticker) return '$'
  const t = ticker.toUpperCase()
  if (t.endsWith('.NS') || t.endsWith('.BO')) return '₹'
  return '$'
}

function formatAmountByCurrency(value?: number, ticker?: string): string {
  if (value === undefined || value === null || isNaN(Number(value))) return '—'
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

// Stars component not currently used; kept for future nuanced star rendering

function formatPct(value?: number, digits: number = 1): string {
  if (value === undefined || value === null || isNaN(Number(value))) return '—'
  return `${(Number(value) * 100).toFixed(digits)}%`
}

function formatNumber(value?: number, digits: number = 2): string {
  if (value === undefined || value === null || isNaN(Number(value))) return '—'
  return Number(value).toFixed(digits)
}

export function ResultSummaryGrid({ report }: { report: any }) {
  const labels: string[] = report?.technicals?.details?.labels ?? []
  const closes: number[] = report?.technicals?.details?.closes ?? []
  const ticker: string | undefined = report?.ticker
  const signals = report?.technicals?.details?.signals
  const indicators = report?.technicals?.details?.indicators
  const comp = report?.comprehensive_fundamentals
  // Build a client-side fallback executive summary if backend is missing it
  const execSummary: string | undefined = (() => {
    if (report?.executive_summary) return report.executive_summary
    try {
      const action = report?.decision?.action || 'Hold'
      const score = Number(report?.decision?.rating || 0)
      const scorePct = Math.round((score / 5) * 100)
      const iv = comp?.intrinsic_value
      const mos = comp?.margin_of_safety
      const positives: string[] = report?.decision?.top_reasons_for || []
      const negatives: string[] = report?.decision?.top_reasons_against || []
      const parts: string[] = []
      parts.push(`${action}: ${scorePct}`)
      if (typeof iv === 'number') parts.push(`IV ${formatAmountByCurrency(iv, ticker)}`)
      if (typeof mos === 'number') parts.push(`MoS ${(mos * 100).toFixed(0)}%`)
      if (positives.length) parts.push(`Key: ${positives.slice(0, 2).join(', ')}`)
      if (negatives.length) parts.push(`Risks: ${negatives.slice(0, 2).join(', ')}`)
      return parts.join('; ')
    } catch {
      return undefined
    }
  })()
  return (
    <div className="grid md:grid-cols-2 gap-6">
      <div className="card p-5">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-medium">Recommendation & Rating</h3>
          <Icons.Star className="w-5 h-5 text-slate-500" aria-hidden />
        </div>
        {execSummary && (
          <div className="mb-3 text-sm text-slate-800 bg-slate-50 border rounded p-3">
            <strong>Executive Summary:</strong> {execSummary}
          </div>
        )}
        <div className="space-y-3">
          {/* Clean single-line recommendation format */}
          <div className="text-lg font-medium text-slate-900">
            {report?.decision?.action} — {report?.decision?.rating}/5 {(() => {
              const rating = report?.decision?.rating || 0;
              const fullStars = Math.floor(rating);
              const hasHalf = (rating - fullStars) >= 0.5;
              let stars = "★".repeat(fullStars);
              if (hasHalf && fullStars < 5) stars += "☆";
              stars += "☆".repeat(5 - stars.length);
              return stars;
            })()}
          </div>
          
          {/* Professional rationale */}
          <div className="text-sm text-slate-700 leading-relaxed">
            <strong className="text-slate-900">Rationale:</strong> {(() => {
              // Generate professional rationale from available data
              const action = report?.decision?.action || "Hold";
              const positives = report?.decision?.top_reasons_for || [];
              const negatives = report?.decision?.top_reasons_against || [];
              
              if (action === "Hold") {
                return `The stock demonstrates stable performance with balanced risks and opportunities${positives.length > 0 ? `, supported by ${positives[0].toLowerCase()}` : ''}${negatives.length > 0 ? ` while monitoring ${negatives[0].toLowerCase()}` : ''}. No strong short-term catalysts identified.`;
              } else if (action === "Buy" || action === "Strong Buy") {
                return `Strong fundamentals and positive market dynamics support upward potential${positives.length > 0 ? `, particularly ${positives[0].toLowerCase()}` : ''}. Investment thesis remains compelling despite ${negatives.length > 0 ? negatives[0].toLowerCase() : 'market volatility'}.`;
              } else {
                return `Current market conditions and risk factors suggest caution${negatives.length > 0 ? `, primarily due to ${negatives[0].toLowerCase()}` : ''}. Consider defensive positioning until outlook improves.`;
              }
            })()}
          </div>
        </div>
      </div>

      {comp && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-lg font-medium">Comprehensive Fundamentals (DCF & Scoring)</h3>
            <Icons.Fundamentals className="w-5 h-5 text-slate-500" aria-hidden />
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-slate-500">Overall Score</div>
              <div className="font-medium">{formatNumber(comp.overall_score, 1)} / 100</div>
            </div>
            <div>
              <div className="text-slate-500">Grade</div>
              <div className="font-medium">{comp.overall_grade ?? '—'}</div>
            </div>
            <div>
              <div className="text-slate-500">Intrinsic Value (DCF)</div>
              <div className="font-medium">{formatAmountByCurrency(comp.intrinsic_value, ticker)}</div>
            </div>
            <div>
              <div className="text-slate-500">Margin of Safety</div>
              <div className="font-medium">{formatPct(comp.margin_of_safety, 1)}</div>
            </div>
            <div>
            <div className="text-slate-500">Upside Potential</div>
              <div className="font-medium">{(() => {
                const v = typeof comp.upside_potential === 'number' ? comp.upside_potential : (typeof comp.margin_of_safety === 'number' ? comp.margin_of_safety : undefined)
                return formatPct(v, 1)
              })()}</div>
            </div>
            <div>
              <div className="text-slate-500">Buy Zone</div>
              <div className="font-medium">{`${formatAmountByCurrency(comp.entry_zone_low, ticker)} – ${formatAmountByCurrency(comp.entry_zone_high, ticker)}`}</div>
            </div>
            <div>
              <div className="text-slate-500">Target Price</div>
              <div className="font-medium">{formatAmountByCurrency(comp.target_price, ticker)}</div>
            </div>
            <div>
              <div className="text-slate-500">Stop Loss</div>
              <div className="font-medium">{formatAmountByCurrency(comp.stop_loss, ticker)}</div>
            </div>
            <div>
              <div className="text-slate-500">Time Horizon</div>
              <div className="font-medium">{comp.time_horizon_months ? `${comp.time_horizon_months} months` : '—'}</div>
            </div>
            <div>
              <div className="text-slate-500">Risk Rating</div>
              <div className="font-medium">{comp.risk_rating ?? '—'}</div>
            </div>
          </div>
          <div className="grid grid-cols-5 gap-2 mt-4 text-xs">
            <div>
              <div className="text-slate-500">Financial</div>
              <div className="font-medium">{formatNumber(comp.financial_health_score, 0)}</div>
            </div>
            <div>
              <div className="text-slate-500">Valuation</div>
              <div className="font-medium">{formatNumber(comp.valuation_score, 0)}</div>
            </div>
            <div>
              <div className="text-slate-500">Growth</div>
              <div className="font-medium">{formatNumber(comp.growth_prospects_score, 0)}</div>
            </div>
            <div>
              <div className="text-slate-500">Governance</div>
              <div className="font-medium">{formatNumber(comp.governance_score, 0)}</div>
            </div>
            <div>
              <div className="text-slate-500">Macro</div>
              <div className="font-medium">{formatNumber(comp.macro_sensitivity_score, 0)}</div>
            </div>
          </div>
        </div>
      )}

      {comp && (
        <div className="card p-5">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-lg font-medium">Governance & Red Flags</h3>
            <Icons.Fundamentals className="w-5 h-5 text-slate-500" aria-hidden />
          </div>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-slate-500">Governance Score</div>
              <div className="font-medium">{formatNumber(comp.governance_score, 0)}</div>
            </div>
            <div>
              <div className="text-slate-500">Risk Rating</div>
              <div className="font-medium">{comp.risk_rating || '—'}</div>
            </div>
          </div>
          {(comp.key_risks?.length || comp.key_catalysts?.length) && (
            <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
              {comp.key_risks?.length > 0 && (
                <div>
                  <div className="text-slate-500">Top Risks</div>
                  <div className="font-medium text-red-600">
                    {comp.key_risks.slice(0, 3).join(', ')}
                  </div>
                </div>
              )}
              {comp.key_catalysts?.length > 0 && (
                <div>
                  <div className="text-slate-500">Catalysts</div>
                  <div className="font-medium text-green-600">
                    {comp.key_catalysts.slice(0, 3).join(', ')}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      <div className="card p-5">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-medium">Technical Summary</h3>
          <Icons.Technical className="w-5 h-5 text-slate-500" aria-hidden />
        </div>
        {labels.length > 1 && closes.length > 1 ? (
          <TechnicalChart labels={labels.slice(-90)} closes={closes.slice(-90)} />
        ) : (
          <div className="h-16 rounded bg-slate-100" aria-hidden></div>
        )}
        {(signals || indicators) && (
          <div className="grid grid-cols-3 gap-3 mt-3 text-sm">
            {signals && (
              <>
                <div>
                  <div className="text-slate-500">Regime</div>
                  <div className="font-medium">{signals.regime ?? '—'}</div>
                </div>
                <div>
                  <div className="text-slate-500">Signal Score</div>
                  <div className="font-medium">{formatNumber(signals.score, 2)}</div>
                </div>
              </>
            )}
            {indicators && (
              <div>
                <div className="text-slate-500">RSI(14)</div>
                <div className="font-medium">{formatNumber(indicators.rsi14, 1)}</div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-medium">Fundamentals</h3>
          <Icons.Fundamentals className="w-5 h-5 text-slate-500" aria-hidden />
        </div>
        {report?.fundamentals?.details ? (
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-slate-500">P/E</div>
              <div className="font-medium">{formatNumber(report.fundamentals.details.pe, 2)}</div>
            </div>
            <div>
              <div className="text-slate-500">P/B</div>
              <div className="font-medium">{formatNumber(report.fundamentals.details.pb, 2)}</div>
            </div>
            <div>
              <div className="text-slate-500">ROE</div>
              <div className="font-medium">{formatPct(report.fundamentals.details.roe, 1)}</div>
            </div>
            <div>
              <div className="text-slate-500">Dividend Yield</div>
              <div className="font-medium">{formatPct(report.fundamentals.details.dividendYield, 2)}</div>
            </div>
            <div>
              <div className="text-slate-500">ROIC</div>
              <div className="font-medium">{formatPct(report.fundamentals.details.roic, 1)}</div>
            </div>
            <div>
              <div className="text-slate-500">FCF Yield</div>
              <div className="font-medium">{formatPct(report.fundamentals.details.fcfYield, 2)}</div>
            </div>
            <div>
              <div className="text-slate-500">EBITDA Margin</div>
              <div className="font-medium">{formatPct(report.fundamentals.details.ebitdaMargin, 1)}</div>
            </div>
            <div>
              <div className="text-slate-500">Interest Coverage</div>
              <div className="font-medium">{report.fundamentals.details.interestCoverage ? `${formatNumber(report.fundamentals.details.interestCoverage, 1)}×` : '—'}</div>
            </div>
            <div>
              <div className="text-slate-500">PEG</div>
              <div className="font-medium">{formatNumber(report.fundamentals.details.peg, 2)}</div>
            </div>
          </div>
        ) : (
          <div className="h-16 rounded bg-slate-100" aria-hidden></div>
        )}
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-medium">Cash Flow</h3>
          <Icons.Cashflow className="w-5 h-5 text-slate-500" aria-hidden />
        </div>
        {report?.cashflow?.details ? (
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-slate-500">OCF (latest)</div>
              <div className="font-medium">{formatAmountByCurrency(report.cashflow.details.ocf_latest, ticker)}</div>
            </div>
            <div>
              <div className="text-slate-500">OCF Trend</div>
              <div className="font-medium">{report.cashflow.details.ocf_trend ?? '—'}</div>
            </div>
            <div>
              <div className="text-slate-500">CapEx (latest)</div>
              <div className="font-medium">{formatAmountByCurrency(report.cashflow.details.capex_latest, ticker)}</div>
            </div>
            {report.cashflow.details.free_cash_flow !== undefined && (
              <div>
                <div className="text-slate-500">Free Cash Flow</div>
                <div className="font-medium">{formatAmountByCurrency(report.cashflow.details.free_cash_flow, ticker)}</div>
              </div>
            )}
            {report.cashflow.details.summary && (
              <div className="md:col-span-2 text-slate-600" aria-live="polite">
                <span className="text-xs">{report.cashflow.details.summary}</span>
              </div>
            )}
          </div>
        ) : (
          <div className="h-16 rounded bg-slate-100" aria-hidden></div>
        )}
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-medium">Peer Analysis</h3>
          <Icons.Technical className="w-5 h-5 text-slate-500" aria-hidden />
        </div>
        {report?.peer_analysis?.details ? (
          <div className="space-y-2 text-sm">
            <div>
              <div className="text-slate-500">Relative Position</div>
              <div className="font-medium">{report.peer_analysis.details.relative_position || '—'}</div>
            </div>
            <div>
              <div className="text-slate-500">Peers Analyzed</div>
              <div className="font-medium">{report.peer_analysis.details.peers_identified?.length || 0} companies</div>
            </div>
            {report.peer_analysis.details.strengths?.length > 0 && (
              <div>
                <div className="text-slate-500">Key Strengths</div>
                <div className="font-medium text-green-600">{report.peer_analysis.details.strengths.slice(0, 2).join(', ')}</div>
              </div>
            )}
          </div>
        ) : (
          <div className="h-16 rounded bg-slate-100" aria-hidden></div>
        )}
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-medium">Analyst Consensus</h3>
          <Icons.Star className="w-5 h-5 text-slate-500" aria-hidden />
        </div>
        {report?.analyst_recommendations?.details ? (
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div>
              <div className="text-slate-500">Consensus</div>
              <div className="font-medium">{report.analyst_recommendations.details.recommendation_summary?.consensus || '—'}</div>
            </div>
            <div>
              <div className="text-slate-500">Target Price</div>
              <div className="font-medium">{(() => {
                const target = report.analyst_recommendations.details.target_prices?.mean
                return target ? formatAmountByCurrency(target, ticker) : '—'
              })()}</div>
            </div>
            <div>
              <div className="text-slate-500">Implied Return</div>
              <div className="font-medium">{formatPct(report.analyst_recommendations.details.consensus_analysis?.implied_return / 100, 1)}</div>
            </div>
            <div>
              <div className="text-slate-500">Analyst Count</div>
              <div className="font-medium">{report.analyst_recommendations.details.recommendation_summary?.analyst_count || '—'}</div>
            </div>
          </div>
        ) : (
          <div className="h-16 rounded bg-slate-100" aria-hidden></div>
        )}
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-medium">Growth Prospects</h3>
          <Icons.TrendingUp className="w-5 h-5 text-slate-500" aria-hidden />
        </div>
        {report?.growth_prospects?.details ? (
          <div className="space-y-2 text-sm">
            <div>
              <div className="text-slate-500">Overall Outlook</div>
              <div className="font-medium">{report.growth_prospects.details.growth_outlook?.overall_outlook || '—'}</div>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <div className="text-slate-500">1Y Est.</div>
                <div className="font-medium">{formatPct(report.growth_prospects.details.growth_outlook?.short_term?.revenue_growth_estimate, 1)}</div>
              </div>
              <div>
                <div className="text-slate-500">3Y Est.</div>
                <div className="font-medium">{formatPct(report.growth_prospects.details.growth_outlook?.medium_term?.revenue_growth_estimate, 1)}</div>
              </div>
              <div>
                <div className="text-slate-500">5Y+ Est.</div>
                <div className="font-medium">{formatPct(report.growth_prospects.details.growth_outlook?.long_term?.revenue_growth_estimate, 1)}</div>
              </div>
            </div>
          </div>
        ) : (
          <div className="h-16 rounded bg-slate-100" aria-hidden></div>
        )}
      </div>

      <div className="card p-5">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-medium">Enhanced Valuation</h3>
          <Icons.Fundamentals className="w-5 h-5 text-slate-500" aria-hidden />
        </div>
        {report?.valuation?.details ? (
          <div className="space-y-2 text-sm">
            <div>
              <div className="text-slate-500">Consolidated Target</div>
              <div className="font-medium">{(() => {
                const target = report.valuation.details.consolidated_valuation?.target_price
                return target ? formatAmountByCurrency(target, ticker) : '—'
              })()}</div>
            </div>
            <div>
              <div className="text-slate-500">Upside/Downside</div>
              <div className="font-medium">{formatPct(report.valuation.details.consolidated_valuation?.upside_downside_pct / 100, 1)}</div>
            </div>
            <div>
              <div className="text-slate-500">Models Used</div>
              <div className="font-medium">{report.valuation.details.consolidated_valuation?.models_used?.join(', ') || '—'}</div>
            </div>
            <div>
              <div className="text-slate-500">Confidence</div>
              <div className="font-medium">{report.valuation.details.consolidated_valuation?.confidence || '—'}</div>
            </div>
          </div>
        ) : (
          <div className="h-16 rounded bg-slate-100" aria-hidden></div>
        )}
      </div>

      <div className="card p-5 md:col-span-2">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-medium">Sentiment</h3>
        <Icons.Sentiment className="w-5 h-5 text-slate-500" aria-hidden />
        </div>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div>
            <div className="text-slate-500 flex items-center gap-2">
              News Sentiment
              {report?.news_sentiment?.latest_date && (
                <span className="text-xs text-slate-400">
                  ({new Date(report.news_sentiment.latest_date).toLocaleDateString()})
                </span>
              )}
            </div>
            <div className="font-medium text-sm mb-2">
              {report?.news_sentiment?.details?.professional_sentiment || 
               report?.news_sentiment?.professional_sentiment || '—'}
            </div>
            {(() => {
              const headlineAnalyses = report?.news_sentiment?.details?.headline_analyses || 
                                     report?.news_sentiment?.headline_analyses || [];
              const headlines = report?.news_sentiment?.details?.headlines || 
                              report?.news_sentiment?.headlines || [];
              const articleCount = report?.news_sentiment?.details?.article_count ?? 
                                 report?.news_sentiment?.article_count ?? 0;
              
              // Show professional format if available, otherwise fallback to basic format
              if (headlineAnalyses && headlineAnalyses.length > 0) {
                return (
                  <div className="space-y-1">
                    <div className="text-xs font-medium text-slate-600 mb-1">Headlines:</div>
                    {headlineAnalyses.slice(0, 2).map((analysis: any, idx: number) => (
                      <div key={idx} className="text-xs text-slate-600">
                        <div className="line-clamp-1 mb-1">• {analysis.headline}</div>
                        <div className="text-slate-500 ml-2">
                          <span className={`font-medium ${
                            analysis.sentiment === 'Positive' ? 'text-green-600' : 
                            analysis.sentiment === 'Negative' ? 'text-red-600' : 
                            'text-slate-600'
                          }`}>
                            {analysis.sentiment}
                          </span>
                          : {analysis.rationale}
                        </div>
                      </div>
                    ))}
                    {articleCount > 2 && (
                      <div className="text-xs text-blue-600 mt-1">
                        +{articleCount - 2} more articles
                      </div>
                    )}
                  </div>
                );
              } else if (headlines && headlines.length > 0) {
                // Fallback to simple format
                return (
                  <div className="mt-2 space-y-1">
                    {headlines.slice(0, 2).map((headline: string, idx: number) => (
                      <div key={idx} className="text-xs text-slate-600 line-clamp-2">
                        • {headline}
                      </div>
                    ))}
                    {articleCount > 2 && (
                      <div className="text-xs text-blue-600">
                        +{articleCount - 2} more articles
                      </div>
                    )}
                  </div>
                );
              }
              return null;
            })()}
          </div>
          <div>
            <div className="text-slate-500">YouTube</div>
            <div className="font-medium">{report?.youtube_sentiment?.summary || '—'}</div>
          </div>
        </div>
      </div>
    </div>
  )
}
