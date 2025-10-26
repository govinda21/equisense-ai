import { useEffect, useState } from 'react'
import { Icons } from './icons'
import { useTheme } from '../contexts/ThemeContext'

interface NavbarProps {
  chatOpen?: boolean
  onChatToggle?: () => void
  currentView?: 'dashboard' | 'analysis'
  onViewChange?: (view: 'dashboard' | 'analysis') => void
}

export function Navbar({ chatOpen = false, onChatToggle, currentView = 'dashboard', onViewChange }: NavbarProps) {
  const { theme, toggleTheme } = useTheme()
  
  // Sync theme to document root for dark mode classes
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') {
      root.classList.add('dark')
    } else {
      root.classList.remove('dark')
    }
  }, [theme])

  return (
    <header className="bg-white/80 dark:bg-slate-900/70 backdrop-blur supports-[backdrop-filter]:bg-white/60 dark:supports-[backdrop-filter]:bg-slate-900/60 sticky top-0 z-20 border-b border-slate-200 dark:border-slate-700">
      <div className="container py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center" aria-hidden>
            <Icons.TrendingUp className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-slate-900 dark:text-slate-100">EquiSense AI</h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">Intelligent Stock Analysis</p>
          </div>
        </div>
        <div className="flex items-center gap-3 text-sm">
          {/* Navigation Buttons */}
          {onViewChange && (
            <div className="flex space-x-2">
              <button
                onClick={() => onViewChange('dashboard')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  currentView === 'dashboard'
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                    : 'text-slate-600 dark:text-slate-400 hover:text-blue-500 dark:hover:text-blue-300'
                }`}
              >
                Dashboard
              </button>
              <button
                onClick={() => onViewChange('analysis')}
                className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  currentView === 'analysis'
                    ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300'
                    : 'text-slate-600 dark:text-slate-400 hover:text-blue-500 dark:hover:text-blue-300'
                }`}
              >
                Stock Analysis
              </button>
            </div>
          )}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300 rounded-full text-xs">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span>Gemma3:4b Active</span>
          </div>
          {onChatToggle && (
            <button
              onClick={onChatToggle}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all duration-200 shadow-lg ${
                chatOpen
                  ? 'bg-blue-500 text-white'
                  : 'bg-white/70 dark:bg-slate-800/70 text-slate-600 dark:text-slate-400 hover:text-blue-500 backdrop-blur'
              }`}
            >
              <Icons.MessageCircle className="w-4 h-4" />
              {chatOpen ? 'Close AI Chat' : 'Open AI Chat'}
            </button>
          )}
          <button 
            className="rounded-lg border px-3 py-2 text-slate-700 dark:text-slate-200 border-slate-300 dark:border-slate-600 hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors" 
            onClick={toggleTheme}
            aria-label="Toggle theme"
          >
            {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
          </button>
        </div>
      </div>
    </header>
  )
}
