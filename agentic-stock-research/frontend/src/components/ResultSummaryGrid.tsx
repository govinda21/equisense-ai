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

function Stars({ value = 0 }: { value?: number }) {
  const numValue = Number(value) || 0
  const full = Math.floor(numValue)  // Use floor instead of round
  const hasHalf = numValue % 1 >= 0.5
  
  return (
    <div className="flex items-center gap-1" aria-label={`Rating ${value} out of 5`}>
      {Array.from({ length: 5 }, (_, i) => {
        if (i < full) {
          return <span key={i} className="text-yellow-500">★</span>;
        } else if (i === full && hasHalf) {
          return <span key={i} className="text-yellow-400">⭐</span>;
        } else {
          return <span key={i} className="text-slate-300">★</span>;
        }
      })}
    </div>
  )
}

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
  return (
    <div className="grid md:grid-cols-2 gap-6">
      <div className="card p-5">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-medium">Recommendation & Rating</h3>
          <Icons.Star className="w-5 h-5 text-slate-500" aria-hidden />
        </div>
        <div className="flex items-center gap-4">
          <span className="text-2xl font-semibold">{report?.decision?.action}</span>
          <Stars value={report?.decision?.rating} />
        </div>
      </div>

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
              News
              {report?.news_sentiment?.latest_date && (
                <span className="text-xs text-slate-400">
                  ({new Date(report.news_sentiment.latest_date).toLocaleDateString()})
                </span>
              )}
            </div>
            <div className="font-medium">{report?.news_sentiment?.summary || '—'}</div>
            {report?.news_sentiment?.headlines && report.news_sentiment.headlines.length > 0 && (
              <div className="mt-2 space-y-1">
                {report.news_sentiment.headlines.slice(0, 2).map((headline: string, idx: number) => (
                  <div key={idx} className="text-xs text-slate-600 line-clamp-2">
                    • {headline}
                  </div>
                ))}
                {report.news_sentiment.article_count > 2 && (
                  <div className="text-xs text-blue-600">
                    +{report.news_sentiment.article_count - 2} more articles
                  </div>
                )}
              </div>
            )}
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
