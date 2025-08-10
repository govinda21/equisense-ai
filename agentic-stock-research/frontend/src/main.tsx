import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'
import { Navbar } from './components/Navbar'

function Root() {
  return (
    <React.StrictMode>
      <Navbar />
      <App />
    </React.StrictMode>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(<Root />)
