import { motion } from 'framer-motion'
import { TrendingUp, TrendingDown, Star, Shield } from 'lucide-react'

interface ProfessionalHeaderProps {
  ticker: string; action: string; rating: number; confidence: number;
  currentPrice: number; priceChange: number; marketCap?: number
}

function getActionColor(action: string) {
  const a = action.toLowerCase()
  if (a.includes('buy')) return 'green'
  if (a.includes('sell')) return 'red'
  return 'amber'
}

const ACTION_STYLES: Record<string, string> = {
  green: 'bg-green-50 dark:bg-green-900/30 border-green-500 dark:border-green-600',
  red:   'bg-red-50 dark:bg-red-900/30 border-red-500 dark:border-red-600',
  amber: 'bg-amber-50 dark:bg-amber-900/30 border-amber-500 dark:border-amber-600',
}

const ACTION_TEXT: Record<string, string> = {
  green: 'text-green-900 dark:text-green-200',
  red:   'text-red-900 dark:text-red-200',
  amber: 'text-amber-900 dark:text-amber-200',
}

const confidenceColor = (c: number) =>
  c >= 80 ? 'bg-green-600' : c >= 60 ? 'bg-blue-600' : c >= 40 ? 'bg-amber-600' : 'bg-red-600'

export function ProfessionalHeader({ ticker, action, rating, confidence, currentPrice, priceChange, marketCap }: ProfessionalHeaderProps) {
  const color = getActionColor(action)
  const isPositive = priceChange >= 0

  return (
    <motion.div initial={{ opacity: 0, y: -20 }} animate={{ opacity: 1, y: 0 }}
      className="bg-gradient-to-r from-slate-50 to-slate-100 dark:from-slate-800 dark:to-slate-900 border-2 border-slate-200 dark:border-slate-700 rounded-2xl p-8 shadow-2xl mb-6">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
        {/* Left: Ticker & Price */}
        <div className="flex-1">
          <div className="flex items-center gap-4 mb-3">
            <h1 className="text-4xl font-extrabold text-slate-950 dark:text-slate-50">{ticker}</h1>
            <div className={`px-4 py-2 rounded-lg border-2 ${ACTION_STYLES[color]}`}>
              <span className={`text-sm font-extrabold uppercase tracking-wider ${ACTION_TEXT[color]}`}>{action}</span>
            </div>
          </div>
          <div className="flex items-baseline gap-4">
            <span className="text-5xl font-extrabold text-slate-950 dark:text-slate-50 font-mono">
              ₹{currentPrice.toLocaleString('en-IN', { maximumFractionDigits: 2 })}
            </span>
            <div className={`flex items-center gap-1 ${isPositive ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}`}>
              {isPositive ? <TrendingUp className="w-6 h-6" /> : <TrendingDown className="w-6 h-6" />}
              <span className="text-2xl font-bold">{isPositive ? '+' : ''}{priceChange.toFixed(2)}%</span>
            </div>
          </div>
          {marketCap && <p className="mt-2 text-sm font-semibold text-slate-600 dark:text-slate-400">Market Cap: ₹{(marketCap / 1e7).toFixed(2)} Cr</p>}
        </div>

        {/* Right: Rating & Confidence */}
        <div className="flex flex-col lg:flex-row gap-6">
          <div className="bg-white dark:bg-slate-800 border-2 border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-lg min-w-[200px]">
            <div className="flex items-center gap-2 mb-3">
              <Star className="w-5 h-5 text-amber-500" />
              <span className="text-sm font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Rating</span>
            </div>
            <div className="flex items-center gap-2 mb-2">
              {[...Array(5)].map((_, i) => (
                <Star key={i} className={`w-7 h-7 ${
                  i < Math.floor(rating) ? 'fill-amber-500 text-amber-500'
                  : i < rating ? 'fill-amber-300 text-amber-300'
                  : 'fill-slate-200 text-slate-200 dark:fill-slate-700 dark:text-slate-700'}`} />
              ))}
            </div>
            <p className="text-2xl font-extrabold text-slate-950 dark:text-slate-50">{rating.toFixed(1)}/5.0</p>
          </div>

          <div className="bg-white dark:bg-slate-800 border-2 border-slate-200 dark:border-slate-700 rounded-xl p-6 shadow-lg min-w-[200px]">
            <div className="flex items-center gap-2 mb-3">
              <Shield className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              <span className="text-sm font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wider">Confidence</span>
            </div>
            <div className="relative w-full h-3 bg-slate-200 dark:bg-slate-700 rounded-full mb-2">
              <motion.div initial={{ width: 0 }} animate={{ width: `${confidence}%` }} transition={{ duration: 1, ease: 'easeOut' }}
                className={`absolute left-0 top-0 h-full rounded-full ${confidenceColor(confidence)}`} />
            </div>
            <p className="text-2xl font-extrabold text-slate-950 dark:text-slate-50">{confidence.toFixed(0)}%</p>
          </div>
        </div>
      </div>
    </motion.div>
  )
}
