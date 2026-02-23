import { Line } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Tooltip, Legend, Filler)

interface TechnicalChartProps {
  labels: string[]
  closes: number[]
  indicators?: {
    sma20?: number
    sma50?: number
    sma200?: number
    bollinger?: {
      upper: number
      middle: number
      lower: number
    }
    rsi14?: number
    macd?: {
      macd: number
      signal: number
      hist: number
    }
  }
  signals?: {
    regime: string
    score: number
  }
}

export function TechnicalChart({ labels, closes, indicators, signals }: TechnicalChartProps) {
  // Calculate proper moving averages from price data
  const calculateSMA = (data: number[], period: number): number[] => {
    const sma: number[] = []
    for (let i = 0; i < data.length; i++) {
      if (i < period - 1) {
        sma.push(NaN) // Not enough data points
      } else {
        const sum = data.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0)
        sma.push(sum / period)
      }
    }
    return sma
  }

  // Calculate Bollinger Bands
  const calculateBollingerBands = (data: number[], period: number = 20, stdDev: number = 2): { upper: number[], middle: number[], lower: number[] } => {
    const sma20 = calculateSMA(data, period)
    const upper: number[] = []
    const middle = sma20
    const lower: number[] = []

    for (let i = 0; i < data.length; i++) {
      if (i < period - 1) {
        upper.push(NaN)
        lower.push(NaN)
      } else {
        const slice = data.slice(i - period + 1, i + 1)
        const mean = sma20[i]
        const variance = slice.reduce((acc, price) => acc + Math.pow(price - mean, 2), 0) / period
        const standardDeviation = Math.sqrt(variance)
        
        upper.push(mean + (stdDev * standardDeviation))
        lower.push(mean - (stdDev * standardDeviation))
      }
    }

    return { upper, middle, lower }
  }

  // Calculate proper moving averages
  const sma20Data = calculateSMA(closes, 20)
  const sma50Data = calculateSMA(closes, 50)
  const sma200Data = calculateSMA(closes, 200)
  
  // Calculate Bollinger Bands
  const bollingerBands = calculateBollingerBands(closes, 20, 2)

  const data = {
    labels,
    datasets: [
      // Price line
      {
        label: 'Price',
        data: closes,
        borderColor: '#1e40af',
        backgroundColor: 'rgba(30, 64, 175, 0.1)',
        pointRadius: 0,
        pointHoverRadius: 4,
        borderWidth: 2,
        tension: 0.1,
        fill: true,
        order: 1,
      },
      // SMA 20
      {
        label: 'SMA 20',
        data: sma20Data,
        borderColor: '#f59e0b',
        backgroundColor: 'transparent',
        pointRadius: 0,
        pointHoverRadius: 3,
        borderWidth: 1.5,
        borderDash: [5, 5],
        tension: 0,
        order: 2,
      },
      // SMA 50
      {
        label: 'SMA 50',
        data: sma50Data,
        borderColor: '#10b981',
        backgroundColor: 'transparent',
        pointRadius: 0,
        pointHoverRadius: 3,
        borderWidth: 1.5,
        borderDash: [5, 5],
        tension: 0,
        order: 2,
      },
      // SMA 200
      {
        label: 'SMA 200',
        data: sma200Data,
        borderColor: '#8b5cf6',
        backgroundColor: 'transparent',
        pointRadius: 0,
        pointHoverRadius: 3,
        borderWidth: 2,
        borderDash: [10, 5],
        tension: 0,
        order: 2,
      },
      // Bollinger Upper Band
      {
        label: 'BB Upper',
        data: bollingerBands.upper,
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        pointRadius: 0,
        pointHoverRadius: 2,
        borderWidth: 1,
        borderDash: [3, 3],
        tension: 0,
        fill: '+1',
        order: 3,
      },
      // Bollinger Lower Band
      {
        label: 'BB Lower',
        data: bollingerBands.lower,
        borderColor: '#ef4444',
        backgroundColor: 'rgba(239, 68, 68, 0.1)',
        pointRadius: 0,
        pointHoverRadius: 2,
        borderWidth: 1,
        borderDash: [3, 3],
        tension: 0,
        fill: false,
        order: 3,
      },
    ],
  }

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      intersect: false,
      mode: 'index' as const,
    },
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
        labels: {
          usePointStyle: true,
          padding: 12,
          font: {
            size: 12,
            weight: 500 as any,
          },
          filter: (legendItem: any) => {
            // Only show legend for main indicators
            return ['Price', 'SMA 20', 'SMA 50', 'SMA 200', 'BB Upper', 'BB Lower'].includes(legendItem.text)
          },
        },
      },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        titleColor: '#f8fafc',
        bodyColor: '#f8fafc',
        borderColor: 'rgba(148, 163, 184, 0.2)',
        borderWidth: 1,
        cornerRadius: 12,
        displayColors: true,
        padding: 12,
        titleFont: {
          size: 13,
          weight: 600 as any,
        },
        bodyFont: {
          size: 12,
        },
        callbacks: {
          title: (context: any) => {
            const index = context[0].dataIndex
            const date = labels[index]
            if (date) {
              return new Date(date).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric'
              })
            }
            return `Point ${index + 1}`
          },
          label: (context: any) => {
            const label = context.dataset.label || 'Data'
            const value = context.parsed.y
            if (isNaN(value)) return `${label}: —`
            const formattedValue = typeof value === 'number' ? value.toFixed(2) : value
            return `${label}: ${formattedValue}`
          },
        },
      },
    },
    scales: {
      x: {
        display: true,
        grid: {
          display: true,
          color: 'rgba(148, 163, 184, 0.1)',
          drawBorder: false,
        },
        ticks: {
          maxTicksLimit: 6,
          font: {
            size: 11,
            color: '#64748b',
          },
          callback: function(_value: any, index: number) {
            const label = labels[index]
            if (label) {
              return new Date(label).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
            }
            return ''
          },
        },
        border: {
          display: false,
        },
      },
      y: {
        display: true,
        grid: {
          display: true,
          color: 'rgba(148, 163, 184, 0.1)',
          drawBorder: false,
        },
        ticks: {
          font: {
            size: 11,
            color: '#64748b',
          },
          callback: function(value: any) {
            if (typeof value === 'number') {
              return value.toFixed(0)
            }
            return value
          },
        },
        border: {
          display: false,
        },
      },
    },
    elements: {
      point: {
        hoverRadius: 8,
        hoverBorderWidth: 2,
        hoverBorderColor: '#ffffff',
      },
      line: {
        tension: 0.1,
      },
    },
  }

  return (
    <div className="h-96 bg-gradient-to-br from-slate-50 to-white rounded-xl border border-slate-200 shadow-sm p-6">
      <div className="h-full">
        <Line data={data} options={options} />
      </div>
      
      {/* Technical Summary */}
      {signals && (
        <div className="mt-4 flex items-center justify-between text-sm bg-slate-50 rounded-lg p-3">
          <div className="flex items-center space-x-4">
            <div className={`px-3 py-1.5 rounded-full text-xs font-semibold ${
              signals.regime === 'bull' ? 'bg-green-100 text-green-800 border border-green-200' :
              signals.regime === 'bear' ? 'bg-red-100 text-red-800 border border-red-200' :
              'bg-gray-100 text-gray-800 border border-gray-200'
            }`}>
              {signals.regime?.toUpperCase()} Market
            </div>
            <div className="text-slate-700 font-medium">
              Score: <span className="font-bold text-slate-900">{(signals.score * 100).toFixed(0)}%</span>
            </div>
          </div>
          
          {/* Key Technical Levels */}
          <div className="flex items-center space-x-4 text-xs text-slate-600">
            {indicators?.sma20 && (
              <div className="flex items-center">
                <div className="w-4 h-0.5 bg-amber-500 mr-2 rounded"></div>
                <span className="font-medium">SMA20: {indicators.sma20.toFixed(0)}</span>
              </div>
            )}
            {indicators?.sma50 && (
              <div className="flex items-center">
                <div className="w-4 h-0.5 bg-emerald-500 mr-2 rounded"></div>
                <span className="font-medium">SMA50: {indicators.sma50.toFixed(0)}</span>
              </div>
            )}
            {indicators?.sma200 && (
              <div className="flex items-center">
                <div className="w-4 h-0.5 bg-purple-500 mr-2 rounded"></div>
                <span className="font-medium">SMA200: {indicators.sma200.toFixed(0)}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
