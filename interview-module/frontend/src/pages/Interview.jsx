import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || ''

export default function Interview() {
  const { sessionId } = useParams()
  const { state } = useLocation()
  const navigate = useNavigate()

  const [questions, setQuestions] = useState(state?.questions || [])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [transcript, setTranscript] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [timeLeft, setTimeLeft] = useState((state?.timeLimit || 45) * 60)
  const [isWrapUp, setIsWrapUp] = useState(false)
  const isWrapUpRef = useRef(false)
  const [finishing, setFinishing] = useState(false)

  const recognitionRef = useRef(null)
  const timerRef = useRef(null)
  const transcriptRef = useRef('')
  const fullTranscriptRef = useRef('')
  const finishRef = useRef(null)         // stable ref to finish so timer closure is never stale
  const currentIndexRef = useRef(0)      // stable ref so advance() always reads latest index
  const questionsRef = useRef(questions) // stable ref so finish() always reads latest questions

  // Keep refs in sync
  useEffect(() => { currentIndexRef.current = currentIndex }, [currentIndex])
  useEffect(() => { questionsRef.current = questions }, [questions])

  // Load session if no state
  useEffect(() => {
    if (!state?.questions) {
      axios.get(`${API}/api/interview/session/${sessionId}`).then(({ data }) => {
        setQuestions(data.questions)
        setTimeLeft(data.time_limit * 60)
      })
    }
  }, [sessionId])

  // Timer — uses finishRef so it always calls the latest finish()
  useEffect(() => {
    timerRef.current = setInterval(() => {
      setTimeLeft(t => {
        if (t <= 1) {
          if (isWrapUpRef.current) {
            clearInterval(timerRef.current)
            finishRef.current?.()
            return 0
          } else {
            isWrapUpRef.current = true
            setIsWrapUp(true)
            return 120
          }
        }
        return t - 1
      })
    }, 1000)
    return () => clearInterval(timerRef.current)
  }, [])

  // Auto-start recording only when currentIndex changes (not on every render)
  useEffect(() => {
    if (questionsRef.current.length === 0) return
    transcriptRef.current = ''
    setTranscript('')
    startRecording()
    // no cleanup stopRecording here — we call it explicitly before advancing
  }, [currentIndex]) // eslint-disable-line react-hooks/exhaustive-deps

  // Start recording once questions load (first question)
  useEffect(() => {
    if (questions.length > 0 && currentIndex === 0) {
      transcriptRef.current = ''
      setTranscript('')
      startRecording()
    }
  }, [questions.length]) // eslint-disable-line react-hooks/exhaustive-deps

  const formatTime = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

  const startRecording = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    if (recognitionRef.current) {
      recognitionRef.current.onend = null
      try { recognitionRef.current.stop() } catch (_) {}
      recognitionRef.current = null
    }
    const r = new SR()
    r.continuous = true
    r.interimResults = true
    r.onresult = e => {
      const t = Array.from(e.results).map(r => r[0].transcript).join(' ')
      transcriptRef.current = t
      setTranscript(t)
    }
    r.onend = () => {
      // auto-restart only if this is still the active recognition instance
      if (recognitionRef.current === r) {
        try { r.start() } catch (_) {}
      }
    }
    r.start()
    recognitionRef.current = r
    setIsRecording(true)
  }

  const stopRecording = () => {
    if (recognitionRef.current) {
      recognitionRef.current.onend = null
      try { recognitionRef.current.stop() } catch (_) {}
      recognitionRef.current = null
    }
    setIsRecording(false)
  }

  const commitToTranscript = (answerText, skipped = false) => {
    const idx = currentIndexRef.current
    const q = questionsRef.current[idx]
    if (!q) return
    const marker = `[Q${idx + 1}: ${q.question}]\n`
    const answer = skipped ? '[SKIPPED]\n' : `${answerText.trim() || '(no answer)'}\n`
    fullTranscriptRef.current += `${marker}${answer}\n`
  }

  const advance = () => {
    const idx = currentIndexRef.current
    const qs = questionsRef.current
    transcriptRef.current = ''
    setTranscript('')
    if (idx + 1 >= qs.length) {
      finishRef.current?.()
    } else {
      setCurrentIndex(idx + 1)
    }
  }

  const nextQuestion = () => {
    stopRecording()
    commitToTranscript(transcriptRef.current, false)
    advance()
  }

  const skip = () => {
    stopRecording()
    commitToTranscript('', true)
    advance()
  }

  const finish = useCallback(async () => {
    clearInterval(timerRef.current)
    stopRecording()
    commitToTranscript(transcriptRef.current, false)
    setFinishing(true)
    try {
      await axios.post(`${API}/api/interview/session/${sessionId}/complete`, {
        full_transcript: fullTranscriptRef.current,
        questions: questionsRef.current,
      })
    } catch (e) { console.error(e) }
    navigate(`/report/${sessionId}`)
  }, [sessionId, navigate])

  useEffect(() => { isWrapUpRef.current = isWrapUp }, [isWrapUp])

  // Keep finishRef pointing to latest finish
  useEffect(() => { finishRef.current = finish }, [finish])

  const q = questions[currentIndex]
  const progress = questions.length > 0 ? (currentIndex / questions.length) * 100 : 0
  const timerColor = isWrapUp ? 'text-orange-400' : timeLeft < 60 ? 'text-red-400' : timeLeft < 300 ? 'text-yellow-400' : 'text-green-400'

  if (finishing) return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 text-gray-300">
      <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      <p>Generating your report...</p>
    </div>
  )

  if (!q) return <div className="min-h-screen flex items-center justify-center text-gray-400">Loading...</div>

  return (
    <div className="min-h-screen flex flex-col p-6 max-w-3xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <span className="text-gray-400 text-sm">Question {currentIndex + 1} of {questions.length}</span>
        <div className="text-right">
          <span className={`font-mono text-2xl font-bold ${timerColor}`}>{formatTime(timeLeft)}</span>
          {isWrapUp && <p className="text-orange-400 text-xs mt-0.5 font-medium">Wrap-up time — finish your thought</p>}
          {!isWrapUp && timeLeft < 60 && <p className="text-red-400 text-xs mt-0.5">{formatTime(timeLeft)} left · 2:00 wrap-up follows</p>}
        </div>
      </div>

      {/* Progress */}
      <div className="w-full h-1.5 bg-gray-800 rounded-full mb-8">
        <div className="h-1.5 bg-blue-500 rounded-full transition-all duration-500" style={{ width: `${progress}%` }} />
      </div>

      {/* Question */}
      <div className="bg-gray-900 rounded-2xl p-6 border border-gray-800 mb-6">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-xs bg-blue-900 text-blue-300 px-2 py-0.5 rounded-full">{q.topic || 'Technical'}</span>
          {isRecording && (
            <span className="text-xs text-red-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse inline-block" />
              Recording
            </span>
          )}
        </div>
        <p className="text-xl text-white leading-relaxed">{q.question}</p>
      </div>

      {/* Transcript (debug) */}
      <div className="bg-gray-900 rounded-2xl p-4 border border-gray-800 mb-4 min-h-32 flex-1">
        {transcript ? (
          <p className="text-gray-200 text-sm leading-relaxed">{transcript}</p>
        ) : (
          <p className="text-gray-600 text-sm italic">
            {isRecording ? 'Listening... speak your answer' : 'Microphone inactive'}
          </p>
        )}
      </div>

      {/* Controls */}
      <div className="flex gap-3">
        <button
          onClick={nextQuestion}
          className="flex-1 py-3 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl transition-colors"
        >
          {currentIndex + 1 >= questions.length ? 'Finish Interview' : 'Next Question →'}
        </button>
        <button
          onClick={skip}
          className="px-5 py-3 bg-gray-800 hover:bg-gray-700 text-gray-400 rounded-xl transition-colors text-sm"
        >
          Skip
        </button>
        <button
          onClick={finish}
          className="px-5 py-3 bg-red-900 hover:bg-red-800 text-red-300 rounded-xl transition-colors text-sm"
        >
          End Interview
        </button>
      </div>
    </div>
  )
}
