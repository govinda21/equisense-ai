import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, ChevronUp } from 'lucide-react'
import { ReactNode, useState } from 'react'

interface CollapsibleSectionProps {
  title: string; children: ReactNode; defaultOpen?: boolean; icon?: ReactNode; badge?: string
}

export function CollapsibleSection({ title, children, defaultOpen = false, icon, badge }: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen)
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-slate-900 border-2 border-slate-200 dark:border-slate-700 rounded-xl shadow-lg overflow-hidden">
      <button onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between p-6 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors">
        <div className="flex items-center gap-3">
          {icon && <div className="text-black dark:text-slate-300">{icon}</div>}
          <h3 className="text-xl font-extrabold text-black dark:text-white tracking-tight">{title}</h3>
          {badge && (
            <span className="px-3 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-950 dark:text-blue-200 text-xs font-extrabold rounded-full border border-blue-200 dark:border-blue-800">
              {badge}
            </span>
          )}
        </div>
        <motion.div animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.3 }}>
          {isOpen ? <ChevronUp className="w-6 h-6 text-black dark:text-slate-400" /> : <ChevronDown className="w-6 h-6 text-black dark:text-slate-400" />}
        </motion.div>
      </button>
      <AnimatePresence>
        {isOpen && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: 'auto', opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.3 }}>
            <div className="px-6 pb-6 border-t-2 border-slate-100 dark:border-slate-800">
              <div className="pt-6">{children}</div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
