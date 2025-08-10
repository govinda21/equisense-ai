import { useState } from 'react'

export function MetricTooltip({ label, info }: { label: string; info: string }) {
  const [open, setOpen] = useState(false)
  return (
    <span className="relative inline-flex items-center gap-1">
      <span>{label}</span>
      <button aria-label={`More info about ${label}`} className="h-4 w-4 rounded-full bg-slate-200 text-slate-700 text-xs leading-4" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)} onFocus={() => setOpen(true)} onBlur={() => setOpen(false)}>i</button>
      {open && (
        <div role="tooltip" className="absolute left-1/2 -translate-x-1/2 top-full mt-1 w-56 rounded-lg border bg-white p-2 text-xs shadow dark:bg-slate-800 dark:text-slate-100 dark:border-slate-700">
          {info}
        </div>
      )}
    </span>
  )}
