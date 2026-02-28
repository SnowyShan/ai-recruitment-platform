import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8001'

export default function Interview() {
  const { sessionId } = useParams()
  const { state } = useLocation()
  const navigate = useNavigate()

  const [questions, setQuestions] = useState(state?.questions || [])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [transcript, setTranscript] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [timeLeft, setTimeLeft] = useState((state?.timeLimit || 45) * 60)
  const [submitting, setSubmitting] = useState(false)
  const [answers, setAnswers] = useState({})
  const [evaluation, setEvaluation] = useState(null)

  const recognitionRef = useRef(null)
  const timerRef = useRef(null)

  // Load session if no state
  useEffect(() => {
    if (!state?.questions) {
      axios.get(`${API}/api/interview/session/${sessionId}`).then(({ data }) => {
        setQuestions(data.questions)
        setTimeLeft(data.time_limit * 60)
        setAnswers(data.answers || {})
      })
    }
  }, [sessionId])

  // Timer
  useEffect(() => {
    timerRef.current = setInterval(() => {
      setTimeLeft(t => {
        if (t <= 1) { clearInterval(timerRef.current); finish(); return 0 }
        return t - 1
      })
    }, 1000)
    return () => clearInterval(timerRef.current)
  }, [])

  const formatTime = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

  const startRecording = useCallback(() => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) { alert('Speech recognition not supported. Use Chrome.'); return }
    const r = new SR()
    r.continuous = true
    r.interimResults = true
    r.onresult = e => {
      const t = Array.from(e.results).map(r => r[0].transcript).join(' ')
      setTranscript(t)
    }
    r.start()
    recognitionRef.current = r
    setIsRecording(true)
  }, [])

  const stopRecording = useCallback(() => {
    recognitionRef.current?.stop()
    setIsRecording(false)
  }, [])

  const submitAnswer = async (answerText) => {
    if (!answerText.trim()) { skip(); return }
    setSubmitting(true)
    try {
      const { data } = await axios.post(`${API}/api/interview/session/${sessionId}/answer`, {
        question_index: currentIndex,
        answer: answerText,
      })
      setAnswers(prev => ({ ...prev, [currentIndex]: { answer: answerText, ...data.evaluation } }))
      setEvaluation(data.evaluation)
      setTimeout(() => {
        setEvaluation(null)
        setTranscript('')
        if (currentIndex + 1 >= questions.length) finish()
        else setCurrentIndex(i => i + 1)
      }, 2500)
    } catch (e) { console.error(e) }
    setSubmitting(false)
  }

  const skip = () => {
    setTranscript('')
    if (currentIndex + 1 >= questions.length) finish()
    else setCurrentIndex(i => i + 1)
  }

  const finish = async () => {
    clearInterval(timerRef.current)
    stopRecording()
    try {
      await axios.post(`${API}/api/interview/session/${sessionId}/complete`)
    } catch (e) { console.error(e) }
    navigate(`/report/${sessionId}`)
  }

  const q = questions[currentIndex]
  const progress = questions.length > 0 ? ((currentIndex) / questions.length) * 100 : 0
  const timerColor = timeLeft < 300 ? 'text-red-400' : timeLeft < 600 ? 'text-yellow-400' : 'text-green-400'

  if (!q) return <div className="min-h-screen flex items-center justify-center text-gray-400">Loading...</div>

  return (
    <div className="min-h-screen flex flex-col p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <span className="text-gray-400 text-sm">Question {currentIndex + 1} of {questions.length}</span>
        <span className={`font-mono text-2xl font-bold ${timerColor}`}>{formatTime(timeLeft)}</span>
      </div>

      {/* Progress */}
      <div className="w-full h-1.5 bg-gray-800 rounded-full mb-8">
        <div className="h-1.5 bg-blue-500 rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
      </div>

      {/* Question */}
      <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs bg-blue-900 text-blue-300 px-2 py-0.5 rounded-full">{q.topic || 'Technical'}</span>
        </div>
        <p className="text-xl text-white leading-relaxed">{q.question}</p>
      </div>

      {/* Transcript */}
      <div className="bg-gray-900 rounded-2xl p-4 border border-gray-800 mb-4 min-h-32 flex-1">
        {transcript ? (
          <p className="text-gray-200 text-sm leading-relaxed">{transcript}</p>
        ) : (
          <p className="text-gray-600 text-sm italic">{isRecording ? 'Listening... speak your answer' : 'Press "Start Recording" and speak your answer'}</p>
        )}
      </div>

      {/* Evaluation flash */}
      {evaluation && (
        <div className={`rounded-xl p-3 mb-4 text-sm font-medium text-center ${evaluation.pass ? 'bg-green-900 text-green-300' : 'bg-red-900 text-red-300'}`}>
          Score: {evaluation.score}/100 — {evaluation.pass ? '✓ Pass' : '✗ Needs improvement'}
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-3">
        {!isRecording ? (
          <button onClick={startRecording} className="flex-1 py-3 bg-red-600 hover:bg-red-500 text-white font-semibold rounded-xl transition-colors flex items-center justify-center gap-2">
            <span className="w-2 h-2 rounded-full bg-white animate-pulse" />
            Start Recording
          </button>
        ) : (
          <button onClick={stopRecording} className="flex-1 py-3 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-xl transition-colors">
            Stop Recording
          </button>
        )}
        <button onClick={() => submitAnswer(transcript)} disabled={submitting || !transcript} className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-600 text-white font-semibold rounded-xl transition-colors">
          {submitting ? 'Evaluating...' : 'Submit Answer'}
        </button>
        <button onClick={skip} className="px-5 py-3 bg-gray-800 hover:bg-gray-700 text-gray-400 rounded-xl transition-colors text-sm">
          Skip
        </button>
      </div>

      <button onClick={finish} className="mt-4 text-xs text-gray-600 hover:text-gray-400 text-center transition-colors">
        End interview early
      </button>
    </div>
  )
}
