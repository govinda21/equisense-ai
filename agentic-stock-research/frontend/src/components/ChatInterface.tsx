import { useState, useRef, useEffect } from 'react'
import { Icons } from './icons'

interface Message {
  id: string
  type: 'user' | 'assistant'
  content: string
  timestamp: Date
  loading?: boolean
}

interface ChatInterfaceProps {
  analysisContext?: {
    tickers?: string[]
    data?: any
    latency?: number | null
  }
}

export function ChatInterface({ analysisContext }: ChatInterfaceProps) {
  const ctx = analysisContext ?? { tickers: [], data: null, latency: null }
  // Generate context-aware initial message
  const getInitialMessage = () => {
    if (ctx.data?.reports?.length > 0) {
      const tickers = ctx.data.reports.map((r: any) => r.ticker).join(', ')
      return `Hi! I can see you've analyzed ${tickers}. I'm here to help you understand the analysis, answer questions about these stocks, or provide additional insights. What would you like to know?`
    }
    return "Hi! I'm your AI financial assistant. I can help you analyze stocks, explain market trends, or answer questions about your portfolio. What would you like to know?"
  }

  const [messages, setMessages] = useState<Message[]>([
    {
      id: '1',
      type: 'assistant',
      content: getInitialMessage(),
      timestamp: new Date()
    }
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Update initial message when analysis context changes
  useEffect(() => {
    setMessages(prev => prev.length === 1 ? [{
      ...prev[0],
      content: getInitialMessage()
    }] : prev)
  }, [ctx.data])

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage: Message = {
      id: Date.now().toString(),
      type: 'user',
      content: input.trim(),
      timestamp: new Date()
    }

    const loadingMessage: Message = {
      id: (Date.now() + 1).toString(),
      type: 'assistant',
      content: '',
      timestamp: new Date(),
      loading: true
    }

    setMessages(prev => [...prev, userMessage, loadingMessage])
    setInput('')
    setLoading(true)

    try {
      // Include analysis context in the chat request
      const contextMessage = ctx.data?.reports?.length > 0 
        ? `Context: User has analyzed ${ctx.data.reports.map((r: any) => r.ticker).join(', ')}. Latest analysis shows: ${ctx.data.reports.map((r: any) => `${r.ticker}: ${r.decision?.action} (${r.decision?.rating}/5)`).join(', ')}. User question: ${input.trim()}`
        : input.trim()

      const base = (import.meta as any).env.VITE_API_BASE_URL || 'http://localhost:8000'
      const response = await fetch(base + '/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: contextMessage })
      })

      let assistantResponse = ''
      if (response.ok) {
        const data = await response.json()
        assistantResponse = data.response || 'I apologize, but I encountered an issue processing your request.'
      } else {
        // Fallback response for demo purposes
        assistantResponse = generateFallbackResponse(input.trim())
      }

      setMessages(prev => 
        prev.map(msg => 
          msg.id === loadingMessage.id 
            ? { ...msg, content: assistantResponse, loading: false }
            : msg
        )
      )
    } catch (error) {
      const errorResponse = "I'm currently experiencing some connectivity issues. Please try again in a moment."
      setMessages(prev => 
        prev.map(msg => 
          msg.id === loadingMessage.id 
            ? { ...msg, content: errorResponse, loading: false }
            : msg
        )
      )
    } finally {
      setLoading(false)
    }
  }

  // Fallback responses for demo purposes
  const generateFallbackResponse = (input: string): string => {
    const lowerInput = input.toLowerCase()
    
    if (lowerInput.includes('price') || lowerInput.includes('stock')) {
      return "I can help you analyze stock prices and trends. Try using the Stock Analysis tab to get comprehensive reports on specific tickers like AAPL, MSFT, or GOOGL."
    }
    
    if (lowerInput.includes('market') || lowerInput.includes('economy')) {
      return "Market conditions are influenced by various factors including economic indicators, earnings reports, and global events. Would you like me to analyze specific stocks or sectors?"
    }
    
    if (lowerInput.includes('buy') || lowerInput.includes('sell') || lowerInput.includes('invest')) {
      return "I can provide analysis and insights, but remember that this is not financial advice. Always do your own research and consider consulting with a financial advisor for investment decisions."
    }
    
    return "That's an interesting question about finance! I can help you analyze stocks, explain market trends, or provide insights on financial data. What specific stocks or topics would you like to explore?"
  }

  // Generate context-aware quick prompts
  const getQuickPrompts = () => {
    if (ctx.data?.reports?.length > 0) {
      const tickers = ctx.data.reports.map((r: any) => r.ticker)
      const firstTicker = tickers[0]
      return [
        `Why is ${firstTicker} rated as ${ctx.data.reports[0]?.decision?.action}?`,
        `What are the risks for ${firstTicker}?`,
        `Compare ${firstTicker} to its competitors`,
        tickers.length > 1 ? `Which is better: ${tickers.slice(0, 2).join(' or ')}?` : `Is ${firstTicker} a good long-term investment?`
      ].filter(Boolean)
    }
    return [
      "Analyze AAPL stock",
      "Market trends today",
      "Tech sector outlook",
      "Best dividend stocks"
    ]
  }

  const quickPrompts = getQuickPrompts()

  const handleQuickPrompt = (prompt: string) => {
    setInput(prompt)
  }

  return (
    <div className="h-full flex flex-col">
      {/* Chat Header */}
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
          <div className="w-2 h-2 bg-green-500 rounded-full"></div>
          <span className="text-xs text-slate-500">Online</span>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message) => (
          <div
            key={message.id}
            className={`flex items-start gap-3 ${
              message.type === 'user' ? 'flex-row-reverse' : 'flex-row'
            }`}
          >
            <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
              message.type === 'user' 
                ? 'bg-blue-600 text-white' 
                : 'bg-gradient-to-br from-blue-500 to-purple-600 text-white'
            }`}>
              {message.type === 'user' ? (
                <Icons.User className="w-4 h-4" />
              ) : (
                <Icons.Bot className="w-4 h-4" />
              )}
            </div>
            <div className={`flex-1 max-w-[80%] ${
              message.type === 'user' ? 'flex justify-end' : ''
            }`}>
              <div className={`p-3 rounded-lg ${
                message.type === 'user'
                  ? 'bg-blue-600 text-white'
                  : 'bg-slate-100 dark:bg-slate-800 text-slate-900 dark:text-slate-100'
              }`}>
                {message.loading ? (
                  <div className="flex items-center gap-2">
                    <div className="flex space-x-1">
                      <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
                      <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                      <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    </div>
                    <span className="text-xs text-slate-500">Thinking...</span>
                  </div>
                ) : (
                  <p className="text-sm whitespace-pre-wrap">{message.content}</p>
                )}
              </div>
              <div className={`text-xs text-slate-500 mt-1 ${
                message.type === 'user' ? 'text-right' : 'text-left'
              }`}>
                {message.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
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
            {quickPrompts.map((prompt) => (
              <button
                key={prompt}
                onClick={() => handleQuickPrompt(prompt)}
                className="px-3 py-1 text-xs bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-900/30 dark:text-blue-300 dark:hover:bg-blue-900/50 rounded-full transition-colors shadow-sm"
              >
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
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about stocks, market trends, or financial analysis..."
              className="w-full pl-4 pr-12 py-3 rounded-lg border border-slate-300 dark:border-slate-600 bg-white dark:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={!input.trim() || loading}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1.5 rounded-md bg-blue-600 text-white disabled:opacity-50 disabled:cursor-not-allowed hover:bg-blue-700 transition-colors"
            >
              <Icons.Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </form>
    </div>
  )
}
