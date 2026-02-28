import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001'

function ScoreRing({ score }) {
  const color = score >= 70 ? 'text-green-400' : score >= 50 ? 'text-yellow-400' : 'text-red-400'
  const bg = score >= 70 ? 'border-green-400' : score >= 50 ? 'border-yellow-400' : 'border-red-400'
  return (
    <div className={`w-32 h-32 rounded-full border-8 ${bg} flex items-center justify-center`}>
      <span className={`text-4xl font-bold ${color}`}>{score}</span>
    </div>
  )
}

export default function Report() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [report, setReport] = useState(null)
  const [expanded, setExpanded] = useState({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/api/interview/session/${sessionId}`)
        if (data.report) { setReport(data.report); setLoading(false) }
        else {
          const { data: r } = await axios.post(`${API}/api/interview/session/${sessionId}/complete`)
          setReport(r); setLoading(false)
        }
      } catch (e) { console.error(e); setLoading(false) }
    }
    load()
  }, [sessionId])

  if (loading) return <div className="min-h-screen flex items-center justify-center text-gray-400">Generating report...</div>
  if (!report) return <div className="min-h-screen flex items-center justify-center text-red-400">Failed to load report.</div>

  return (
    <div className="min-h-screen p-6 max-w-3xl mx-auto space-y-6">
      <div className="text-center space-y-4">
        <h1 className="text-3xl font-bold text-white">Interview Report</h1>
        <div className="flex items-center justify-center gap-6">
          <ScoreRing score={report.overall_score} />
          <div className="text-left">
            <div className={`text-2xl font-bold ${report.pass ? 'text-green-400' : 'text-red-400'}`}>
              {report.pass ? '✓ PASS' : '✗ NOT PASS'}
            </div>
            <p className="text-gray-400 text-sm mt-1 max-w-xs">{report.summary}</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
          <h3 className="text-green-400 font-semibold mb-3">✓ Strengths</h3>
          <ul className="space-y-1">{(report.strengths || []).map((s, i) => <li key={i} className="text-gray-300 text-sm">• {s}</li>)}</ul>
        </div>
        <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
          <h3 className="text-red-400 font-semibold mb-3">✗ Areas to Improve</h3>
          <ul className="space-y-1">{(report.weaknesses || []).map((w, i) => <li key={i} className="text-gray-300 text-sm">• {w}</li>)}</ul>
        </div>
      </div>

      <div className="bg-gray-900 rounded-xl p-4 border border-gray-800">
        <h3 className="text-gray-300 font-semibold mb-2">Hiring Recommendation</h3>
        <p className="text-gray-400 text-sm">{report.hiring_recommendation}</p>
      </div>

      <div className="space-y-3">
        <h3 className="text-white font-semibold text-lg">Per-Question Breakdown</h3>
        {(report.per_question || []).map((pq, i) => (
          <div key={i} className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <button onClick={() => setExpanded(e => ({ ...e, [i]: !e[i] }))} className="w-full flex items-center justify-between p-4 text-left hover:bg-gray-800 transition-colors">
              <span className="text-gray-200 text-sm font-medium flex-1 mr-4">{pq.question}</span>
              <div className="flex items-center gap-3 flex-shrink-0">
                <span className={`text-sm font-bold ${pq.score >= 70 ? 'text-green-400' : pq.score >= 50 ? 'text-yellow-400' : 'text-red-400'}`}>{pq.score}/100</span>
                <span className="text-gray-500 text-xs">{expanded[i] ? '▲' : '▼'}</span>
              </div>
            </button>
            {expanded[i] && (
              <div className="px-4 pb-4 space-y-2 border-t border-gray-800 pt-3">
                <p className="text-gray-400 text-sm">{pq.feedback}</p>
                {pq.what_was_good && <p className="text-green-400 text-xs">✓ {pq.what_was_good}</p>}
                {pq.what_was_missing && <p className="text-red-400 text-xs">✗ {pq.what_was_missing}</p>}
              </div>
            )}
          </div>
        ))}
      </div>

      <button onClick={() => navigate('/')} className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl transition-colors">
        Start New Interview →
      </button>
    </div>
  )
}
