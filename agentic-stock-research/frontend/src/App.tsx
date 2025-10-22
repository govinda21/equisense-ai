import { useState, useEffect, useRef } from 'react'
import { ResultSummaryGrid } from './components/ResultSummaryGrid'
import { ChatInterface } from './components/ChatInterface'
import { Icons } from './components/icons'
import { ErrorBoundary } from './components/ErrorBoundary'
import { ToastProvider, useToastHelpers } from './components/Toast'
import { LoadingOverlay, Spinner, ProgressBar } from './components/LoadingStates'
import { ErrorState } from './components/ErrorStates'
import { BulkStockInput } from './components/BulkStockInput'
import { RankedStockList } from './components/RankedStockList'
// import { AuthProvider, useAuth, LoginForm } from './components/Auth'  // Disabled for now
// import { EnhancedDashboard } from './components/EnhancedDashboard'  // Disabled for now

// Badge UI is currently unused; keep implementation minimal when needed next.

function Field({ id, label, hint, children }: { id: string; label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="label" htmlFor={id}>{label}</label>
      {children}
      {hint && <p className="mt-1 text-xs text-slate-500" id={`${id}-hint`}>{hint}</p>}
    </div>
  )
}

interface AppProps {
  chatOpen: boolean
  currentView: 'dashboard' | 'analysis'
  onViewChange: (view: 'dashboard' | 'analysis') => void
}

// type ViewType = 'dashboard' | 'analysis';  // Removed - not used

