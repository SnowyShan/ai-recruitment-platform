import React, { useState, useEffect } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || ''

const DIFFICULTY_LABELS = ['', 'Intern', 'Junior', 'Mid-Level', 'Senior', 'Staff / Principal']
const SENIORITY_OPTIONS = ['junior', 'mid', 'senior', 'staff']

export default function Setup() {
  const navigate = useNavigate()
  const [jobDescription, setJobDescription] = useState('')
  const [resumeText, setResumeText] = useState('')
  const [difficulty, setDifficulty] = useState(3)
  const [seniority, setSeniority] = useState('senior')
  const [timeLimit, setTimeLimit] = useState(45)
  const [numQuestions, setNumQuestions] = useState(8)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [hardcodedQuestions, setHardcodedQuestions] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [folders, setFolders] = useState([])
  const [activeFolder, setActiveFolder] = useState(null)
  const [prefilling, setPrefilling] = useState(false)

  useEffect(() => {
    axios.get(`${API}/api/interview/testdata`).then(({ data }) => {
      setFolders(data.folders)
    }).catch(() => {})
  }, [])

  const loadFolder = async (folder) => {
    setPrefilling(true)
    setActiveFolder(folder)
    try {
      const { data } = await axios.get(`${API}/api/interview/testdata/${folder}`)
      setJobDescription(data.job_description)
      setResumeText(data.resume)
    } catch (e) {
      console.warn('Could not load test data:', e)
    }
    setPrefilling(false)
  }

  const start = async () => {
    if (!jobDescription.trim() || !resumeText.trim()) {
      setError('Please fill in both job description and resume.')
      return
    }
    setError('')
    setLoading(true)
    try {
      const hardcoded = hardcodedQuestions.trim()
        ? hardcodedQuestions.split('\n').map(q => q.trim()).filter(Boolean)
        : null
      const { data } = await axios.post(`${API}/api/interview/session`, {
        job_description: jobDescription,
        resume_text: resumeText,
        difficulty,
        seniority_bar: seniority,
        time_limit: timeLimit,
        num_questions: numQuestions,
        hardcoded_questions: hardcoded,
      })
      navigate(`/interview/${data.session_id}`, {
        state: { questions: data.questions, timeLimit: data.time_limit }
      })
    } catch (e) {
      setError('Failed to start session. Please try again.')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
      <div className="w-full max-w-2xl space-y-6 animate-fade-in">

        {/* Header */}
        <div className="text-center">
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">AI Screening Interview</h1>
          <p className="text-slate-500 mt-1 text-sm">Select a test profile or fill in manually</p>
        </div>

        {/* Test data selector */}
        {folders.length > 0 && (
          <div className="card p-4">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-3">Load Test Data</p>
            <div className="flex flex-wrap gap-2">
              {folders.map(f => (
                <button
                  key={f}
                  onClick={() => loadFolder(f)}
                  disabled={prefilling}
                  className={`px-4 py-2 rounded-xl text-sm font-medium border transition-colors
                    ${activeFolder === f
                      ? 'bg-primary-600 text-white border-primary-600'
                      : 'bg-white text-slate-600 border-slate-200 hover:border-primary-400 hover:text-primary-600'
                    }`}
                >
                  {prefilling && activeFolder === f ? 'Loading…' : f}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="card p-6 space-y-5">
          {/* Job Description */}
          <div>
            <label className="label">Job Description</label>
            <textarea
              value={jobDescription}
              onChange={e => setJobDescription(e.target.value)}
              rows={5}
              className="input resize-none font-mono text-xs"
              placeholder="Paste job description here…"
            />
          </div>

          {/* Resume */}
          <div>
            <label className="label">Candidate Resume</label>
            <textarea
              value={resumeText}
              onChange={e => setResumeText(e.target.value)}
              rows={5}
              className="input resize-none font-mono text-xs"
              placeholder="Paste resume text here…"
            />
          </div>

          {/* Basic config */}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="label">Difficulty — {DIFFICULTY_LABELS[difficulty]}</label>
              <input type="range" min={1} max={5} value={difficulty}
                onChange={e => setDifficulty(Number(e.target.value))}
                className="w-full accent-primary-600" />
              <div className="flex justify-between text-xs text-slate-400 mt-0.5">
                <span>Intern</span><span>Staff</span>
              </div>
            </div>
            <div>
              <label className="label">Seniority Bar</label>
              <select value={seniority} onChange={e => setSeniority(e.target.value)} className="input">
                {SENIORITY_OPTIONS.map(o => (
                  <option key={o} value={o}>{o.charAt(0).toUpperCase() + o.slice(1)}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Time Limit (min)</label>
              <input type="number" min={10} max={120} value={timeLimit}
                onChange={e => setTimeLimit(Number(e.target.value))}
                className="input" />
            </div>
          </div>

          {/* Advanced */}
          <div>
            <button
              onClick={() => setShowAdvanced(v => !v)}
              className="text-sm text-primary-600 hover:text-primary-700 font-medium"
            >
              {showAdvanced ? '▾ Hide advanced options' : '▸ Advanced options'}
            </button>
            {showAdvanced && (
              <div className="mt-4 space-y-4 p-4 bg-slate-50 rounded-xl border border-slate-200">
                <div>
                  <label className="label">Number of Questions</label>
                  <input type="number" min={3} max={20} value={numQuestions}
                    onChange={e => setNumQuestions(Number(e.target.value))}
                    className="input w-32" />
                </div>
                <div>
                  <label className="label">Hardcoded Questions <span className="text-slate-400 font-normal">(one per line)</span></label>
                  <textarea
                    value={hardcodedQuestions}
                    onChange={e => setHardcodedQuestions(e.target.value)}
                    rows={4}
                    className="input resize-none text-sm"
                    placeholder="What is the difference between struct and class in Swift?"
                  />
                </div>
              </div>
            )}
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          <button
            onClick={start}
            disabled={loading}
            className="btn btn-primary w-full"
          >
            {loading ? 'Generating questions…' : 'Start Interview →'}
          </button>
        </div>

        <div className="text-center">
          <Link to="/settings" className="text-xs text-slate-400 hover:text-slate-600 transition-colors">
            ⚙ Evaluation Settings
          </Link>
        </div>
      </div>
    </div>
  )
}
