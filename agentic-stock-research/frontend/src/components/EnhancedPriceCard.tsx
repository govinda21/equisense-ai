import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown } from 'lucide-react'

interface EnhancedPriceCardProps {
  ticker: string; currentPrice: number; changePercent?: number;
  intrinsicValue?: number; priceTarget?: number;
  entryZoneLow?: number; entryZoneHigh?: number; stopLoss?: number; tickerSymbol?: string
}

function formatAmountByCurrency(value?: number, ticker?: string): string {
  if (value === undefined || value === null || isNaN(Number(value)) || value === 0) return '—'
  const isIndian = ticker?.endsWith('.NS') || ticker?.endsWith('.BO')
  const symbol = isIndian ? '₹' : '$'
  const v = Number(value), abs = Math.abs(v)
  if (isIndian) {
    if (abs >= 1e7) return `₹${(v / 1e7).toFixed(1)} Cr`
    if (abs >= 1e5) return `₹${(v / 1e5).toFixed(1)} L`
    return `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
  }
  if (abs >= 1e12) return `${symbol}${(v / 1e12).toFixed(1)}T`
  if (abs >= 1e9) return `${symbol}${(v / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `${symbol}${(v / 1e6).toFixed(1)}M`
  return `${symbol}${v.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
}

function getRiskLevel(currentPrice: number, intrinsicValue?: number) {
  if (!intrinsicValue || intrinsicValue <= 0) return { level: 'Moderate', percentage: 50, color: 'bg-yellow-500' }
  const ovPct = ((currentPrice - intrinsicValue) / intrinsicValue) * 100
  if (ovPct > 100) return { level: 'High', percentage: 85, color: 'bg-red-500' }
  if (ovPct > 50)  return { level: 'Moderate-High', percentage: 70, color: 'bg-orange-500' }
  if (ovPct > 0)   return { level: 'Moderate', percentage: 50, color: 'bg-yellow-500' }
  return { level: 'Low', percentage: 30, color: 'bg-green-500' }
}

export function EnhancedPriceCard({ ticker, currentPrice, changePercent = 0, intrinsicValue, tickerSymbol }: EnhancedPriceCardProps) {
  const risk = getRiskLevel(currentPrice, intrinsicValue)
  const isPositive = changePercent >= 0
  const sym = tickerSymbol || ticker

  return (
    <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4 }}
      className="bg-white dark:bg-slate-900 rounded-xl shadow-xl p-6 border-l-4 border-blue-600 dark:border-blue-400 border border-slate-200 dark:border-slate-700">
      <div className="flex justify-between items-start mb-4">
        <div className="flex-1">
          <h2 className="text-2xl font-extrabold text-slate-900 dark:text-slate-50 mb-2">{ticker}</h2>
          <div className="flex items-baseline gap-3">
            <p className="text-4xl font-extrabold text-slate-900 dark:text-white font-mono">
              {formatAmountByCurrency(currentPrice, sym)}
            </p>
            <div className={`flex items-center gap-1 text-lg font-bold ${isPositive ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}`}>
              {isPositive ? <TrendingUp className="w-5 h-5" /> : <TrendingDown className="w-5 h-5" />}
              <span>{isPositive ? '+' : ''}{changePercent.toFixed(2)}%</span>
            </div>
          </div>
        </div>
      </div>

      <div className="border-t-2 border-slate-300 dark:border-slate-600 pt-4 space-y-3">
        {intrinsicValue && (
          <div className="flex justify-between items-center">
            <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">Intrinsic Value:</span>
            <span className="text-lg font-bold text-slate-900 dark:text-slate-50">{formatAmountByCurrency(intrinsicValue, sym)}</span>
            <span className={`text-sm font-bold ${currentPrice > intrinsicValue ? 'text-red-700 dark:text-red-300' : 'text-green-700 dark:text-green-300'}`}>
              ({currentPrice > intrinsicValue ? '-' : '+'}{Math.abs(((currentPrice - intrinsicValue) / intrinsicValue) * 100).toFixed(1)}% {currentPrice > intrinsicValue ? 'overvalued' : 'undervalued'})
            </span>
          </div>
        )}
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">Risk Level:</span>
          <div className="flex items-center gap-2">
            <div className="w-24 h-2.5 bg-gray-300 dark:bg-gray-600 rounded-full border border-gray-400 dark:border-gray-500">
              <div className={`h-full ${risk.color} rounded-full transition-all shadow-sm`} style={{ width: `${risk.percentage}%` }} />
            </div>
            <span className="text-sm font-bold text-slate-900 dark:text-slate-50">{risk.level}</span>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
