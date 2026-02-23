import React, { useState, useEffect } from 'react';
import { AdvancedChart } from './AdvancedChart';

interface MarketData { ticker: string; price: number; change: number; change_percent: number; volume: number; market_cap: number }
interface SectorData { name: string; ticker: string; price: number; change: number; change_percent: number; volume: number }
interface ChartData { timestamp: number; open: number; high: number; low: number; close: number; volume: number }

const mockChartData = (): ChartData[] =>
  Array.from({ length: 30 }, (_, i) => ({
    timestamp: Date.now() - (29 - i) * 86400000,
    open: 100 + Math.random() * 20, high: 110 + Math.random() * 20,
    low: 90 + Math.random() * 20, close: 100 + Math.random() * 20,
    volume: Math.floor(Math.random() * 1000000)
  }))

const mockIndicator = (name: string) => ({
  name, data: Array.from({ length: 30 }, () => Math.random() * 100), color: '#3B82F6', type: 'line' as const
})

const PctBadge = ({ pct }: { pct: number }) => (
  <span className={`text-sm font-medium ${pct >= 0 ? 'text-green-600' : 'text-red-600'}`}>
    {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
  </span>
)

export const EnhancedDashboard: React.FC = () => {
  const user = { full_name: 'User' }
  const [marketData, setMarketData] = useState<MarketData[]>([])
  const [sectorData, setSectorData] = useState<SectorData[]>([])
  const [chartData, setChartData] = useState<ChartData[]>([])
  const [selectedTicker, setSelectedTicker] = useState('NIFTY50.NS')
  const [timeframe, setTimeframe] = useState('1M')
  const [indicators, setIndicators] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { fetchDashboardData() }, [])

  const fetchDashboardData = async () => {
    setLoading(true); setError(null)
    try {
      const [marketRes, sectorRes] = await Promise.all([fetch('/realtime/market-overview'), fetch('/realtime/sector-performance')])
      if (marketRes.ok) {
        const d = await marketRes.json()
        setMarketData(Object.entries(d.indices).map(([ticker, data]: [string, any]) => ({ ticker, ...data })))
      }
      if (sectorRes.ok) {
        const d = await sectorRes.json()
        setSectorData(Object.entries(d.sectors).map(([name, data]: [string, any]) => ({ name, ...data })))
      }
      setChartData(mockChartData())
    } catch {
      setError('Failed to fetch dashboard data')
    } finally {
      setLoading(false)
    }
  }

  const handleTimeframeChange = (tf: string) => { setTimeframe(tf); setChartData(mockChartData()) }
  const handleIndicatorAdd = (name: string) => setIndicators(prev => [...prev, mockIndicator(name)])
  const handleIndicatorRemove = (name: string) => setIndicators(prev => prev.filter(i => i.name !== name))

  const addToWatchlist = async (ticker: string) => {
    try {
      await fetch('/auth/watchlist', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${localStorage.getItem('auth_token')}` }, body: JSON.stringify({ ticker }) })
    } catch { console.error('Error adding to watchlist') }
  }

  if (loading) return <div className="min-h-screen flex items-center justify-center"><div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500" /></div>
  if (error) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="text-red-600 text-xl mb-4">{error}</div>
        <button onClick={fetchDashboardData} className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">Retry</button>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Equisense AI Dashboard</h1>
              <p className="text-sm text-gray-600">Welcome back, {user.full_name}</p>
            </div>
            <button onClick={() => addToWatchlist(selectedTicker)} className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors">Add to Watchlist</button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className="lg:col-span-2">
            <AdvancedChart ticker={selectedTicker} data={chartData} indicators={indicators}
              timeframe={timeframe as any} onTimeframeChange={handleTimeframeChange}
              onIndicatorAdd={handleIndicatorAdd} onIndicatorRemove={handleIndicatorRemove} />
          </div>

          <div className="space-y-6">
            {/* Key Indices */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Key Indices</h3>
              <div className="space-y-3">
                {marketData.slice(0, 5).map(idx => (
                  <div key={idx.ticker} onClick={() => setSelectedTicker(idx.ticker)}
                    className={`p-3 rounded-lg cursor-pointer transition-colors ${selectedTicker === idx.ticker ? 'bg-blue-50 border-blue-200' : 'bg-gray-50 hover:bg-gray-100'}`}>
                    <div className="flex justify-between items-center">
                      <div>
                        <div className="font-medium text-sm">{idx.ticker}</div>
                        <div className="text-xs text-gray-600">₹{idx.price?.toFixed(2) || 'N/A'}</div>
                      </div>
                      <PctBadge pct={idx.change_percent || 0} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Sector Performance */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Sector Performance</h3>
              <div className="space-y-3">
                {sectorData.slice(0, 8).map(s => (
                  <div key={s.name} className="flex justify-between items-center p-2 hover:bg-gray-50 rounded">
                    <div>
                      <div className="font-medium text-sm">{s.name}</div>
                      <div className="text-xs text-gray-600">₹{s.price?.toFixed(2) || 'N/A'}</div>
                    </div>
                    <PctBadge pct={s.change_percent || 0} />
                  </div>
                ))}
              </div>
            </div>

            {/* Market Status */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Market Status</h3>
              <div className="space-y-2">
                {['NSE', 'BSE'].map(ex => (
                  <div key={ex} className="flex justify-between">
                    <span className="text-sm text-gray-600">{ex}</span>
                    <span className="text-sm font-medium text-green-600">Open</span>
                  </div>
                ))}
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Last Update</span>
                  <span className="text-sm text-gray-600">{new Date().toLocaleTimeString()}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Actions */}
        <div className="mt-8 bg-white rounded-lg shadow-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Quick Actions</h3>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[['📊', 'Stock Analysis'], ['📈', 'Portfolio'], ['🔔', 'Alerts'], ['📰', 'News']].map(([emoji, label]) => (
              <button key={label} className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
                <div className="text-center">
                  <div className="text-2xl mb-2">{emoji}</div>
                  <div className="text-sm font-medium">{label}</div>
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
