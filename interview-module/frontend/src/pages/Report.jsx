import React, { useState, useEffect } from 'react'
import { useParams, useNavigate, useLocation } from 'react-router-dom'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || ''

function ScoreRing({ score }) {
  const colorClass = score >= 70
    ? 'border-emerald-500 text-emerald-600'
    : score >= 50
      ? 'border-amber-400 text-amber-600'
      : 'border-red-400 text-red-600'
  return (
    <div className={`w-28 h-28 rounded-full border-8 ${colorClass} flex items-center justify-center flex-shrink-0`}>
      <span className="text-3xl font-bold">{score}</span>
    </div>
  )
}

export default function Report() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const { state } = useLocation()
  const isTest = state?.isTest ?? true  // default to showing report if navigated directly
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

  // Real candidate interview — show thank you, not the report
  if (!isTest && !loading) return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-6 p-6 text-center">
      <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 text-2xl">✓</div>
      <div>
        <h2 className="text-xl font-bold text-slate-900 mb-2">Interview Complete</h2>
        <p className="text-slate-500 text-sm max-w-sm">
          Thank you for completing your screening interview. The recruiting team will review your responses and be in touch soon.
        </p>
      </div>
    </div>
  )

  if (loading) return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-3 text-slate-400">
      <div className="spinner" />
      <p className="text-sm">Generating report…</p>
    </div>
  )

  if (!report) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center text-red-500 text-sm">
      Failed to load report.
    </div>
  )

  const scoreLabel = report.overall_score >= 70 ? 'text-emerald-600' : report.overall_score >= 50 ? 'text-amber-600' : 'text-red-600'

  return (
    <div className="min-h-screen bg-slate-50 py-10 px-6">
      <div className="max-w-3xl mx-auto space-y-6 animate-fade-in">

        {/* Header */}
        <div className="text-center">
          <h1 className="text-2xl font-bold text-slate-900">Interview Report</h1>
        </div>

        {/* Overall score card */}
        <div className="card p-6">
          <div className="flex flex-col sm:flex-row items-center sm:items-start gap-4 sm:gap-6">
            <ScoreRing score={report.overall_score} />
            <div className="flex-1 text-center sm:text-left">
              <div className={`text-xl font-bold mb-1 ${scoreLabel}`}>
                {report.pass ? '✓ Pass' : '✗ Did not pass'}
              </div>
              <p className="text-slate-600 text-sm leading-relaxed">{report.summary}</p>
            </div>
          </div>
        </div>

        {/* Strengths / Weaknesses */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-emerald-700 mb-3 flex items-center gap-1.5">
              <span className="w-4 h-4 rounded-full bg-emerald-100 flex items-center justify-center text-[10px]">✓</span>
              Strengths
            </h3>
            <ul className="space-y-1.5">
              {(report.strengths || []).map((s, i) => (
                <li key={i} className="text-slate-600 text-sm flex gap-2">
                  <span className="text-emerald-500 mt-0.5">•</span>{s}
                </li>
              ))}
            </ul>
          </div>
          <div className="card p-5">
            <h3 className="text-sm font-semibold text-red-600 mb-3 flex items-center gap-1.5">
              <span className="w-4 h-4 rounded-full bg-red-100 flex items-center justify-center text-[10px]">✗</span>
              Areas to Improve
            </h3>
            <ul className="space-y-1.5">
              {(report.weaknesses || []).map((w, i) => (
                <li key={i} className="text-slate-600 text-sm flex gap-2">
                  <span className="text-red-400 mt-0.5">•</span>{w}
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Recommendation */}
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-slate-700 mb-1">Hiring Recommendation</h3>
          <p className="text-slate-600 text-sm">{report.hiring_recommendation}</p>
        </div>

        {/* Per-question breakdown */}
        <div>
          <h3 className="text-base font-semibold text-slate-800 mb-3">Per-Question Breakdown</h3>
          <div className="space-y-2">
            {(report.per_question || []).map((pq, i) => {
              const scoreColor = pq.score >= 70
                ? 'text-emerald-600 bg-emerald-50'
                : pq.score >= 50
                  ? 'text-amber-600 bg-amber-50'
                  : 'text-red-600 bg-red-50'
              return (
                <div key={i} className="card overflow-hidden">
                  <button
                    onClick={() => setExpanded(e => ({ ...e, [i]: !e[i] }))}
                    className="w-full flex items-center justify-between p-4 text-left hover:bg-slate-50 transition-colors"
                  >
                    <span className="text-slate-700 text-sm font-medium flex-1 mr-4">{pq.question}</span>
                    <div className="flex items-center gap-3 flex-shrink-0">
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${scoreColor}`}>
                        {pq.score}/100
                      </span>
                      <span className="text-slate-400 text-xs">{expanded[i] ? '▲' : '▼'}</span>
                    </div>
                  </button>
                  {expanded[i] && (
                    <div className="px-4 pb-4 space-y-2 border-t border-slate-100 pt-3">
                      <p className="text-slate-600 text-sm">{pq.feedback}</p>
                      {pq.what_was_good && (
                        <p className="text-emerald-600 text-xs flex gap-1.5">
                          <span>✓</span>{pq.what_was_good}
                        </p>
                      )}
                      {pq.what_was_missing && (
                        <p className="text-red-500 text-xs flex gap-1.5">
                          <span>✗</span>{pq.what_was_missing}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        <button onClick={() => navigate('/')} className="btn btn-primary w-full">
          Start New Interview →
        </button>

      </div>
    </div>
  )
}
