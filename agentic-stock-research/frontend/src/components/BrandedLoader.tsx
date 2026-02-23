export function BrandedLoader({ message }: { message?: string }) {
  return (
    <div className="flex items-center gap-3 text-blue-700 dark:text-blue-400" role="status" aria-live="polite">
      <div className="h-6 w-6 rounded-lg bg-blue-600 animate-pulse" aria-hidden />
      <span>{message || 'Analyzing…'}</span>
    </div>
  )
}