function AppContent({ chatOpen, currentView }: AppProps) {
  // const { user, loading: authLoading } = useAuth()  // Disabled for now
  // const user = { full_name: 'User' }  // Mock user for now - not used
  const [activeTab, setActiveTab] = useState<'single' | 'bulk'>('single')
  const [tickers, setTickers] = useState('RELIANCE')
  const [country, setCountry] = useState('India')
  const [countries, setCountries] = useState<string[]>(['India', 'United States', 'United Kingdom', 'Canada'])
  const [hs, setHs] = useState(30)
  const [hl, setHl] = useState(365)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorType, setErrorType] = useState<'network' | 'server' | 'validation' | 'generic'>('generic')
  const [data, setData] = useState<any | null>(null)
  const [latency, setLatency] = useState<number | null>(null)
  const [analysisProgress, setAnalysisProgress] = useState(0)
  
  // Bulk analysis state
  const [bulkLoading, setBulkLoading] = useState(false)
  const [rankedStocks, setRankedStocks] = useState<any[]>([])
  const [bulkMode, setBulkMode] = useState<'buy' | 'sell'>('buy')
  
  const toast = useToastHelpers()
  const countriesFetched = useRef(false)

  // Show loading spinner while checking authentication - DISABLED
  // if (authLoading) {
  //   return (
  //     <div className="min-h-screen flex items-center justify-center">
  //       <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500"></div>
  //     </div>
  //   )
  // }

  // Show login form if user is not authenticated - DISABLED
  // if (!user) {
  //   return <LoginForm />
  // }

  // Add navigation state for dashboard vs analysis - REMOVED (now passed as prop)
  // const [currentView, setCurrentView] = useState<ViewType>('dashboard')

  // Show dashboard or analysis based on current view
  if (currentView === 'dashboard') {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold text-gray-900 mb-6">Dashboard</h1>
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-semibold mb-4">Welcome to Equisense AI</h2>
            <p className="text-gray-600 mb-4">
              This is a simplified dashboard view. The full dashboard is being loaded...
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-blue-50 p-4 rounded-lg">
                <h3 className="font-semibold text-blue-900">Stock Analysis</h3>
                <p className="text-blue-700 text-sm">Analyze individual stocks</p>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <h3 className="font-semibold text-green-900">Bulk Ranking</h3>
                <p className="text-green-700 text-sm">Compare multiple stocks</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }

  // Fetch supported countries on component mount (with StrictMode protection)
  useEffect(() => {
    // Prevent double execution in React StrictMode
    if (countriesFetched.current) {
      return
    }
    
    let isMounted = true
    countriesFetched.current = true
    
    const fetchCountries = async () => {
      try {
        const base = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000'
        const response = await fetch(base + '/countries')
        
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`)
        }
        
        const data = await response.json()
        
        // Only update state if component is still mounted
        if (isMounted && data.countries) {
          setCountries(data.countries)
        }
      } catch (error) {
        console.error('Failed to fetch countries:', error)
        
        // Only update state if component is still mounted
        if (isMounted) {
          setCountries(['India', 'United States', 'United Kingdom', 'Canada'])
        }
      }
    }
    
    fetchCountries()
    
    // Cleanup function to prevent state updates on unmounted component
    return () => {
      isMounted = false
    }
  }, [])

  // Update default ticker based on country selection
  useEffect(() => {
    if (country === 'India' && (tickers === 'AAPL' || tickers === 'MSFT')) {
      setTickers('RELIANCE')
    } else if (country === 'United States' && (tickers === 'RELIANCE' || tickers === 'TCS' || tickers === 'HDFCBANK')) {
      setTickers('AAPL')
    }
  }, [country])

  // Quick-set tickers helper (reserved for future presets)
  // const quick = (t: string) => setTickers(t)

  const submit = async (e?: React.FormEvent) => {
    e?.preventDefault()
    setError(null)
    setData(null)
    setAnalysisProgress(0)
    
    // Validation
    const parsed = tickers.split(',').map(t => t.trim()).filter(t => t.length > 0)
    if (parsed.length === 0) { 
      const errorMsg = `Enter at least one valid ticker, e.g., ${country === 'India' ? 'JIOFIN or BAJFINANCE' : 'AAPL or MSFT'}`
      setError(errorMsg)
      setErrorType('validation')
      toast.error(errorMsg, 'Invalid Input')
      return 
    }

    if (parsed.length > 5) {
      const errorMsg = 'Please analyze maximum 5 tickers at once'
      setError(errorMsg)
      setErrorType('validation')
      toast.error(errorMsg, 'Too Many Tickers')
      return
    }
    
    setLoading(true)
    const start = performance.now()
    
    // Simulate progress for better UX
    const progressInterval = setInterval(() => {
      setAnalysisProgress(prev => {
        if (prev >= 90) return prev
        return prev + Math.random() * 10
      })
    }, 1000)
    
    try {
      const base = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000'
      
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 120000) // 2 minute timeout
      
      const res = await fetch(base + '/analyze', {
        method: 'POST', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ 
          tickers: parsed, 
          country: country, 
          horizon_short_days: hs, 
          horizon_long_days: hl 
        }),
        signal: controller.signal
      })
      
      clearTimeout(timeoutId)
      
      if (!res.ok) {
        // Create error with response info for better error handling
        const error = new Error(`HTTP ${res.status}: ${res.statusText}`)
        ;(error as any).response = res
        ;(error as any).status = res.status
        throw error
      }
      
      const txt = await res.text()
      let j: any
      try { 
        j = JSON.parse(txt) 
      } catch { 
        const error = new Error('Invalid response from server. Please try again.')
        ;(error as any).response = res
        ;(error as any).status = res.status
        throw error
      }
      
      setAnalysisProgress(100)
      setData(j)
      toast.success(
        `Analysis completed for ${parsed.join(', ')} in ${Math.round(performance.now() - start)}ms`,
        'Analysis Complete'
      )
      
    } catch (err: any) {
      const errorMsg = err.message || String(err)
      let errorType: 'network' | 'server' | 'validation' | 'generic' = 'generic'
      let userMessage = errorMsg
      let toastTitle = 'Analysis Failed'
      
      // Detailed error categorization based on error patterns
      if (err.name === 'AbortError') {
        errorType = 'server'
        userMessage = 'Analysis timed out after 2 minutes. Please try again with fewer tickers.'
        toastTitle = 'Request Timeout'
      } else if (err.name === 'TypeError' && errorMsg.includes('Failed to fetch')) {
        // Backend is completely down or unreachable
        errorType = 'network'
        userMessage = 'Cannot connect to the analysis service. Please check if the backend server is running on port 8000.'
        toastTitle = 'Backend Unreachable'
      } else if (errorMsg.includes('ECONNREFUSED') || errorMsg.includes('Connection refused')) {
        // Connection actively refused (port not open)
        errorType = 'network' 
        userMessage = 'Connection refused by server. The backend service may not be running.'
        toastTitle = 'Connection Refused'
      } else if (errorMsg.includes('ENOTFOUND') || errorMsg.includes('getaddrinfo ENOTFOUND')) {
        // DNS resolution failed
        errorType = 'network'
        userMessage = 'Cannot resolve server address. Check your network connection.'
        toastTitle = 'DNS Error'
      } else if ((err as any).status || (err as any).response?.status) {
        // HTTP status code based errors
        const status = (err as any).status || (err as any).response?.status
        switch (status) {
          case 404:
            errorType = 'server'
            userMessage = 'Analysis endpoint not found. The API may have changed.'
            toastTitle = 'Service Not Found'
            break
          case 429:
            errorType = 'server'
            userMessage = 'Too many requests. Please wait a moment before trying again.'
            toastTitle = 'Rate Limited'
            break
          case 500:
            errorType = 'server'
            userMessage = 'Internal server error. The backend service encountered a problem.'
            toastTitle = 'Server Error'
            break
          case 502:
            errorType = 'server'
            userMessage = 'Bad gateway. The server is misconfigured or unavailable.'
            toastTitle = 'Bad Gateway'
            break
          case 503:
            errorType = 'server'
            userMessage = 'Service temporarily unavailable. The server may be overloaded.'
            toastTitle = 'Service Unavailable'
            break
          case 504:
            errorType = 'server'
            userMessage = 'Gateway timeout. The server took too long to respond.'
            toastTitle = 'Gateway Timeout'
            break
          default:
            errorType = 'server'
            userMessage = `Server returned error ${status}: ${(err as any).response?.statusText || 'Unknown error'}`
            toastTitle = `HTTP ${status}`
        }
      } else if (errorMsg.includes('JSON') || errorMsg.includes('Unexpected token')) {
        // Invalid JSON response from server
        errorType = 'server'
        userMessage = 'Received invalid response from server. The service may be experiencing issues.'
        toastTitle = 'Invalid Response'
      } else if (errorMsg.includes('NetworkError') || errorMsg.includes('network')) {
        // General network issues
        errorType = 'network'
        userMessage = 'Network error occurred. Check your internet connection and try again.'
        toastTitle = 'Network Error'
      } else if (errorMsg.includes('timeout')) {
        // Various timeout scenarios
        errorType = 'server'
        userMessage = 'Request timed out. The server may be slow or overloaded.'
        toastTitle = 'Request Timeout'
      }
      
      setError(userMessage)
      setErrorType(errorType)
      toast.error(userMessage, toastTitle)
      
    } finally {
      clearInterval(progressInterval)
      setLatency(Math.round(performance.now() - start))
      setLoading(false)
      setAnalysisProgress(0)
    }
  }

  // Bulk analysis function with improved rate limiting
  const handleBulkAnalyze = async (tickerList: string[], mode: 'buy' | 'sell') => {
    console.log('Starting bulk analysis:', { tickerList, mode })
    setBulkLoading(true)
    setBulkMode(mode)
    setRankedStocks([])
    
    try {
      toast.info(`Analyzing ${tickerList.length} stocks...`, 'Bulk Analysis Started')
      
      // Analyze stocks in smaller batches with delays to respect rate limits
      const batchSize = 3  // Reduced batch size
      const delayBetweenBatches = 2000  // 2 second delay between batches
      const results: any[] = []
      
      for (let i = 0; i < tickerList.length; i += batchSize) {
        const batch = tickerList.slice(i, i + batchSize)
        console.log(`Processing batch ${Math.floor(i/batchSize) + 1}:`, batch)
        
        // Analyze batch with individual delays
        const batchPromises = batch.map(async (ticker, index) => {
          try {
            // Add delay between individual requests within batch
            if (index > 0) {
              await new Promise(resolve => setTimeout(resolve, 1000))
            }
            
            const base = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000'
            const res = await fetch(base + '/analyze', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                tickers: [ticker],
                target_depth: 'quick' // Use quick analysis for bulk
              }),
              signal: AbortSignal.timeout(60000) // 60 sec timeout per stock
            })
            
            if (!res.ok) {
              console.error(`Failed to fetch ${ticker}: ${res.status}`)
              return null
            }
            
            const data = await res.json()
            console.log(`Response for ${ticker}:`, data)
            
            const report = data.reports?.[0]
            if (!report) {
              console.warn(`No report found for ${ticker}`)
              return null
            }
            
            // Extract key metrics
            const decision = report.decision || {}
            const tech = report.technicals?.details || {}
            const fundamentals = report.fundamentals?.details || {}
            
            // Get last price from multiple sources
            let lastPrice = 0
            if (tech.closes && tech.closes.length > 0) {
              lastPrice = tech.closes[tech.closes.length - 1]
            } else if (fundamentals.current_price) {
              lastPrice = fundamentals.current_price
            }
            
            const result = {
              ticker,
              confidenceScore: Math.round((decision.rating || 2.5) * 20), // Convert 0-5 to 0-100
              lastPrice,
              changePercent: tech.close_change_pct || fundamentals.change_pct || 0,
              sentiment: decision.rating >= 3.5 ? 'bullish' : decision.rating <= 2.5 ? 'bearish' : 'neutral',
              recommendation: decision.action || 'Hold',
              marketCap: fundamentals.market_cap,
              sector: fundamentals.sector || 'Unknown',
              volatility: tech.volatility || 0,
              report: report // Store full report for expansion
            }
            
            console.log(`Extracted data for ${ticker}:`, result)
            return result
          } catch (err) {
            console.error(`Failed to analyze ${ticker}:`, err)
            return null
          }
        })
        
        const batchResults = await Promise.all(batchPromises)
        const validResults = batchResults.filter(r => r !== null)
        console.log(`Batch complete. Valid results:`, validResults)
        results.push(...validResults)
        
        // Update progress
        toast.info(
          `Analyzed ${Math.min(i + batchSize, tickerList.length)} of ${tickerList.length} stocks`,
          'Progress'
        )
        
        // Add delay between batches to respect rate limits
        if (i + batchSize < tickerList.length) {
          await new Promise(resolve => setTimeout(resolve, delayBetweenBatches))
        }
      }
      
      console.log('All batches complete. Total results:', results.length)
      
      // Sort by recommendation strength first, then by confidence score
      const sorted = results.sort((a, b) => {
        // Define recommendation strength order for buy opportunities
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
        
        const aStrength = getRecommendationStrength(a.recommendation)
        const bStrength = getRecommendationStrength(b.recommendation)
        
        // First sort by recommendation strength (descending)
        if (aStrength !== bStrength) {
          return bStrength - aStrength
        }
        
        // Then sort by confidence score (descending)
        return b.confidenceScore - a.confidenceScore
      })
      console.log('Sorted results:', sorted)
      setRankedStocks(sorted)
      
      toast.success(
        `Successfully analyzed ${results.length} of ${tickerList.length} stocks`,
        'Bulk Analysis Complete'
      )
      
    } catch (err: any) {
      toast.error(err.message || 'Bulk analysis failed', 'Error')
    } finally {
      setBulkLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-slate-50 to-blue-50 dark:from-slate-900 dark:to-slate-800">
        <main className="flex-1 py-4 sm:py-6 md:py-8">
          <div className="container px-3 sm:px-4 md:px-6">

          {/* Side-by-side Layout - Mobile Responsive */}
          <div className="flex flex-col lg:flex-row gap-4 sm:gap-6 min-h-[calc(100vh-180px)]">
            {/* Main Content Area */}
            <div className={`transition-all duration-300 space-y-4 sm:space-y-6 overflow-y-auto ${chatOpen ? 'lg:flex-1' : 'w-full'}`}>
              {/* Tab Navigation */}
              <div className="card p-2 backdrop-blur bg-white/80">
                <div className="flex space-x-1">
                  <button
                    onClick={() => setActiveTab('single')}
                    className={`flex-1 px-4 py-3 rounded-lg font-medium transition-all ${
                      activeTab === 'single'
                        ? 'bg-blue-600 text-white shadow-lg'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    <div className="flex items-center justify-center space-x-2">
                      <Icons.ChartPie className="w-5 h-5" />
                      <span>Single Analysis</span>
                    </div>
                  </button>
                  <button
                    onClick={() => setActiveTab('bulk')}
                    className={`flex-1 px-4 py-3 rounded-lg font-medium transition-all ${
                      activeTab === 'bulk'
                        ? 'bg-blue-600 text-white shadow-lg'
                        : 'text-slate-600 hover:bg-slate-100'
                    }`}
                  >
                    <div className="flex items-center justify-center space-x-2">
                      <Icons.List className="w-5 h-5" />
                      <span>Bulk Ranking</span>
                    </div>
                  </button>
                </div>
              </div>

              {/* Single Analysis Form */}
              {activeTab === 'single' && (
                <>
                  <section className="card p-4 sm:p-6 backdrop-blur bg-white/80 dark:bg-slate-900/80" aria-labelledby="analyze-title">
                    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
                      <h2 id="analyze-title" className="text-base sm:text-lg font-medium">Analyze Stocks</h2>
                      {latency !== null && <span className="text-xs text-slate-600" aria-live="polite">API latency: {latency} ms</span>}
                    </div>
                <form onSubmit={submit} className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4 sm:gap-6" role="form" aria-describedby={error ? 'form-error' : undefined}>
                  <Field id="country" label="Country" hint="Select the stock market">
                    <select 
                      id="country" 
                      className="input" 
                      value={country} 
                      onChange={(e) => setCountry(e.target.value)} 
                      disabled={loading}
                      aria-describedby="country-hint"
                    >
                      {countries.map((c) => (
                        <option key={c} value={c}>{c}</option>
                      ))}
                    </select>
                  </Field>
                  <Field id="tickers" label="Tickers (comma-separated)" hint={`Examples: ${country === 'India' ? 'JIOFIN, BAJFINANCE' : 'AAPL, MSFT'}`}>
                    <input 
                      id="tickers" 
                      className="input" 
                      value={tickers} 
                      onChange={(e) => setTickers(e.target.value)} 
                      placeholder={country === 'India' ? 'JIOFIN, BAJFINANCE' : 'AAPL, MSFT'} 
                      disabled={loading} 
                      aria-describedby="tickers-hint" 
                    />
                  </Field>
                  <Field id="hs" label="Short-term (days)">
                    <input id="hs" type="number" min={1} max={365} className="input" value={hs} onChange={(e) => setHs(parseInt(e.target.value || '0'))} disabled={loading} />
                  </Field>
                  <Field id="hl" label="Long-term (days)">
                    <input id="hl" type="number" min={30} max={1825} className="input" value={hl} onChange={(e) => setHl(parseInt(e.target.value || '0'))} disabled={loading} />
                  </Field>
                  <div className="md:col-span-4 flex items-center gap-3">
                    <button 
                      type="submit" 
                      className="btn-primary flex items-center gap-2" 
                      disabled={loading} 
                      aria-busy={loading}
                    >
                      {loading && <Spinner size="sm" />}
                      {loading ? 'Analyzing...' : 'Analyze'}
                    </button>
                    <button 
                      type="button" 
                      className="rounded-lg border px-3 py-2 text-sm hover:bg-gray-50 transition-colors" 
                      onClick={() => { setTickers(''); setData(null); setError(null); }}
                      disabled={loading}
                    >
                      Clear
                    </button>
                  </div>
                </form>
                
                {/* Progress Bar */}
                {loading && analysisProgress > 0 && (
                  <div className="mt-4">
                    <ProgressBar 
                      progress={analysisProgress} 
                      className="mb-2" 
                      showPercentage={false}
                    />
                    <p className="text-sm text-gray-600 text-center">
                      Analyzing {tickers.split(',').map(t => t.trim()).join(', ')}...
                    </p>
                  </div>
                )}
                
                {/* Enhanced Error Display */}
                {error && (
                  <div className="mt-4">
                    <ErrorState
                      type={errorType}
                      message={error}
                      onRetry={() => submit()}
                      className="min-h-[120px]"
                    />
                  </div>
                )}
              </section>

              {!data && !loading && !error && (
                <section className="text-center text-slate-500 py-12">
                  <div className="max-w-md mx-auto">
                    <Icons.TrendingUp className="w-16 h-16 mx-auto mb-4 text-slate-300" />
                    <h3 className="text-lg font-medium mb-2">Start Your Analysis</h3>
                    <p>Enter one or more tickers to get an comprehensive AI-powered research report.</p>
                  </div>
                </section>
              )}

              {/* Results with Loading Overlay */}
              <LoadingOverlay 
                isLoading={loading} 
                message={`Analyzing ${tickers.split(',').map(t => t.trim()).join(', ')}...`}
              >
                {data && data.reports && data.reports.map((r: any) => (
                  <ErrorBoundary key={r.ticker}>
                    <section className="space-y-6">
                      <ResultSummaryGrid report={r} />
                    </section>
                  </ErrorBoundary>
                ))}
              </LoadingOverlay>
                </>
              )}

              {/* Bulk Analysis Tab */}
              {activeTab === 'bulk' && (
                <>
                  <BulkStockInput
                    onAnalyze={handleBulkAnalyze}
                    loading={bulkLoading}
                  />
                  
                  {rankedStocks.length > 0 && (
                    <RankedStockList
                      stocks={rankedStocks}
                      mode={bulkMode}
                      loading={bulkLoading}
                    />
                  )}
                </>
              )}
            </div>

            {/* Chat Panel */}
            {chatOpen && (
              <div className="w-96 flex-shrink-0">
                <div className="h-full bg-white/80 dark:bg-slate-900/80 backdrop-blur rounded-xl shadow-lg overflow-hidden">
                  <ErrorBoundary>
                    <ChatInterface 
                      analysisContext={{
                        tickers: tickers.split(',').map(t => t.trim()),
                        data: data,
                        latency: latency
                      }}
                    />
                  </ErrorBoundary>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}

// Main App component with providers
export default function App({ chatOpen, currentView, onViewChange }: AppProps) {
  return (
    <ErrorBoundary>
      <ToastProvider>
        {/* <AuthProvider>  Disabled for now */}
          <AppContent chatOpen={chatOpen} currentView={currentView} onViewChange={onViewChange} />
        {/* </AuthProvider> */}
      </ToastProvider>
    </ErrorBoundary>
  )
}