export function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="card p-6 text-center border border-rose-200 bg-rose-50 text-rose-800">
      <h3 className="text-lg font-semibold mb-2">Something went wrong</h3>
      <p className="text-sm mb-4">{message}</p>
      <button className="btn-primary" onClick={onRetry}>Retry</button>
    </div>
  )
}
