import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Setup from './pages/Setup'
import ThankYou from './pages/ThankYou'
import Settings from './pages/Settings'
import Interview from './pages/Interview'
import Report from './pages/Report'
import './index.css'

class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null } }
  static getDerivedStateFromError(error) { return { error } }
  render() {
    if (this.state.error) {
      return (
        <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '24px', background: '#f8fafc', textAlign: 'center' }}>
          <div style={{ fontSize: '2rem', marginBottom: '12px' }}>⚠️</div>
          <h2 style={{ fontSize: '1.1rem', fontWeight: '600', color: '#1e293b', marginBottom: '8px' }}>Something went wrong</h2>
          <p style={{ fontSize: '0.875rem', color: '#64748b', marginBottom: '16px' }}>{String(this.state.error?.message || this.state.error)}</p>
          <button onClick={() => window.location.reload()} style={{ background: '#2563eb', color: '#fff', border: 'none', borderRadius: '8px', padding: '10px 24px', fontSize: '0.875rem', cursor: 'pointer' }}>
            Reload
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')).render(
  <ErrorBoundary>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Setup />} />
        <Route path="/interview/:sessionId" element={<Interview />} />
        <Route path="/report/:sessionId" element={<Report />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/thank-you" element={<ThankYou />} />
      </Routes>
    </BrowserRouter>
  </ErrorBoundary>
)
