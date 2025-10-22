import React, { useState, useEffect } from 'react';
import { AdvancedChart } from './AdvancedChart';
// import { UserProfile } from './Auth';  // Disabled for now
// import { useAuth } from './Auth';  // Disabled for now

interface MarketData {
  ticker: string;
  price: number;
  change: number;
  change_percent: number;
  volume: number;
  market_cap: number;
}

interface SectorData {
  name: string;
  ticker: string;
  price: number;
  change: number;
  change_percent: number;
  volume: number;
}

interface ChartData {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export const EnhancedDashboard: React.FC = () => {
  // const { user } = useAuth();  // Disabled for now
  const user = { full_name: 'User' };  // Mock user
  const [marketData, setMarketData] = useState<MarketData[]>([]);
  const [sectorData, setSectorData] = useState<SectorData[]>([]);
  const [chartData, setChartData] = useState<ChartData[]>([]);
  const [selectedTicker, setSelectedTicker] = useState('NIFTY50.NS');
  const [timeframe, setTimeframe] = useState('1M');
  const [indicators, setIndicators] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [marketResponse, sectorResponse] = await Promise.all([
        fetch('/realtime/market-overview'),
        fetch('/realtime/sector-performance')
      ]);

      if (marketResponse.ok) {
        const marketData = await marketResponse.json();
        setMarketData(Object.entries(marketData.indices).map(([ticker, data]: [string, any]) => ({
          ticker,
          ...data
        })));
      }

      if (sectorResponse.ok) {
        const sectorData = await sectorResponse.json();
        setSectorData(Object.entries(sectorData.sectors).map(([name, data]: [string, any]) => ({
          name,
          ...data
        })));
      }

      // Fetch chart data for default ticker
      await fetchChartData(selectedTicker, timeframe);

    } catch (err) {
      setError('Failed to fetch dashboard data');
      console.error('Dashboard data fetch error:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchChartData = async (_ticker: string, _timeframe: string) => {
    try {
      // Mock chart data - in real implementation, this would come from your API
      const mockData: ChartData[] = Array.from({ length: 30 }, (_, i) => ({
        timestamp: Date.now() - (29 - i) * 24 * 60 * 60 * 1000,
        open: 100 + Math.random() * 20,
        high: 110 + Math.random() * 20,
        low: 90 + Math.random() * 20,
        close: 100 + Math.random() * 20,
        volume: Math.floor(Math.random() * 1000000)
      }));
      setChartData(mockData);
    } catch (err) {
      console.error('Chart data fetch error:', err);
    }
  };

  const handleTimeframeChange = (newTimeframe: string) => {
    setTimeframe(newTimeframe);
    fetchChartData(selectedTicker, newTimeframe);
  };

  const handleIndicatorAdd = (indicator: string) => {
    const newIndicator = {
      name: indicator,
      data: Array.from({ length: 30 }, () => Math.random() * 100),
      color: '#3B82F6',
      type: 'line' as const
    };
    setIndicators([...indicators, newIndicator]);
  };

  const handleIndicatorRemove = (indicatorName: string) => {
    setIndicators(indicators.filter(ind => ind.name !== indicatorName));
  };

  const addToWatchlist = async (ticker: string) => {
    try {
      const response = await fetch('/auth/watchlist', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('auth_token')}`
        },
        body: JSON.stringify({ ticker })
      });

      if (response.ok) {
        // Refresh watchlist or show success message
        console.log(`Added ${ticker} to watchlist`);
      }
    } catch (err) {
      console.error('Error adding to watchlist:', err);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-600 text-xl mb-4">{error}</div>
          <button
            onClick={fetchDashboardData}
            className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">Equisense AI Dashboard</h1>
              <p className="text-sm text-gray-600">Welcome back, {user?.full_name}</p>
            </div>
            <div className="flex items-center space-x-4">
              <button
                onClick={() => addToWatchlist(selectedTicker)}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
              >
                Add to Watchlist
              </button>
              {/* <UserProfile />  Disabled for now */}
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Chart */}
          <div className="lg:col-span-2">
            <AdvancedChart
              ticker={selectedTicker}
              data={chartData}
              indicators={indicators}
              timeframe={timeframe as any}
              onTimeframeChange={handleTimeframeChange}
              onIndicatorAdd={handleIndicatorAdd}
              onIndicatorRemove={handleIndicatorRemove}
            />
          </div>

          {/* Market Overview */}
          <div className="space-y-6">
            {/* Key Indices */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Key Indices</h3>
              <div className="space-y-3">
                {marketData.slice(0, 5).map((index) => (
                  <div
                    key={index.ticker}
                    className={`p-3 rounded-lg cursor-pointer transition-colors ${
                      selectedTicker === index.ticker ? 'bg-blue-50 border-blue-200' : 'bg-gray-50 hover:bg-gray-100'
                    }`}
                    onClick={() => setSelectedTicker(index.ticker)}
                  >
                    <div className="flex justify-between items-center">
                      <div>
                        <div className="font-medium text-sm">{index.ticker}</div>
                        <div className="text-xs text-gray-600">₹{index.price?.toFixed(2) || 'N/A'}</div>
                      </div>
                      <div className={`text-sm font-medium ${
                        (index.change_percent || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {(index.change_percent || 0) >= 0 ? '+' : ''}{(index.change_percent || 0).toFixed(2)}%
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Sector Performance */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Sector Performance</h3>
              <div className="space-y-3">
                {sectorData.slice(0, 8).map((sector) => (
                  <div key={sector.name} className="flex justify-between items-center p-2 hover:bg-gray-50 rounded">
                    <div>
                      <div className="font-medium text-sm">{sector.name}</div>
                      <div className="text-xs text-gray-600">₹{sector.price?.toFixed(2) || 'N/A'}</div>
                    </div>
                    <div className={`text-sm font-medium ${
                      (sector.change_percent || 0) >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {(sector.change_percent || 0) >= 0 ? '+' : ''}{(sector.change_percent || 0).toFixed(2)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Market Status */}
            <div className="bg-white rounded-lg shadow-lg p-6">
              <h3 className="text-lg font-semibold mb-4">Market Status</h3>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">NSE</span>
                  <span className="text-sm font-medium text-green-600">Open</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">BSE</span>
                  <span className="text-sm font-medium text-green-600">Open</span>
                </div>
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
            <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
              <div className="text-center">
                <div className="text-2xl mb-2">📊</div>
                <div className="text-sm font-medium">Stock Analysis</div>
              </div>
            </button>
            <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
              <div className="text-center">
                <div className="text-2xl mb-2">📈</div>
                <div className="text-sm font-medium">Portfolio</div>
              </div>
            </button>
            <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
              <div className="text-center">
                <div className="text-2xl mb-2">🔔</div>
                <div className="text-sm font-medium">Alerts</div>
              </div>
            </button>
            <button className="p-4 border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
              <div className="text-center">
                <div className="text-2xl mb-2">📰</div>
                <div className="text-sm font-medium">News</div>
              </div>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
