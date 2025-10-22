import React, { useState } from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'
import { Navbar } from './components/Navbar'

export function Root() {
  const [chatOpen, setChatOpen] = useState(false)
  const [currentView, setCurrentView] = useState<'dashboard' | 'analysis'>('analysis')  // Default to analysis

  return (
    <React.StrictMode>
      <Navbar 
        chatOpen={chatOpen} 
        onChatToggle={() => setChatOpen(!chatOpen)}
        currentView={currentView}
        onViewChange={setCurrentView}
      />
      <App chatOpen={chatOpen} currentView={currentView} onViewChange={setCurrentView} />
    </React.StrictMode>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(<Root />)
