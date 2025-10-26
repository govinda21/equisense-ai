import { useState, useMemo } from 'react'
import { Icons } from './icons'
import { ResultSummaryGrid } from './ResultSummaryGrid'

interface RankedStock {
  ticker: string
  confidenceScore: number
  lastPrice: number
  changePercent: number
  sentiment: 'bullish' | 'bearish' | 'neutral'
  marketCap?: number
  sector?: string
  volatility?: number
  recommendation?: string
  report?: any // Full analysis report
}

interface RankedStockListProps {
  stocks: RankedStock[]
  mode: 'buy' | 'sell'
  onAnalyze?: (tickers: string[]) => void
  loading?: boolean
}

type SortField = 'confidence' | 'price' | 'change' | 'marketCap' | 'volatility'
type SortDirection = 'asc' | 'desc'

export function RankedStockList({ stocks, mode, loading }: RankedStockListProps) {
  const [expandedTickers, setExpandedTickers] = useState<Set<string>>(new Set())
  const [sortField, setSortField] = useState<SortField>('confidence')
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc')
  const [sectorFilter, setSectorFilter] = useState<string>('all')
  const [minConfidence, setMinConfidence] = useState<number>(0)

  // Toggle expansion
  const toggleExpand = (ticker: string) => {
    const newExpanded = new Set(expandedTickers)
    if (newExpanded.has(ticker)) {
      newExpanded.delete(ticker)
    } else {
      newExpanded.add(ticker)
    }
    setExpandedTickers(newExpanded)
  }

  // Sorting logic
  const sortedStocks = useMemo(() => {
    let filtered = stocks.filter(stock => {
      if (sectorFilter !== 'all' && stock.sector !== sectorFilter) return false
      if (stock.confidenceScore < minConfidence) return false
      return true
    })

    return filtered.sort((a, b) => {
      // If sorting by recommendation (default), use recommendation strength + confidence
      if (sortField === 'confidence') {
        // Define recommendation strength order
        const getRecommendationStrength = (rec: string) => {
          const strengthMap: { [key: string]: number } = {
            'Strong Buy': 7,
            'Buy': 6,
            'Hold': 5,
            'Weak Hold': 4,
            'Weak Sell': 3,
            'Sell': 2,
            'Strong Sell': 1
          }
          return strengthMap[rec] || 0
        }
        
        const aStrength = getRecommendationStrength(a.recommendation || '')
        const bStrength = getRecommendationStrength(b.recommendation || '')
        
        // First sort by recommendation strength (descending)
        if (aStrength !== bStrength) {
          return bStrength - aStrength
        }
        
        // Then sort by confidence score (descending)
        return b.confidenceScore - a.confidenceScore
      }
      
      // For other sort fields, use the original logic
      let aVal: number, bVal: number
      
      switch (sortField) {
        case 'price':
          aVal = a.lastPrice
          bVal = b.lastPrice
          break
        case 'change':
          aVal = a.changePercent
          bVal = b.changePercent
          break
        case 'marketCap':
          aVal = a.marketCap || 0
          bVal = b.marketCap || 0
          break
        case 'volatility':
          aVal = a.volatility || 0
          bVal = b.volatility || 0
          break
        default:
          return 0
      }
      
      return sortDirection === 'asc' ? aVal - bVal : bVal - aVal
    })
  }, [stocks, sortField, sortDirection, sectorFilter, minConfidence])

  // Get unique sectors for filter
  const sectors = useMemo(() => {
    const uniqueSectors = new Set(stocks.map(s => s.sector).filter(Boolean))
    return Array.from(uniqueSectors) as string[]
  }, [stocks])

  // Confidence color coding (WCAG AA compliant contrast)
  const getConfidenceColor = (score: number) => {
    if (score >= 80) return 'text-green-800 bg-green-100 border-green-300 dark:text-green-100 dark:bg-green-900 dark:border-green-700'
    if (score >= 60) return 'text-blue-800 bg-blue-100 border-blue-300 dark:text-blue-100 dark:bg-blue-900 dark:border-blue-700'
    if (score >= 40) return 'text-yellow-800 bg-yellow-100 border-yellow-300 dark:text-yellow-100 dark:bg-yellow-900 dark:border-yellow-700'
    return 'text-red-800 bg-red-100 border-red-300 dark:text-red-100 dark:bg-red-900 dark:border-red-700'
  }

  // Sentiment icon
  const getSentimentIcon = (sentiment: string) => {
    switch (sentiment) {
      case 'bullish': return '🐂'
      case 'bearish': return '🐻'
      default: return '➡️'
    }
  }

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
            Ranked {mode === 'buy' ? 'Buy' : 'Sell'} Opportunities
          </h2>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            {sortedStocks.length} stocks analyzed • Sorted by {sortField === 'confidence' ? 'recommendation strength' : sortField}
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setExpandedTickers(new Set())}
            className="px-3 py-1.5 text-sm border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200"
          >
            Collapse All
          </button>
        </div>
      </div>

      {/* Filters & Sorting */}
      <div className="card p-4 mb-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Sort By */}
          <div>
            <label className="block text-xs font-semibold text-slate-900 dark:text-slate-100 mb-1">Sort By</label>
            <select
              value={sortField}
              onChange={(e) => handleSort(e.target.value as SortField)}
              className="w-full px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 font-medium"
            >
              <option value="confidence">Recommendation Strength</option>
              <option value="price">Last Price</option>
              <option value="change">Change %</option>
              <option value="marketCap">Market Cap</option>
              <option value="volatility">Volatility</option>
            </select>
          </div>

          {/* Direction */}
          <div>
            <label className="block text-xs font-semibold text-slate-900 dark:text-slate-100 mb-1">Direction</label>
            <button
              onClick={() => setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')}
              className="w-full px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-200 flex items-center justify-center font-medium"
            >
              {sortDirection === 'desc' ? '↓ High to Low' : '↑ Low to High'}
            </button>
          </div>

          {/* Sector Filter */}
          <div>
            <label className="block text-xs font-semibold text-slate-900 dark:text-slate-100 mb-1">Sector</label>
            <select
              value={sectorFilter}
              onChange={(e) => setSectorFilter(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100 font-medium"
            >
              <option value="all">All Sectors</option>
              {sectors.map(sector => (
                <option key={sector} value={sector}>{sector}</option>
              ))}
            </select>
          </div>

          {/* Min Confidence */}
          <div>
            <label className="block text-xs font-semibold text-slate-900 dark:text-slate-100 mb-1">
              Min Confidence: {minConfidence}%
            </label>
            <input
              type="range"
              min="0"
              max="100"
              step="5"
              value={minConfidence}
              onChange={(e) => setMinConfidence(Number(e.target.value))}
              className="w-full"
            />
          </div>
        </div>
      </div>

      {/* Empty State (only show when loading and no results yet) */}
      {loading && sortedStocks.length === 0 && (
        <div className="card p-8 text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-slate-600 dark:text-slate-400">Analyzing stocks...</p>
        </div>
      )}

      {/* Empty State (when not loading but no results) */}
      {!loading && sortedStocks.length === 0 && (
        <div className="card p-8 text-center">
          <p className="text-slate-600 dark:text-slate-400">No stocks match your filters</p>
        </div>
      )}

      {/* Stock List - Show even while loading if we have results */}
      {sortedStocks.length > 0 && sortedStocks.map((stock, index) => {
        const isExpanded = expandedTickers.has(stock.ticker)
        const confidenceColorClass = getConfidenceColor(stock.confidenceScore)
        
        return (
          <div key={stock.ticker} className="card overflow-hidden">
            {/* Compact View */}
            <div
              className="p-4 cursor-pointer hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors"
              onClick={() => toggleExpand(stock.ticker)}
            >
              <div className="flex items-center justify-between gap-4">
                {/* Rank & Ticker */}
                <div className="flex items-center space-x-4 min-w-0 flex-1">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-sm font-bold text-slate-700 dark:text-slate-200">
                    {index + 1}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center space-x-2">
                      <span className="text-lg font-bold text-slate-950 dark:text-slate-50">{stock.ticker}</span>
                      <span className="text-xl">{getSentimentIcon(stock.sentiment)}</span>
                    </div>
                    {stock.sector && (
                      <span className="text-sm text-slate-700 dark:text-slate-300">{stock.sector}</span>
                    )}
                  </div>
                </div>

                {/* Confidence Score */}
                <div className={`flex-shrink-0 px-4 py-2 rounded-lg border ${confidenceColorClass}`}>
                  <div className="text-xs font-medium uppercase">Confidence</div>
                  <div className="text-2xl font-bold">{stock.confidenceScore}%</div>
                </div>

                {/* Price & Change */}
                <div className="hidden sm:block flex-shrink-0 text-right">
                  <div className="text-xl font-bold text-slate-950 dark:text-slate-50">
                    {stock.ticker.endsWith('.NS') || stock.ticker.endsWith('.BO') ? '₹' : '$'}
                    {stock.lastPrice.toLocaleString()}
                  </div>
                  <div className={`text-sm font-bold ${stock.changePercent >= 0 ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}`}>
                    {stock.changePercent >= 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%
                  </div>
                </div>

                {/* Recommendation */}
                {stock.recommendation && (
                  <div className="hidden md:block flex-shrink-0">
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                      stock.recommendation.includes('Buy') ? 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200' :
                      stock.recommendation.includes('Sell') ? 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200' :
                      'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200'
                    }`}>
                      {stock.recommendation}
                    </span>
                  </div>
                )}

                {/* Expand Icon */}
                <div className="flex-shrink-0">
                  <Icons.ChartBar className={`w-5 h-5 text-slate-400 dark:text-slate-500 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                </div>
              </div>

              {/* Mobile Price & Change */}
              <div className="sm:hidden mt-3 flex items-center justify-between">
                <div>
                  <span className="text-xl font-bold text-slate-950 dark:text-slate-50">
                    {stock.ticker.endsWith('.NS') || stock.ticker.endsWith('.BO') ? '₹' : '$'}
                    {stock.lastPrice.toLocaleString()}
                  </span>
                  <span className={`ml-2 text-sm font-bold ${stock.changePercent >= 0 ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}`}>
                    {stock.changePercent >= 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%
                  </span>
                </div>
                {stock.recommendation && (
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    stock.recommendation.includes('Buy') ? 'bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200' :
                    stock.recommendation.includes('Sell') ? 'bg-red-100 dark:bg-red-900 text-red-800 dark:text-red-200' :
                    'bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200'
                  }`}>
                    {stock.recommendation}
                  </span>
                )}
              </div>
            </div>

            {/* Expanded Detail View */}
            {isExpanded && stock.report && (
              <div className="border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 p-6">
                <ResultSummaryGrid report={stock.report} />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

