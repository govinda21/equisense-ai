import { motion } from 'framer-motion'
import { Target } from 'lucide-react'

interface ValuationVisualizationProps {
  currentPrice: number
  intrinsicValue?: number
  priceTarget?: number
  entryZoneLow?: number
  entryZoneHigh?: number
  stopLoss?: number
  ticker?: string
}

function formatAmountByCurrency(value?: number, ticker?: string): string {
  if (value === undefined || value === null || isNaN(Number(value)) || value === 0) return '—'
  const symbol = ticker?.endsWith('.NS') || ticker?.endsWith('.BO') ? '₹' : '$'
  const v = Number(value)
  
  if (symbol === '₹') {
    const abs = Math.abs(v)
    if (abs >= 1e7) return `₹${(v / 1e7).toFixed(1)} Cr`
    if (abs >= 1e5) return `₹${(v / 1e5).toFixed(1)} L`
    return `₹${v.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`
  }
  
  const abs = Math.abs(v)
  if (abs >= 1e12) return `${symbol}${(v / 1e12).toFixed(1)}T`
  if (abs >= 1e9) return `${symbol}${(v / 1e9).toFixed(1)}B`
  if (abs >= 1e6) return `${symbol}${(v / 1e6).toFixed(1)}M`
  return `${symbol}${v.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
}

export function ValuationVisualization({
  currentPrice,
  intrinsicValue,
  priceTarget,
  entryZoneLow,
  entryZoneHigh,
  stopLoss,
  ticker
}: ValuationVisualizationProps) {
  // Calculate min and max for scale
  const allValues = [currentPrice, intrinsicValue, priceTarget, entryZoneLow, entryZoneHigh, stopLoss]
    .filter(v => v !== undefined && v !== null && v > 0) as number[]
  
  if (allValues.length === 0) return null
  
  const minValue = Math.min(...allValues)
  const maxValue = Math.max(...allValues)
  const range = maxValue - minValue || 1
  
  // Calculate positions as percentages
  const getPosition = (value?: number) => {
    if (!value || value <= 0) return 0
    return ((value - minValue) / range) * 100
  }
  
  const currentPos = getPosition(currentPrice)
  const intrinsicPos = getPosition(intrinsicValue)
  const targetPos = getPosition(priceTarget)
  const entryLowPos = getPosition(entryZoneLow)
  const entryHighPos = getPosition(entryZoneHigh)
  const stopLossPos = getPosition(stopLoss)
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-slate-900 border-2 border-slate-300 dark:border-slate-600 rounded-xl p-6 shadow-xl"
    >
      <h3 className="text-lg font-extrabold text-slate-900 dark:text-slate-50 mb-6 flex items-center gap-2">
        <Target className="w-5 h-5 text-slate-800 dark:text-slate-200" />
        Valuation Snapshot
      </h3>
      
      <div className="space-y-6">
        {/* Visual Bar */}
        <div className="relative">
          <div className="h-8 bg-slate-200 dark:bg-slate-700 rounded-lg relative overflow-hidden border border-slate-300 dark:border-slate-600">
            {/* Intrinsic Value */}
            {intrinsicValue && (
              <div
                className="absolute h-full bg-green-500 dark:bg-green-600 opacity-30"
                style={{ left: '0%', width: `${intrinsicPos}%` }}
              />
            )}
            
            {/* Entry Zone */}
            {entryZoneLow && entryZoneHigh && (
              <div
                className="absolute h-full bg-blue-500 dark:bg-blue-600 opacity-40"
                style={{ left: `${entryLowPos}%`, width: `${entryHighPos - entryLowPos}%` }}
              />
            )}
            
            {/* Stop Loss */}
            {stopLoss && (
              <div
                className="absolute h-full bg-red-500 dark:bg-red-600 opacity-30"
                style={{ left: '0%', width: `${stopLossPos}%` }}
              />
            )}
            
            {/* Price Target */}
            {priceTarget && (
              <div
                className="absolute h-full bg-purple-500 dark:bg-purple-600 opacity-30"
                style={{ left: '0%', width: `${targetPos}%` }}
              />
            )}
            
            {/* Current Price Indicator */}
            <div
              className="absolute top-0 h-full w-1.5 bg-slate-900 dark:bg-slate-100 z-10 shadow-lg"
              style={{ left: `${currentPos}%` }}
            >
              <div className="absolute -top-2 left-1/2 transform -translate-x-1/2">
                <div className="w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-slate-900 dark:border-t-slate-100"></div>
              </div>
              <div className="absolute -bottom-7 left-1/2 transform -translate-x-1/2 whitespace-nowrap text-xs font-bold text-slate-900 dark:text-slate-100 bg-white dark:bg-slate-800 px-2 py-1 rounded border border-slate-300 dark:border-slate-600">
                You are here
              </div>
            </div>
          </div>
        </div>
        
        {/* Labels */}
        <div className="space-y-3">
          {/* Current Price */}
          <div className="flex items-center justify-between bg-slate-100 dark:bg-slate-800 p-4 rounded-lg border-2 border-slate-300 dark:border-slate-600 shadow-sm">
            <div className="flex items-center gap-2">
              <div className="w-4 h-4 bg-slate-900 dark:bg-slate-100 rounded border-2 border-white dark:border-slate-900"></div>
              <span className="text-sm font-extrabold text-slate-900 dark:text-slate-50">Current Price</span>
            </div>
            <span className="text-lg font-extrabold text-slate-900 dark:text-white font-mono">
              {formatAmountByCurrency(currentPrice, ticker)}
            </span>
          </div>
          
          {/* Intrinsic Value */}
          {intrinsicValue && (
            <div className="flex items-center justify-between bg-green-100 dark:bg-green-900/40 p-4 rounded-lg border-2 border-green-400 dark:border-green-600 shadow-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-green-700 dark:bg-green-400 rounded border-2 border-white dark:border-slate-900"></div>
                <span className="text-sm font-extrabold text-green-900 dark:text-green-100">Intrinsic Value</span>
              </div>
              <span className="text-base font-extrabold text-green-900 dark:text-green-200 font-mono">
                {formatAmountByCurrency(intrinsicValue, ticker)}
              </span>
            </div>
          )}
          
          {/* Price Target */}
          {priceTarget && (
            <div className="flex items-center justify-between bg-purple-100 dark:bg-purple-900/40 p-4 rounded-lg border-2 border-purple-400 dark:border-purple-600 shadow-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-purple-700 dark:bg-purple-400 rounded border-2 border-white dark:border-slate-900"></div>
                <span className="text-sm font-extrabold text-purple-900 dark:text-purple-100">Analyst Target</span>
              </div>
              <span className="text-base font-extrabold text-purple-900 dark:text-purple-200 font-mono">
                {formatAmountByCurrency(priceTarget, ticker)}
              </span>
            </div>
          )}
          
          {/* Entry Zone */}
          {entryZoneLow && entryZoneHigh && (
            <div className="flex items-center justify-between bg-blue-100 dark:bg-blue-900/40 p-4 rounded-lg border-2 border-blue-400 dark:border-blue-600 shadow-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-blue-700 dark:bg-blue-400 rounded border-2 border-white dark:border-slate-900"></div>
                <span className="text-sm font-extrabold text-blue-900 dark:text-blue-100">Entry Zone</span>
              </div>
              <span className="text-base font-extrabold text-blue-900 dark:text-blue-200 font-mono">
                {formatAmountByCurrency(entryZoneLow, ticker)} – {formatAmountByCurrency(entryZoneHigh, ticker)}
              </span>
            </div>
          )}
          
          {/* Stop Loss */}
          {stopLoss && (
            <div className="flex items-center justify-between bg-red-100 dark:bg-red-900/40 p-4 rounded-lg border-2 border-red-400 dark:border-red-600 shadow-sm">
              <div className="flex items-center gap-2">
                <div className="w-4 h-4 bg-red-700 dark:bg-red-400 rounded border-2 border-white dark:border-slate-900"></div>
                <span className="text-sm font-extrabold text-red-900 dark:text-red-100">Stop Loss</span>
              </div>
              <span className="text-base font-extrabold text-red-900 dark:text-red-200 font-mono">
                {formatAmountByCurrency(stopLoss, ticker)}
              </span>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  )
}

