import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Setup from './pages/Setup'
import ThankYou from './pages/ThankYou'
import Settings from './pages/Settings'
import Interview from './pages/Interview'
import Report from './pages/Report'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<Setup />} />
      <Route path="/interview/:sessionId" element={<Interview />} />
      <Route path="/report/:sessionId" element={<Report />} />
      <Route path="/settings" element={<Settings />} />
      <Route path="/thank-you" element={<ThankYou />} />
    </Routes>
  </BrowserRouter>
)
