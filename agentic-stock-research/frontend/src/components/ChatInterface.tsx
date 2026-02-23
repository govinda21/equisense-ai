import { useState, useRef, useEffect } from 'react'
import { Icons } from './icons'

interface Message {
  id: string; type: 'user' | 'assistant'; content: string; timestamp: Date; loading?: boolean
}

interface ChatInterfaceProps {
  analysisContext?: { tickers?: string[]; data?: any; latency?: number | null }
}

const API_BASE = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000'

function generateFallbackResponse(input: string): string {
  const lower = input.toLowerCase()
  if (lower.includes('price') || lower.includes('stock'))
    return "I can help you analyze stock prices and trends. Try using the Stock Analysis tab to get comprehensive reports on specific tickers like AAPL, MSFT, or GOOGL."
  if (lower.includes('market') || lower.includes('economy'))
    return "Market conditions are influenced by various factors including economic indicators, earnings reports, and global events. Would you like me to analyze specific stocks or sectors?"
  if (lower.includes('buy') || lower.includes('sell') || lower.includes('invest'))
    return "I can provide analysis and insights, but remember that this is not financial advice. Always do your own research and consider consulting with a financial advisor for investment decisions."
  return "That's an interesting question about finance! I can help you analyze stocks, explain market trends, or provide insights on financial data. What specific stocks or topics would you like to explore?"
}

export function ChatInterface({ analysisContext }: ChatInterfaceProps) {
  const ctx = analysisContext ?? { tickers: [], data: null, latency: null }
  const reports = ctx.data?.reports || []

  const getInitialMessage = () => reports.length > 0
    ? `Hi! I can see you've analyzed ${reports.map((r: any) => r.ticker).join(', ')}. I'm here to help you understand the analysis, answer questions about these stocks, or provide additional insights. What would you like to know?`
    : "Hi! I'm your AI financial assistant. I can help you analyze stocks, explain market trends, or answer questions about your portfolio. What would you like to know?"

  const [messages, setMessages] = useState<Message[]>([{ id: '1', type: 'assistant', content: getInitialMessage(), timestamp: new Date() }])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])
  useEffect(() => {
    setMessages(prev => prev.length === 1 ? [{ ...prev[0], content: getInitialMessage() }] : prev)
  }, [ctx.data])

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    const userMsg: Message = { id: Date.now().toString(), type: 'user', content: input.trim(), timestamp: new Date() }
    const loadingMsg: Message = { id: (Date.now() + 1).toString(), type: 'assistant', content: '', timestamp: new Date(), loading: true }
    setMessages(prev => [...prev, userMsg, loadingMsg])
    const userText = input.trim()
    setInput('')
    setLoading(true)
    try {
      const contextMessage = reports.length > 0
        ? `Context: User has analyzed ${reports.map((r: any) => r.ticker).join(', ')}. Latest analysis shows: ${reports.map((r: any) => `${r.ticker}: ${r.decision?.action} (${r.decision?.rating}/5)`).join(', ')}. User question: ${userText}`
        : userText
      const res = await fetch(API_BASE + '/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: contextMessage }) })
      const content = res.ok ? (await res.json()).response || generateFallbackResponse(userText) : generateFallbackResponse(userText)
      setMessages(prev => prev.map(m => m.id === loadingMsg.id ? { ...m, content, loading: false } : m))
    } catch {
      setMessages(prev => prev.map(m => m.id === loadingMsg.id ? { ...m, content: "I'm currently experiencing some connectivity issues. Please try again in a moment.", loading: false } : m))
    } finally {
      setLoading(false)
    }
  }

  const quickPrompts = reports.length > 0
    ? [
        `Why is ${reports[0].ticker} rated as ${reports[0]?.decision?.action}?`,
        `What are the risks for ${reports[0].ticker}?`,
        `Compare ${reports[0].ticker} to its competitors`,
        reports.length > 1 ? `Which is better: ${reports[0].ticker} or ${reports[1].ticker}?` : `Is ${reports[0].ticker} a good long-term investment?`
      ]
    : ['Analyze AAPL stock', 'Market trends today', 'Tech sector outlook', 'Best dividend stocks']

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-600 rounded-full flex items-center justify-center">
            <Icons.Bot className="w-4 h-4 text-white" />
          </div>
          <div>
            <h3 className="font-medium text-sm">AI Financial Assistant</h3>
            <p className="text-xs text-slate-500">Powered by Gemma3</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 bg-green-500 rounded-full" />
          <span className="text-xs text-slate-500">Online</span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map(msg => (
          <div key={msg.id} className={`flex items-start gap-3 ${msg.type === 'user' ? 'flex-row-reverse' : 'flex-row'}`}>
            <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${msg.type === 'user' ? 'bg-blue-600 text-white' : 'bg-gradient-to-br from-blue-500 to-purple-600 text-white'}`}>
              {msg.type === 'user' ? <Icons.User className="w-4 h-4" /> : <Icons.Bot className="w-4 h-4" />}
            </div>
            <div className={`flex-1 max-w-[80%] ${msg.type === 'user' ? 'flex justify-end' : ''}`}>
              <div className={`p-3 rounded-lg ${msg.type === 'user' ? 'bg-blue-600 text-white' : 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100'}`}>
                {msg.loading ? (
                  <div className="flex items-center gap-2">
                    <div className="flex space-x-1">
                      {[0, 0.1, 0.2].map((d, i) => <div key={i} className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: `${d}s` }} />)}
                    </div>
                    <span className="text-xs text-slate-500">Thinking...</span>
                  </div>
                ) : <p className="text-sm whitespace-pre-wrap">{msg.content}</p>}
              </div>
              <div className={`text-xs text-slate-500 mt-1 ${msg.type === 'user' ? 'text-right' : 'text-left'}`}>
                {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Quick Prompts */}
      {messages.length === 1 && (
        <div className="p-4 border-t border-slate-200 dark:border-slate-700">
          <p className="text-xs text-slate-500 mb-2">Quick prompts:</p>
          <div className="flex flex-wrap gap-2">
            {quickPrompts.filter(Boolean).map(prompt => (
              <button key={prompt} onClick={() => setInput(prompt)}
                className="px-3 py-1 text-xs bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-900/30 dark:text-blue-300 dark:hover:bg-blue-900/50 rounded-full transition-colors shadow-sm">
                {prompt}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <form onSubmit={sendMessage} className="p-4 border-t border-slate-200 dark:border-slate-700">
        <div className="flex items-center gap-2">
          <div className="flex-1 relative">
            <input type="text" value={input} onChange={e => setInput(e.target.value)}
              placeholder="Ask about stocks, market trends, or financial analysis..."
              className="w-full pl-4 pr-12 py-3 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading} />
            <button type="submit" disabled={!input.trim() || loading}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md bg-blue-600 text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-700 transition-colors">
              <Icons.Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
