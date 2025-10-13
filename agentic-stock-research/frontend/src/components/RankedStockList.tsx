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

export function RankedStockList({ stocks, mode, onAnalyze, loading }: RankedStockListProps) {
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
      let aVal: number, bVal: number
      
      switch (sortField) {
        case 'confidence':
          aVal = a.confidenceScore
          bVal = b.confidenceScore
          break
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

  // Confidence color coding
  const getConfidenceColor = (score: number) => {
    if (score >= 80) return 'text-green-600 bg-green-50 border-green-200'
    if (score >= 60) return 'text-blue-600 bg-blue-50 border-blue-200'
    if (score >= 40) return 'text-yellow-600 bg-yellow-50 border-yellow-200'
    return 'text-red-600 bg-red-50 border-red-200'
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
          <h2 className="text-2xl font-bold text-slate-900">
            Ranked {mode === 'buy' ? 'Buy' : 'Sell'} Opportunities
          </h2>
          <p className="text-sm text-slate-600 mt-1">
            {sortedStocks.length} stocks analyzed • Sorted by {sortField}
          </p>
        </div>
        
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setExpandedTickers(new Set())}
            className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg hover:bg-slate-50"
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
            <label className="block text-xs font-medium text-slate-700 mb-1">Sort By</label>
            <select
              value={sortField}
              onChange={(e) => handleSort(e.target.value as SortField)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg"
            >
              <option value="confidence">Confidence Score</option>
              <option value="price">Last Price</option>
              <option value="change">Change %</option>
              <option value="marketCap">Market Cap</option>
              <option value="volatility">Volatility</option>
            </select>
          </div>

          {/* Direction */}
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Direction</label>
            <button
              onClick={() => setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc')}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg hover:bg-slate-50 flex items-center justify-center"
            >
              {sortDirection === 'desc' ? '↓ High to Low' : '↑ Low to High'}
            </button>
          </div>

          {/* Sector Filter */}
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">Sector</label>
            <select
              value={sectorFilter}
              onChange={(e) => setSectorFilter(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg"
            >
              <option value="all">All Sectors</option>
              {sectors.map(sector => (
                <option key={sector} value={sector}>{sector}</option>
              ))}
            </select>
          </div>

          {/* Min Confidence */}
          <div>
            <label className="block text-xs font-medium text-slate-700 mb-1">
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

      {/* Loading State */}
      {loading && (
        <div className="card p-8 text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-slate-600">Analyzing stocks...</p>
        </div>
      )}

      {/* Stock List */}
      {!loading && sortedStocks.length === 0 && (
        <div className="card p-8 text-center">
          <p className="text-slate-600">No stocks match your filters</p>
        </div>
      )}

      {!loading && sortedStocks.map((stock, index) => {
        const isExpanded = expandedTickers.has(stock.ticker)
        const confidenceColorClass = getConfidenceColor(stock.confidenceScore)
        
        return (
          <div key={stock.ticker} className="card overflow-hidden">
            {/* Compact View */}
            <div
              className="p-4 cursor-pointer hover:bg-slate-50 transition-colors"
              onClick={() => toggleExpand(stock.ticker)}
            >
              <div className="flex items-center justify-between gap-4">
                {/* Rank & Ticker */}
                <div className="flex items-center space-x-4 min-w-0 flex-1">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-slate-200 flex items-center justify-center text-sm font-bold text-slate-700">
                    {index + 1}
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center space-x-2">
                      <span className="text-lg font-bold text-slate-900">{stock.ticker}</span>
                      <span className="text-xl">{getSentimentIcon(stock.sentiment)}</span>
                    </div>
                    {stock.sector && (
                      <span className="text-xs text-slate-500">{stock.sector}</span>
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
                  <div className="text-lg font-semibold text-slate-900">
                    {stock.ticker.endsWith('.NS') || stock.ticker.endsWith('.BO') ? '₹' : '$'}
                    {stock.lastPrice.toLocaleString()}
                  </div>
                  <div className={`text-sm font-medium ${stock.changePercent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {stock.changePercent >= 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%
                  </div>
                </div>

                {/* Recommendation */}
                {stock.recommendation && (
                  <div className="hidden md:block flex-shrink-0">
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                      stock.recommendation.includes('Buy') ? 'bg-green-100 text-green-800' :
                      stock.recommendation.includes('Sell') ? 'bg-red-100 text-red-800' :
                      'bg-blue-100 text-blue-800'
                    }`}>
                      {stock.recommendation}
                    </span>
                  </div>
                )}

                {/* Expand Icon */}
                <div className="flex-shrink-0">
                  <Icons.ChartBar className={`w-5 h-5 text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} />
                </div>
              </div>

              {/* Mobile Price & Change */}
              <div className="sm:hidden mt-3 flex items-center justify-between">
                <div>
                  <span className="text-lg font-semibold text-slate-900">
                    {stock.ticker.endsWith('.NS') || stock.ticker.endsWith('.BO') ? '₹' : '$'}
                    {stock.lastPrice.toLocaleString()}
                  </span>
                  <span className={`ml-2 text-sm font-medium ${stock.changePercent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {stock.changePercent >= 0 ? '+' : ''}{stock.changePercent.toFixed(2)}%
                  </span>
                </div>
                {stock.recommendation && (
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                    stock.recommendation.includes('Buy') ? 'bg-green-100 text-green-800' :
                    stock.recommendation.includes('Sell') ? 'bg-red-100 text-red-800' :
                    'bg-blue-100 text-blue-800'
                  }`}>
                    {stock.recommendation}
                  </span>
                )}
              </div>
            </div>

            {/* Expanded Detail View */}
            {isExpanded && stock.report && (
              <div className="border-t border-slate-200 bg-slate-50 p-6">
                <ResultSummaryGrid report={stock.report} />
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

