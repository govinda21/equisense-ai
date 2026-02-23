import { motion } from 'framer-motion'
import { LucideIcon } from 'lucide-react'
import { ReactNode } from 'react'

interface MetricCardProps {
  icon: LucideIcon; label: string; value: string | ReactNode; subtitle?: string;
  color?: 'blue' | 'green' | 'purple' | 'red' | 'amber' | 'slate';
  trend?: 'up' | 'down' | 'neutral'; tooltip?: string; delay?: number
}

const COLOR_CLASSES = {
  blue:   { border: 'border-blue-400 dark:border-blue-600',     icon: 'text-blue-600 dark:text-blue-400',     label: 'text-blue-800 dark:text-blue-400',     bg: 'bg-blue-50/50 dark:bg-blue-900/20' },
  green:  { border: 'border-green-400 dark:border-green-600',   icon: 'text-green-600 dark:text-green-400',   label: 'text-green-800 dark:text-green-400',   bg: 'bg-green-50/50 dark:bg-green-900/20' },
  purple: { border: 'border-purple-400 dark:border-purple-600', icon: 'text-purple-600 dark:text-purple-400', label: 'text-purple-800 dark:text-purple-400', bg: 'bg-purple-50/50 dark:bg-purple-900/20' },
  red:    { border: 'border-red-400 dark:border-red-600',       icon: 'text-red-600 dark:text-red-400',       label: 'text-red-800 dark:text-red-400',       bg: 'bg-red-50/50 dark:bg-red-900/20' },
  amber:  { border: 'border-amber-400 dark:border-amber-600',   icon: 'text-amber-600 dark:text-amber-400',   label: 'text-amber-800 dark:text-amber-400',   bg: 'bg-amber-50/50 dark:bg-amber-900/20' },
  slate:  { border: 'border-slate-200 dark:border-slate-700',   icon: 'text-slate-600 dark:text-slate-400',   label: 'text-slate-800 dark:text-slate-400',   bg: 'bg-white dark:bg-slate-900' },
}

const TREND_BADGE = {
  up:      'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300',
  down:    'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300',
  neutral: 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300',
}

const TREND_LABEL = { up: '↗ UP', down: '↘ DOWN', neutral: '→ STABLE' }

export function MetricCard({ icon: Icon, label, value, subtitle, color = 'slate', trend, tooltip, delay = 0 }: MetricCardProps) {
  const c = COLOR_CLASSES[color]
  return (
    <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay, duration: 0.3 }}
      whileHover={{ scale: 1.02, y: -2, transition: { duration: 0.2 } }}
      className={`group relative ${c.bg} border-2 ${c.border} rounded-xl p-6 shadow-lg hover:shadow-2xl transition-all cursor-pointer`}
      title={tooltip}>
      <div className="absolute inset-0 bg-gradient-to-br from-transparent to-slate-100/20 dark:to-slate-800/20 opacity-0 group-hover:opacity-100 transition-opacity rounded-xl pointer-events-none" />
      <div className="relative z-10">
        <div className="flex items-center justify-between mb-4">
          <div className={`p-2 rounded-lg ${c.bg}`}><Icon className={`w-6 h-6 ${c.icon}`} /></div>
          {trend && <div className={`text-xs font-bold px-2 py-1 rounded-md ${TREND_BADGE[trend]}`}>{TREND_LABEL[trend]}</div>}
        </div>
        <div className={`text-sm font-bold ${c.label} uppercase tracking-wider mb-3`}>{label}</div>
        <div className="text-3xl font-extrabold text-black dark:text-white font-mono mb-2 leading-tight">{value}</div>
        {subtitle && <p className="text-sm text-slate-800 dark:text-slate-400 font-semibold">{subtitle}</p>}
      </div>
    </motion.div>
  )
}
