import { useState } from 'react'
import { Icons } from './icons'

interface BulkStockInputProps {
  onAnalyze: (tickers: string[], mode: 'buy' | 'sell') => void
  loading?: boolean
}

export function BulkStockInput({ onAnalyze, loading }: BulkStockInputProps) {
  const [inputText, setInputText] = useState('')
  const [mode, setMode] = useState<'buy' | 'sell'>('buy')
  const [error, setError] = useState('')

  // Popular watchlists
  const presetLists = {
    'NIFTY 50 Top 10': ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'HINDUNILVR.NS', 'ITC.NS', 'SBIN.NS', 'BHARTIARTL.NS', 'KOTAKBANK.NS', 'LT.NS'],
    'Tech Giants': ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META', 'NVDA', 'TSLA', 'AMD', 'INTC', 'ORCL'],
    'Indian IT': ['TCS.NS', 'INFY.NS', 'WIPRO.NS', 'HCLTECH.NS', 'TECHM.NS', 'LTI.NS'],
    'Indian Banks': ['HDFCBANK.NS', 'ICICIBANK.NS', 'KOTAKBANK.NS', 'SBIN.NS', 'AXISBANK.NS', 'INDUSINDBK.NS'],
    'Indian Pharma': ['SUNPHARMA.NS', 'DIVISLAB.NS', 'DRREDDY.NS', 'CIPLA.NS', 'AUROPHAR MO.NS']
  }

  const handleAnalyze = () => {
    // Parse input - supports comma, space, newline separated
    const tickers = inputText
      .split(/[,\s\n]+/)
      .map(t => t.trim().toUpperCase())
      .filter(t => t.length > 0)

    if (tickers.length === 0) {
      setError('Please enter at least one ticker symbol')
      return
    }

    if (tickers.length > 50) {
      setError('Maximum 50 tickers allowed per analysis')
      return
    }

    setError('')
    onAnalyze(tickers, mode)
  }

  const loadPreset = (listName: string) => {
    const tickers = presetLists[listName as keyof typeof presetLists]
    setInputText(tickers.join(', '))
    setError('')
  }

  const handleFileUpload = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (e) => {
      const text = e.target?.result as string
      setInputText(text)
      setError('')
    }
    reader.readAsText(file)
  }

  const exampleText = `Example formats:
• RELIANCE.NS, TCS.NS, INFY.NS
• AAPL MSFT GOOGL
• One per line:
  HDFCBANK.NS
  ICICIBANK.NS`

  return (
    <div className="space-y-6">
      {/* Mode Selection */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Analysis Mode</h3>
        <div className="flex space-x-4">
          <button
            onClick={() => setMode('buy')}
            className={`flex-1 px-6 py-3 rounded-lg font-medium transition-colors ${
              mode === 'buy'
                ? 'bg-green-600 text-white'
                : 'bg-white border-2 border-slate-300 text-slate-700 hover:border-green-600'
            }`}
          >
            <div className="flex items-center justify-center space-x-2">
              <span className="text-2xl">🐂</span>
              <span>Buy Opportunities</span>
            </div>
            <div className="text-sm mt-1 opacity-80">Find undervalued stocks</div>
          </button>
          
          <button
            onClick={() => setMode('sell')}
            className={`flex-1 px-6 py-3 rounded-lg font-medium transition-colors ${
              mode === 'sell'
                ? 'bg-red-600 text-white'
                : 'bg-white border-2 border-slate-300 text-slate-700 hover:border-red-600'
            }`}
          >
            <div className="flex items-center justify-center space-x-2">
              <span className="text-2xl">🐻</span>
              <span>Sell Signals</span>
            </div>
            <div className="text-sm mt-1 opacity-80">Identify overvalued positions</div>
          </button>
        </div>
      </div>

      {/* Input Methods */}
      <div className="card p-6">
        <h3 className="text-lg font-semibold text-slate-900 mb-4">Input Stock Symbols</h3>
        
        {/* Preset Lists */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Quick Start - Load Preset List
          </label>
          <div className="flex flex-wrap gap-2">
            {Object.keys(presetLists).map(listName => (
              <button
                key={listName}
                onClick={() => loadPreset(listName)}
                className="px-3 py-1.5 text-sm border border-slate-300 rounded-lg hover:bg-blue-50 hover:border-blue-500 transition-colors"
                disabled={loading}
              >
                {listName}
              </button>
            ))}
          </div>
        </div>

        {/* Text Input */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Manual Entry (comma, space, or newline separated)
          </label>
          <textarea
            value={inputText}
            onChange={(e) => {
              setInputText(e.target.value)
              setError('')
            }}
            placeholder={exampleText}
            className="w-full h-40 px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
            disabled={loading}
          />
          <div className="flex justify-between items-center mt-2">
            <p className="text-xs text-slate-500">
              {inputText.split(/[,\s\n]+/).filter(t => t.trim().length > 0).length} tickers entered (max 50)
            </p>
            <button
              onClick={() => setInputText('')}
              className="text-xs text-blue-600 hover:text-blue-800"
              disabled={loading}
            >
              Clear All
            </button>
          </div>
        </div>

        {/* File Upload */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Or Upload File (.txt, .csv)
          </label>
          <label className="flex items-center justify-center w-full h-20 px-4 border-2 border-dashed border-slate-300 rounded-lg cursor-pointer hover:bg-slate-50 transition-colors">
            <div className="flex flex-col items-center">
              <Icons.DocumentText className="w-8 h-8 text-slate-400 mb-1" />
              <span className="text-sm text-slate-600">Click to upload or drag file here</span>
            </div>
            <input
              type="file"
              className="hidden"
              accept=".txt,.csv"
              onChange={handleFileUpload}
              disabled={loading}
            />
          </label>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start">
            <Icons.AlertTriangle className="w-5 h-5 text-red-600 mr-2 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Analyze Button */}
        <button
          onClick={handleAnalyze}
          disabled={loading || inputText.trim().length === 0}
          className="w-full px-6 py-4 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors flex items-center justify-center space-x-2"
        >
          {loading ? (
            <>
              <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
              <span>Analyzing...</span>
            </>
          ) : (
            <>
              <Icons.ChartPie className="w-5 h-5" />
              <span>Analyze & Rank Stocks</span>
            </>
          )}
        </button>
      </div>

      {/* Tips */}
      <div className="card p-6 bg-blue-50 border-blue-200">
        <div className="flex items-start">
          <Icons.Star className="w-5 h-5 text-blue-600 mr-3 flex-shrink-0 mt-0.5" />
          <div>
            <h4 className="font-semibold text-blue-900 mb-2">Pro Tips</h4>
            <ul className="text-sm text-blue-800 space-y-1">
              <li>• Indian stocks: Add .NS suffix (e.g., RELIANCE.NS)</li>
              <li>• BSE stocks: Add .BO suffix (e.g., RELIANCE.BO)</li>
              <li>• US stocks: Use plain ticker (e.g., AAPL, MSFT)</li>
              <li>• Analysis takes ~10-15 seconds per stock</li>
              <li>• Results are cached for faster subsequent lookups</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}

