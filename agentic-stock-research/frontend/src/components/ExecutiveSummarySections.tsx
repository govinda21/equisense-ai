import { motion } from 'framer-motion'
import { AlertTriangle, Target, CheckCircle } from 'lucide-react'

interface ExecutiveSummarySectionsProps { summary: string }

const POSITIVE_WORDS = ['strong', 'good', 'excellent', 'conservative', 'low debt', 'adequate', 'positive']
const CONCERN_WORDS = ['concern', 'risk', 'warning', 'overvaluation', 'limited', 'monitor']
const VALUATION_WORDS = ['overvalued', 'undervalued', 'intrinsic value', 'margin of safety', 'entry', 'target']
const ACTION_WORDS = ['wait', 'monitor', 'set', 'alert', 'entry zone', 'stop loss']

function matchesAny(lower: string, words: string[]) { return words.some(w => lower.includes(w)) }

function parseExecutiveSummary(summary: string) {
  const quickTake: string[] = [], whatsWorking: string[] = [], concerns: string[] = [], actionPlan: string[] = []
  const lines = summary.split('\n').filter(l => l.trim())

  for (const line of lines) {
    const lower = line.toLowerCase(), t = line.trim()
    if (quickTake.length < 3 && matchesAny(lower, VALUATION_WORDS)) quickTake.push(t)
    if (whatsWorking.length < 5 && matchesAny(lower, POSITIVE_WORDS)) whatsWorking.push(t)
    if (concerns.length < 5 && matchesAny(lower, CONCERN_WORDS)) concerns.push(t)
    if (actionPlan.length < 3 && matchesAny(lower, ACTION_WORDS)) actionPlan.push(t)
  }

  // Fallback: categorize from sentences if no structured data found
  if (!quickTake.length && !whatsWorking.length && !concerns.length) {
    const sentences = summary.split(/[.!?]+/).filter(s => s.trim().length > 20)
    sentences.slice(0, 3).forEach(s => { if (s.trim()) quickTake.push(s.trim()) })
    sentences.slice(3, 6).forEach(s => {
      const t = s.trim(), l = t.toLowerCase()
      if (matchesAny(l, POSITIVE_WORDS)) whatsWorking.push(t)
      else if (matchesAny(l, CONCERN_WORDS)) concerns.push(t)
    })
  }

  return { quickTake, whatsWorking, concerns }
}

interface SectionProps { delay: number; className: string; icon: React.ReactNode; title: string; points: string[] }

function Section({ delay, className, icon, title, points }: SectionProps) {
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay }}
      className={`border-2 rounded-lg p-4 shadow-sm ${className}`}>
      <div className="flex items-center gap-2 mb-3">{icon}<h4 className="text-sm font-extrabold">{title}</h4></div>
      <ul className="space-y-2">
        {points.map((p, i) => (
          <li key={i} className="text-sm font-semibold flex items-start gap-2">
            <span className="mt-1 font-bold">•</span><span>{p}</span>
          </li>
        ))}
      </ul>
    </motion.div>
  )
}

export function ExecutiveSummarySections({ summary }: ExecutiveSummarySectionsProps) {
  const { quickTake, whatsWorking, concerns } = parseExecutiveSummary(summary)

  if (!quickTake.length && !whatsWorking.length && !concerns.length) {
    return (
      <div className="bg-slate-100 dark:bg-slate-800 rounded-lg p-6 border-2 border-slate-300 dark:border-slate-600 shadow-sm">
        <div className="flex items-center gap-2 mb-3">
          <Target className="w-4 h-4 text-slate-800 dark:text-slate-200" />
          <h4 className="text-sm font-extrabold text-slate-900 dark:text-slate-50 uppercase tracking-wide">Executive Summary</h4>
        </div>
        <div className="max-h-[300px] overflow-y-auto pr-2 exec-summary-scroll">
          <p className="text-sm font-medium text-slate-800 dark:text-slate-200 leading-relaxed whitespace-pre-wrap">{summary}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {quickTake.length > 0 && (
        <Section delay={0.1} className="bg-blue-100 dark:bg-blue-900/40 border-blue-400 dark:border-blue-600"
          icon={<Target className="w-4 h-4 text-blue-700 dark:text-blue-300" />}
          title="📊 Quick Take (3 Key Points)" points={quickTake} />
      )}
      {whatsWorking.length > 0 && (
        <Section delay={0.2} className="bg-green-100 dark:bg-green-900/40 border-green-400 dark:border-green-600"
          icon={<CheckCircle className="w-4 h-4 text-green-700 dark:text-green-300" />}
          title="📈 What's Working" points={whatsWorking} />
      )}
      {concerns.length > 0 && (
        <Section delay={0.3} className="bg-amber-100 dark:bg-amber-900/40 border-amber-400 dark:border-amber-600"
          icon={<AlertTriangle className="w-4 h-4 text-amber-700 dark:text-amber-300" />}
          title="⚠️ What's Concerning" points={concerns} />
      )}
    </div>
  )
}
