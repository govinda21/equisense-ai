import React, { useState } from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'
import { Navbar } from './components/Navbar'

export function Root() {
  const [chatOpen, setChatOpen] = useState(false)

  return (
    <React.StrictMode>
      <Navbar chatOpen={chatOpen} onChatToggle={() => setChatOpen(!chatOpen)} />
      <App chatOpen={chatOpen} />
    </React.StrictMode>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(<Root />)
