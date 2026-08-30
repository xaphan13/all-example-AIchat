import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'
import { logger } from '@/services/logger'

// Initialize logging
logger.info('Application starting', {
  environment: import.meta.env.MODE,
  timestamp: new Date().toISOString(),
  userAgent: navigator.userAgent,
})

// Log unhandled errors
window.addEventListener('error', (event) => {
  logger.error('Unhandled error', event.error, {
    message: event.message,
    filename: event.filename,
    lineno: event.lineno,
    colno: event.colno,
  })
})

// Log unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
  logger.error('Unhandled promise rejection', new Error(String(event.reason)), {
    reason: event.reason,
  })
})

// Log when app becomes visible/hidden (for analytics)
document.addEventListener('visibilitychange', () => {
  logger.debug('Visibility changed', {
    hidden: document.hidden,
  })
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)

logger.info('Application mounted')

