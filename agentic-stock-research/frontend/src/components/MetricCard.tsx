import { motion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'

interface MetricCardProps {
  icon: LucideIcon
  label: string
  value: string
  subtitle?: string
  color: 'slate' | 'green' | 'blue' | 'red' | 'purple' | 'amber'
  trend?: 'up' | 'down'
  delay?: number
  tooltip?: string
}

// ─── Unified color system ───────────────────────────────────────────────────
// Each color key maps to a consistent set of tokens used across the card.
// All variants use the same structural pattern so cards look like a family.
//
// Light mode tokens:
//   bg          – card background (very light tint)
//   border      – card border
//   iconBg      – icon container background
//   iconColor   – icon colour
//   labelColor  – uppercase label text
//   valueColor  – large primary value
//   subtitleColor – small muted subtitle text
//
// Dark mode tokens mirror the same slots with dark: prefix.
// ────────────────────────────────────────────────────────────────────────────
const COLOR_MAP: Record<
  MetricCardProps['color'],
  {
    bg: string
    border: string
    iconBg: string
    iconColor: string
    labelColor: string
    valueColor: string
    subtitleColor: string
  }
> = {
  slate: {
    // Current Price — neutral dark slate, no coloured accent on value
    bg:            'bg-slate-50          dark:bg-slate-800/60',
    border:        'border-slate-200     dark:border-slate-700',
    iconBg:        'bg-slate-200         dark:bg-slate-700',
    iconColor:     'text-slate-600       dark:text-slate-300',
    labelColor:    'text-slate-500       dark:text-slate-400',
    valueColor:    'text-slate-900       dark:text-slate-50',
    subtitleColor: 'text-slate-400       dark:text-slate-500',
  },
  green: {
    // Price Target — green accent, readable dark green value (not neon)
    bg:            'bg-emerald-50        dark:bg-emerald-900/20',
    border:        'border-emerald-200   dark:border-emerald-700',
    iconBg:        'bg-emerald-100       dark:bg-emerald-800/60',
    iconColor:     'text-emerald-600     dark:text-emerald-400',
    labelColor:    'text-emerald-700     dark:text-emerald-400',
    valueColor:    'text-emerald-800     dark:text-emerald-300',   // ← rich dark green, not neon
    subtitleColor: 'text-emerald-600/70  dark:text-emerald-500',
  },
  blue: {
    // Expected Return — blue throughout; value must be blue, NOT green
    bg:            'bg-blue-50           dark:bg-blue-900/20',
    border:        'border-blue-200      dark:border-blue-700',
    iconBg:        'bg-blue-100          dark:bg-blue-800/60',
    iconColor:     'text-blue-600        dark:text-blue-400',
    labelColor:    'text-blue-700        dark:text-blue-400',
    valueColor:    'text-blue-800        dark:text-blue-300',      // ← explicitly blue, not green
    subtitleColor: 'text-blue-600/70     dark:text-blue-500',
  },
  red: {
    // Negative returns — red accent
    bg:            'bg-red-50            dark:bg-red-900/20',
    border:        'border-red-200       dark:border-red-700',
    iconBg:        'bg-red-100           dark:bg-red-800/60',
    iconColor:     'text-red-600         dark:text-red-400',
    labelColor:    'text-red-700         dark:text-red-400',
    valueColor:    'text-red-700         dark:text-red-300',
    subtitleColor: 'text-red-600/70      dark:text-red-500',
  },
  purple: {
    // DCF Valuation — purple accent; warning text must be purple-toned, not amber
    bg:            'bg-purple-50         dark:bg-purple-900/20',
    border:        'border-purple-200    dark:border-purple-700',
    iconBg:        'bg-purple-100        dark:bg-purple-800/60',
    iconColor:     'text-purple-600      dark:text-purple-400',
    labelColor:    'text-purple-700      dark:text-purple-400',
    valueColor:    'text-purple-800      dark:text-purple-300',    // ← purple, not amber
    subtitleColor: 'text-purple-600/70   dark:text-purple-500',
  },
  amber: {
    // Amber/warning — intentional amber when the caller explicitly wants it
    bg:            'bg-amber-50          dark:bg-amber-900/20',
    border:        'border-amber-200     dark:border-amber-700',
    iconBg:        'bg-amber-100         dark:bg-amber-800/60',
    iconColor:     'text-amber-600       dark:text-amber-400',
    labelColor:    'text-amber-700       dark:text-amber-400',
    valueColor:    'text-amber-800       dark:text-amber-300',
    subtitleColor: 'text-amber-600/70    dark:text-amber-500',
  },
}

// Trend arrow displayed next to the value
const TrendBadge = ({ trend, color }: { trend?: 'up' | 'down'; color: MetricCardProps['color'] }) => {
  if (!trend) return null
  const isUp = trend === 'up'
  const trendColor = isUp
    ? 'text-emerald-600 dark:text-emerald-400 bg-emerald-100 dark:bg-emerald-900/40'
    : 'text-red-600     dark:text-red-400     bg-red-100     dark:bg-red-900/40'
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-bold ${trendColor}`}>
      {isUp ? '↑' : '↓'}
    </span>
  )
}

export function MetricCard({
  icon: Icon,
  label,
  value,
  subtitle,
  color,
  trend,
  delay = 0,
  tooltip,
}: MetricCardProps) {
  const c = COLOR_MAP[color] ?? COLOR_MAP.slate

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay, ease: 'easeOut' }}
      title={tooltip}
      className={`
        relative rounded-2xl border p-5 flex flex-col gap-3
        shadow-sm hover:shadow-md transition-shadow duration-200
        ${c.bg} ${c.border}
      `}
    >
      {/* Icon + Label row */}
      <div className="flex items-center gap-2.5">
        <span className={`p-2 rounded-xl ${c.iconBg}`}>
          <Icon className={`w-4 h-4 ${c.iconColor}`} />
        </span>
        <span className={`text-xs font-semibold uppercase tracking-widest ${c.labelColor}`}>
          {label}
        </span>
      </div>

      {/* Primary value */}
      <div className="flex items-baseline gap-2">
        <span className={`text-2xl font-extrabold leading-none tracking-tight ${c.valueColor}`}>
          {value}
        </span>
        <TrendBadge trend={trend} color={color} />
      </div>

      {/* Subtitle */}
      {subtitle && (
        <p className={`text-xs leading-snug ${c.subtitleColor}`}>
          {subtitle}
        </p>
      )}
    </motion.div>
  )
}
