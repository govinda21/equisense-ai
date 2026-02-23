import { motion } from 'framer-motion'
import { TrendingUp, AlertTriangle } from 'lucide-react'

interface Scenario {
  name: string
  probability: number
  intrinsic_value: number
}

interface ScenarioVisualizationProps {
  scenarios: Scenario[]
  currentPrice: number
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

function calculateReturn(intrinsicValue: number, currentPrice: number): number {
  return ((intrinsicValue - currentPrice) / currentPrice) * 100
}

function calculateExpectedReturn(scenarios: Scenario[], currentPrice: number): number {
  return scenarios.reduce((sum, s) => {
    const returnPct = calculateReturn(s.intrinsic_value, currentPrice)
    return sum + (returnPct * s.probability / 100)
  }, 0)
}

export function ScenarioVisualization({ scenarios, currentPrice, ticker }: ScenarioVisualizationProps) {
  if (!scenarios || scenarios.length === 0) return null
  
  // Sort scenarios by intrinsic value (highest first for visual)
  const sortedScenarios = [...scenarios].sort((a, b) => b.intrinsic_value - a.intrinsic_value)
  
  // Find max value for scale
  const maxValue = Math.max(...sortedScenarios.map(s => s.intrinsic_value), currentPrice)
  const minValue = Math.min(...sortedScenarios.map(s => s.intrinsic_value), currentPrice)
  const range = maxValue - minValue || 1
  
  const expectedReturn = calculateExpectedReturn(scenarios, currentPrice)
  const negativeProbability = scenarios.reduce((sum, s) => {
    const returnPct = calculateReturn(s.intrinsic_value, currentPrice)
    return returnPct < 0 ? sum + s.probability : sum
  }, 0)
  
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-slate-900 border-2 border-slate-300 dark:border-slate-600 rounded-xl p-6 shadow-xl"
    >
      <h3 className="text-2xl font-extrabold text-black dark:text-white mb-6 flex items-center gap-3 tracking-tight">
        <TrendingUp className="w-7 h-7 text-black dark:text-slate-200" />
        <span>DCF Scenario Analysis</span>
      </h3>
      
      <div className="space-y-4">
        {sortedScenarios.map((scenario, index) => {
          const returnPct = calculateReturn(scenario.intrinsic_value, currentPrice)
          const barWidth = ((scenario.intrinsic_value - minValue) / range) * 100
          const isPositive = returnPct >= 0
          
          return (
            <div key={scenario.name} className="space-y-3 bg-white dark:bg-slate-800 p-5 rounded-lg border-2 border-slate-300 dark:border-slate-600 shadow-md">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className={`w-6 h-6 rounded-full border-2 border-white dark:border-slate-900 shadow-md ${
                    scenario.name === 'Bull' ? 'bg-green-600 dark:bg-green-400' :
                    scenario.name === 'Bear' ? 'bg-red-600 dark:bg-red-400' :
                    'bg-blue-600 dark:bg-blue-400'
                  }`}></div>
                  <div>
                    <div className="font-extrabold text-black dark:text-white text-lg">
                      {scenario.name} Case
                    </div>
                    <div className="text-sm font-semibold text-slate-800 dark:text-slate-400">
                      {scenario.probability}% probability
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-extrabold text-xl text-black dark:text-white mb-1">
                    {formatAmountByCurrency(scenario.intrinsic_value, ticker)}
                  </div>
                  <div className={`text-base font-extrabold ${
                    isPositive ? 'text-green-900 dark:text-green-300' : 'text-red-900 dark:text-red-300'
                  }`}>
                    {isPositive ? '+' : ''}{returnPct.toFixed(1)}%
                  </div>
                </div>
              </div>
              
              {/* Visual Bar */}
              <div className="w-full bg-gray-300 dark:bg-gray-500 rounded-full h-4 relative border border-gray-400 dark:border-gray-400">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${barWidth}%` }}
                  transition={{ duration: 0.8, delay: index * 0.1 }}
                  className={`h-full rounded-full shadow-md ${
                    scenario.name === 'Bull' ? 'bg-green-600 dark:bg-green-400' :
                    scenario.name === 'Bear' ? 'bg-red-600 dark:bg-red-400' :
                    'bg-blue-600 dark:bg-blue-400'
                  }`}
                ></motion.div>
              </div>
            </div>
          )
        })}
      </div>
      
      {/* Summary */}
      <div className="mt-6 pt-4 border-t-2 border-slate-300 dark:border-slate-500 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-extrabold text-black dark:text-white">📈 Expected Return:</span>
          <span className={`text-base font-extrabold ${
            expectedReturn >= 0 ? 'text-green-900 dark:text-green-300' : 'text-red-900 dark:text-red-300'
          }`}>
            {expectedReturn >= 0 ? '+' : ''}{expectedReturn.toFixed(1)}% (Probability-Weighted)
          </span>
        </div>
        
        {negativeProbability > 50 && (
          <div className="flex items-center gap-2 text-sm font-bold text-amber-950 dark:text-amber-100 bg-amber-50 dark:bg-amber-900/50 p-3 rounded-lg border-2 border-amber-400 dark:border-amber-600 shadow-sm">
            <AlertTriangle className="w-4 h-4" />
            <span>⚠️ Risk: {negativeProbability.toFixed(0)}% probability of negative returns</span>
          </div>
        )}
      </div>
    </motion.div>
  )
}

