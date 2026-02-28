import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Setup from './pages/Setup'
import Interview from './pages/Interview'
import Report from './pages/Report'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <BrowserRouter>
    <Routes>
      <Route path="/" element={<Setup />} />
      <Route path="/interview/:sessionId" element={<Interview />} />
      <Route path="/report/:sessionId" element={<Report />} />
    </Routes>
  </BrowserRouter>
)
