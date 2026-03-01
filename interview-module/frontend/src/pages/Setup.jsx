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
  const [seniorityBar, setSeniorityBar] = useState('senior')
  const [timeLimit, setTimeLimit] = useState(45)
  const [numQuestions, setNumQuestions] = useState(8)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [hardcodedQuestions, setHardcodedQuestions] = useState('')
  const [loading, setLoading] = useState(false)
  const [prefilling, setPrefilling] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    const prefill = async () => {
      setPrefilling(true)
      try {
        const { data } = await axios.get(`${API}/api/interview/testdata/random`)
        setJobDescription(data.job_description)
        setResumeText(data.resume)
      } catch (e) {
        console.warn('Could not load test data:', e)
      }
      setPrefilling(false)
    }
    prefill()
  }, [])

  const start = async () => {
    if (!jobDescription.trim() || !resumeText.trim()) {
      setError('Please fill in both job description and resume.')
      return
    }
    setLoading(true)
    setError('')
    try {
      let hq = null
      if (hardcodedQuestions.trim()) {
        try { hq = JSON.parse(hardcodedQuestions) } catch { setError('Hardcoded questions must be valid JSON array.'); setLoading(false); return }
      }
      const { data } = await axios.post(`${API}/api/interview/session`, {
        job_description: jobDescription,
        resume_text: resumeText,
        difficulty,
        seniority_bar: seniorityBar,
        time_limit: timeLimit,
        num_questions: numQuestions,
        hardcoded_questions: hq,
      })
      navigate(`/interview/${data.session_id}`, { state: { questions: data.questions, timeLimit: data.time_limit } })
    } catch (e) {
      setError(e?.response?.data?.detail || 'Failed to start interview. Is the backend running?')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="w-full max-w-2xl space-y-6">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-white mb-2">AI Interview</h1>
          <p className="text-gray-400">{prefilling ? 'Loading test data...' : 'Pre-filled with test data — edit or start directly'}</p>
        </div>

        <div className="bg-gray-900 rounded-2xl p-6 space-y-5 border border-gray-800">
          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Job Description</label>
            <textarea className="w-full h-36 bg-gray-800 border border-gray-700 rounded-lg p-3 text-sm text-gray-100 focus:outline-none focus:border-blue-500 resize-none" placeholder="Paste the job description here..." value={jobDescription} onChange={e => setJobDescription(e.target.value)} />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Resume (paste as text)</label>
            <textarea className="w-full h-36 bg-gray-800 border border-gray-700 rounded-lg p-3 text-sm text-gray-100 focus:outline-none focus:border-blue-500 resize-none" placeholder="Paste resume text here..." value={resumeText} onChange={e => setResumeText(e.target.value)} />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-3">
              Question Difficulty — <span className="text-blue-400">{DIFFICULTY_LABELS[difficulty]}</span>
            </label>
            <input type="range" min="1" max="5" value={difficulty} onChange={e => setDifficulty(Number(e.target.value))} className="w-full accent-blue-500" />
            <div className="flex justify-between text-xs text-gray-500 mt-1">
              {DIFFICULTY_LABELS.slice(1).map(l => <span key={l}>{l}</span>)}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">Expected Answer Bar</label>
            <div className="flex gap-2">
              {SENIORITY_OPTIONS.map(s => (
                <button key={s} onClick={() => setSeniorityBar(s)} className={`flex-1 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${seniorityBar === s ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'}`}>{s}</button>
              ))}
            </div>
          </div>

          <div className="flex gap-4">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-300 mb-2">Time Limit (minutes)</label>
              <input type="number" min="5" max="120" value={timeLimit} onChange={e => setTimeLimit(Number(e.target.value))} className="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-gray-100 focus:outline-none focus:border-blue-500" />
            </div>
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-300 mb-2">Number of Questions</label>
              <input type="number" min="1" max="20" value={numQuestions} onChange={e => setNumQuestions(Number(e.target.value))} className="w-full bg-gray-800 border border-gray-700 rounded-lg p-2 text-gray-100 focus:outline-none focus:border-blue-500" />
            </div>
          </div>

          <div>
            <button onClick={() => setShowAdvanced(!showAdvanced)} className="text-sm text-gray-500 hover:text-gray-300 transition-colors">
              {showAdvanced ? '▼' : '▶'} Advanced: Hardcoded Questions
            </button>
            {showAdvanced && (
              <textarea className="w-full h-24 mt-2 bg-gray-800 border border-gray-700 rounded-lg p-3 text-sm text-gray-100 focus:outline-none focus:border-blue-500 resize-none font-mono" placeholder='["Question 1?", "Question 2?"]' value={hardcodedQuestions} onChange={e => setHardcodedQuestions(e.target.value)} />
            )}
          </div>

          {error && <p className="text-red-400 text-sm">{error}</p>}

          <button onClick={start} disabled={loading} className="w-full py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white font-semibold rounded-xl transition-colors">
            {loading ? 'Generating questions...' : 'Start Interview →'}
          </button>
        </div>
      </div>
      <div className="text-center mt-6">
        <Link to="/settings" className="text-gray-600 hover:text-gray-400 text-xs transition-colors">⚙ Evaluation Settings</Link>
      </div>
    </div>
  )
}
