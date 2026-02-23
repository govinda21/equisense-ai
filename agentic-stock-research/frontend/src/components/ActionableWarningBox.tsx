import { motion } from 'framer-motion'
import { AlertTriangle, Bell, Eye } from 'lucide-react'

interface Warning {
  type: 'valuation' | 'downside' | 'monitoring'
  severity: 'high' | 'moderate' | 'low'
  title: string
  message: string
  action?: string
  actionLabel?: string
}

interface ActionableWarningBoxProps {
  warnings: Warning[]
  onSetAlert?: (price: number) => void
  onAddToWatchlist?: () => void
}

export function ActionableWarningBox({ warnings, onSetAlert, onAddToWatchlist }: ActionableWarningBoxProps) {
  if (!warnings || warnings.length === 0) return null
  
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high':
        return 'bg-red-50 dark:bg-red-900/60 border-red-400 dark:border-red-600 text-red-950 dark:text-red-50'
      case 'moderate':
        return 'bg-amber-50 dark:bg-amber-900/60 border-amber-400 dark:border-amber-600 text-amber-950 dark:text-amber-50'
      default:
        return 'bg-yellow-50 dark:bg-yellow-900/60 border-yellow-400 dark:border-yellow-600 text-yellow-950 dark:text-yellow-50'
    }
  }
  
  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'high':
        return '🔴'
      case 'moderate':
        return '🟡'
      default:
        return '🟠'
    }
  }
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-slate-900 border-2 border-red-500 dark:border-red-500 rounded-xl p-6 shadow-xl"
    >
      <div className="flex items-center gap-3 mb-5">
        <AlertTriangle className="w-7 h-7 text-red-700 dark:text-red-300" />
        <h3 className="text-xl font-extrabold text-black dark:text-white tracking-tight">
          ⚠️ Valuation Model Warnings
        </h3>
      </div>
      
      <div className="space-y-4">
        {warnings.map((warning, index) => (
          <div
            key={index}
            className={`p-5 rounded-lg border-l-4 ${getSeverityColor(warning.severity)}`}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-xl">{getSeverityIcon(warning.severity)}</span>
                  <span className="font-extrabold text-base uppercase tracking-wider text-inherit">
                    {warning.title}: {warning.severity.toUpperCase()}
                  </span>
                </div>
                <p className="text-base mb-3 font-bold leading-relaxed text-inherit">{warning.message}</p>
                {warning.action && (
                  <p className="text-sm font-extrabold opacity-90 text-inherit">→ {warning.action}</p>
                )}
              </div>
              
              {/* Action Buttons */}
              <div className="flex flex-col gap-2">
                {warning.type === 'downside' && onSetAlert && (
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={() => {
                      // Extract price from message if possible
                      const priceMatch = warning.message.match(/₹([\d,]+\.?\d*)/)
                      if (priceMatch) {
                        const price = parseFloat(priceMatch[1].replace(/,/g, ''))
                        onSetAlert(price)
                      }
                    }}
                    className="flex items-center gap-2 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-xs font-medium rounded-lg transition-colors"
                  >
                    <Bell className="w-3 h-3" />
                    Set Alert
                  </motion.button>
                )}
                
                {warning.type === 'monitoring' && onAddToWatchlist && (
                  <motion.button
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                    onClick={onAddToWatchlist}
                    className="flex items-center gap-2 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded-lg transition-colors"
                  >
                    <Eye className="w-3 h-3" />
                    Add to Watchlist
                  </motion.button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </motion.div>
  )
}

