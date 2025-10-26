import React, { useState } from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'
import { Navbar } from './components/Navbar'
import { ThemeProvider } from './contexts/ThemeContext'

export function Root() {
  const [chatOpen, setChatOpen] = useState(false)
  const [currentView, setCurrentView] = useState<'dashboard' | 'analysis'>('analysis')  // Default to analysis

  return (
    <React.StrictMode>
      <ThemeProvider>
        <Navbar 
          chatOpen={chatOpen} 
          onChatToggle={() => setChatOpen(!chatOpen)}
          currentView={currentView}
          onViewChange={setCurrentView}
        />
        <App chatOpen={chatOpen} currentView={currentView} onViewChange={setCurrentView} />
      </ThemeProvider>
    </React.StrictMode>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(<Root />)
