import { motion } from 'framer-motion'
import { AlertTriangle, Info } from 'lucide-react'

interface EnhancedRecommendationCardProps {
  action: string; rating: number; confidence: number; conviction: string;
  showWarning?: boolean; warningMessage?: string
}

const getStars = (rating: number) => {
  const full = Math.floor(rating), half = (rating - full) >= 0.5
  return '★'.repeat(full) + (half && full < 5 ? '☆' : '') + '☆'.repeat(5 - full - (half ? 1 : 0))
}

const getRecommendationColor = (action: string) => {
  const n = action?.toLowerCase() || ''
  if (n.includes('buy')) return 'text-green-600 dark:text-green-400'
  if (n.includes('sell')) return 'text-red-600 dark:text-red-400'
  if (n.includes('weak hold')) return 'text-amber-600 dark:text-amber-400'
  if (n.includes('hold')) return 'text-blue-600 dark:text-blue-400'
  return 'text-slate-700 dark:text-slate-300'
}

const getGrade = (r: number) => r >= 4.5 ? 'A+' : r >= 4.0 ? 'A' : r >= 3.5 ? 'B+' : r >= 3.0 ? 'B' : r >= 2.5 ? 'C+' : r >= 2.0 ? 'C' : r >= 1.5 ? 'D+' : 'D'
const getConfidenceLevel = (c: number) => c >= 85 ? 'High' : c >= 70 ? 'Moderate-High' : c >= 55 ? 'Moderate' : c >= 40 ? 'Low-Moderate' : 'Low'

const confidenceBarColor = (c: number) =>
  c >= 80 ? 'bg-green-600 dark:bg-green-500' : c >= 60 ? 'bg-blue-600 dark:bg-blue-500' : c >= 40 ? 'bg-yellow-600 dark:bg-yellow-500' : 'bg-red-600 dark:bg-red-500'

export function EnhancedRecommendationCard({ action, rating, confidence, showWarning = false, warningMessage }: EnhancedRecommendationCardProps) {
  const grade = getGrade(rating)
  const confLevel = getConfidenceLevel(confidence)
  const isWeakHold = action.toLowerCase().includes('weak hold')

  return (
    <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
      className={`relative overflow-hidden bg-white dark:bg-slate-900 border-2 rounded-xl p-6 shadow-xl ${isWeakHold ? 'border-amber-500 dark:border-amber-400' : 'border-slate-300 dark:border-slate-600'}`}>

      {showWarning && isWeakHold && (
        <div className="mb-4 bg-amber-100 dark:bg-amber-900/50 border-l-4 border-amber-600 dark:border-amber-400 p-4 rounded-lg shadow-sm">
          <div className="flex items-start gap-2">
            <AlertTriangle className="w-5 h-5 text-amber-700 dark:text-amber-300 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-bold text-amber-900 dark:text-amber-100">⚠️ {action.toUpperCase()} - Act with Caution</p>
              {warningMessage && <p className="text-xs font-semibold text-amber-900 dark:text-amber-200 mt-1">{warningMessage}</p>}
            </div>
          </div>
        </div>
      )}

      <div className="text-center mb-6">
        <div className={`text-4xl font-extrabold mb-2 ${getRecommendationColor(action)}`}>{action}</div>
        <div className="flex items-center justify-center gap-4">
          <div>
            <div className="text-3xl font-extrabold text-amber-700 dark:text-amber-300 mb-1">{getStars(rating)}</div>
            <div className="text-lg font-bold text-slate-900 dark:text-slate-50">{rating.toFixed(1)}<span className="text-sm font-semibold text-slate-700 dark:text-slate-300">/5.0</span></div>
          </div>
          <div className="h-12 w-px bg-slate-300 dark:bg-slate-600" />
          <div>
            <div className="text-2xl font-extrabold text-slate-900 dark:text-slate-50 mb-1">{grade}</div>
            <div className="text-xs font-semibold text-slate-700 dark:text-slate-300">Grade</div>
          </div>
        </div>
      </div>

      <div className="h-px bg-slate-300 dark:bg-slate-600 mb-4" />

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-slate-800 dark:text-slate-200">Conviction:</span>
          <span className="text-sm font-bold text-slate-900 dark:text-slate-50">{confidence.toFixed(0)}% {confLevel}</span>
        </div>
        <div className="w-full bg-gray-300 dark:bg-gray-600 rounded-full h-3.5 border border-gray-400 dark:border-gray-500">
          <motion.div initial={{ width: 0 }} animate={{ width: `${confidence}%` }} transition={{ duration: 1, ease: 'easeOut' }}
            className={`h-full rounded-full shadow-sm ${confidenceBarColor(confidence)}`} />
        </div>
        <div className="text-xs font-semibold text-slate-700 dark:text-slate-300 text-center">Confidence Level</div>
      </div>

      <div className="mt-4 flex items-center justify-center gap-2 text-xs font-medium text-slate-600 dark:text-slate-400">
        <Info className="w-4 h-4" />
        <span>Confidence based on model agreement and sentiment analysis</span>
      </div>
    </motion.div>
  )
}
