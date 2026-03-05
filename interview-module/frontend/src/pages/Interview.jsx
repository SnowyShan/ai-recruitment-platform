import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import axios from 'axios'

// ── TTS helpers ───────────────────────────────────────────────────────────────

const TTS_STORAGE_KEY = 'interview_tts_enabled'

function getTTSEnabled() {
  try { return localStorage.getItem(TTS_STORAGE_KEY) !== 'false' } catch { return true }
}

function setTTSEnabled(val) {
  try { localStorage.setItem(TTS_STORAGE_KEY, val ? 'true' : 'false') } catch {}
}

// Pick the best available voice — prefer natural-sounding macOS/iOS voices
function getBestVoice() {
  const voices = window.speechSynthesis?.getVoices() || []
  const preferred = [
    'Samantha', 'Alex', 'Karen', 'Daniel',   // macOS neural voices
    'Google US English', 'Microsoft Aria',     // Chrome/Windows
  ]
  for (const name of preferred) {
    const v = voices.find(v => v.name.includes(name))
    if (v) return v
  }
  return voices.find(v => v.lang.startsWith('en')) || voices[0] || null
}

const API = import.meta.env.VITE_API_URL || ''
const MAIN_API = import.meta.env.VITE_MAIN_API_URL || ''

export default function Interview() {
  const { sessionId } = useParams()
  const { state } = useLocation()
  const navigate = useNavigate()

  const [questions, setQuestions] = useState(state?.questions || [])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [transcript, setTranscript] = useState('')
  const [isRecording, setIsRecording] = useState(false)
  const [timeLeft, setTimeLeft] = useState((state?.timeLimit || 45) * 60)
  const [finishing, setFinishing] = useState(false)
  const [isWrapUp, setIsWrapUp] = useState(false)
  const isWrapUpRef = useRef(false)
  const [finishing2, setFinishing2] = useState(false)

  const [searchParams] = useSearchParams()
  const [tokenError, setTokenError] = useState(null)
  const [tokenChecked, setTokenChecked] = useState(false)
  const tokenRef = useRef(searchParams.get('token'))

  const recognitionRef = useRef(null)
  const timerRef = useRef(null)
  const transcriptRef = useRef('')
  const fullTranscriptRef = useRef('')
  const questionAnswersRef = useRef({}) // live per-question answer map, updated on every onresult
  const finishRef = useRef(null)
  const currentIndexRef = useRef(0)
  const questionsRef = useRef(questions)

  // TTS state
  const [ttsEnabled, setTtsEnabled] = useState(getTTSEnabled)
  const [isSpeaking, setIsSpeaking] = useState(false)
  const ttsEnabledRef = useRef(ttsEnabled)
  const ttsCancelRef = useRef(false)
  const ttsKeepaliveRef = useRef(null)

  useEffect(() => {
    ttsEnabledRef.current = ttsEnabled
    setTTSEnabled(ttsEnabled)
  }, [ttsEnabled])

  useEffect(() => { currentIndexRef.current = currentIndex }, [currentIndex])
  useEffect(() => { questionsRef.current = questions }, [questions])
  useEffect(() => { isWrapUpRef.current = isWrapUp }, [isWrapUp])

  useEffect(() => {
    if (!state?.questions) {
      axios.get(`${API}/api/interview/session/${sessionId}`).then(({ data }) => {
        setQuestions(data.questions)
        setTimeLeft(data.time_limit * 60)
      })
    }
  }, [sessionId])

  // Validate invite token if present
  useEffect(() => {
    const token = tokenRef.current
    if (!token) { setTokenChecked(true); return }
    const validate = async () => {
      try {
        const { data } = await axios.get(`${MAIN_API}/api/screenings/validate-token/${token}`)
        if (!data.valid) { setTokenError(data.reason); setTokenChecked(true); return }
        // Mark in_progress
        await axios.post(`${MAIN_API}/api/screenings/start-from-token/${token}`, {})
      } catch (e) { console.warn('Token validation failed', e) }
      setTokenChecked(true)
    }
    validate()
  }, [])

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

  const formatTime = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`

  // ── TTS ──────────────────────────────────────────────────────────────────────

  const cancelSpeech = () => {
    ttsCancelRef.current = true
    clearInterval(ttsKeepaliveRef.current)
    window.speechSynthesis?.cancel()
    setIsSpeaking(false)
  }

  const speakThenRecord = useCallback((text) => {
    cancelSpeech()
    if (!ttsEnabledRef.current || !window.speechSynthesis) {
      startRecording()
      return
    }

    ttsCancelRef.current = false
    setIsSpeaking(true)

    // Chrome bug: voices may not be loaded yet on first call
    const doSpeak = () => {
      if (ttsCancelRef.current) return
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.rate = 0.92
      utterance.pitch = 1
      utterance.volume = 1
      const voice = getBestVoice()
      if (voice) utterance.voice = voice

      utterance.onend = () => {
        clearInterval(ttsKeepaliveRef.current)
        setIsSpeaking(false)
        if (!ttsCancelRef.current) startRecording()
      }
      utterance.onerror = () => {
        clearInterval(ttsKeepaliveRef.current)
        setIsSpeaking(false)
        if (!ttsCancelRef.current) startRecording()
      }

      window.speechSynthesis.speak(utterance)

      // Chrome-only keepalive: speechSynthesis silently stops after ~15s on Chrome.
      // Do NOT apply on Safari/iOS — pause()+resume() restarts the utterance there.
      const isChrome = /Chrome/.test(navigator.userAgent) && !/Edg|OPR|Safari/.test(navigator.userAgent)
      if (isChrome) {
        ttsKeepaliveRef.current = setInterval(() => {
          if (window.speechSynthesis.speaking) {
            window.speechSynthesis.pause()
            window.speechSynthesis.resume()
          }
        }, 10000)
      }
    }

    // Voices may not be loaded yet (Chrome loads async)
    if (window.speechSynthesis.getVoices().length > 0) {
      doSpeak()
    } else {
      window.speechSynthesis.onvoiceschanged = () => {
        window.speechSynthesis.onvoiceschanged = null
        doSpeak()
      }
      // Fallback if onvoiceschanged never fires
      setTimeout(doSpeak, 500)
    }
  }, [])

  useEffect(() => {
    if (questionsRef.current.length === 0) return
    transcriptRef.current = ''
    setTranscript('')
    const q = questionsRef.current[currentIndex]
    speakThenRecord(q?.voice_text || q?.question || '')
  }, [currentIndex, speakThenRecord])

  useEffect(() => {
    if (questions.length > 0 && currentIndex === 0) {
      transcriptRef.current = ''
      setTranscript('')
      const q = questions[0]
      speakThenRecord(q?.voice_text || q?.question || '')
    }
  }, [questions.length, speakThenRecord])

  const replayQuestion = () => {
    const q = questionsRef.current[currentIndexRef.current]
    if (!q) return
    cancelSpeech()
    stopRecording()
    speakThenRecord(q.voice_text || q.question)
  }

  const toggleTTS = () => {
    if (isSpeaking) cancelSpeech()
    setTtsEnabled(v => !v)
  }

  // ── Recording ─────────────────────────────────────────────────────────────

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
      // Always keep the latest answer for this question, regardless of how the session ends
      if (t.trim()) {
        questionAnswersRef.current[currentIndexRef.current] = t
      }
    }
    r.onend = () => {
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
    // Prefer the live-accumulated answer over the point-in-time capture
    const bestAnswer = skipped ? '[SKIPPED]' : (questionAnswersRef.current[idx] || answerText || '').trim() || '(no answer)'
    const answer = `${bestAnswer}\n`
    fullTranscriptRef.current += `${marker}${answer}\n`
    // Mark this question as committed so we don't double-count it
    if (!skipped) delete questionAnswersRef.current[idx]
  }

  // Build full transcript from any uncommitted answers still in questionAnswersRef
  const buildFinalTranscript = () => {
    const qs = questionsRef.current
    // Commit any remaining uncommitted answers
    qs.forEach((q, idx) => {
      if (questionAnswersRef.current[idx] !== undefined) {
        const marker = `[Q${idx + 1}: ${q.question}]\n`
        fullTranscriptRef.current += `${marker}${questionAnswersRef.current[idx].trim()}\n\n`
        delete questionAnswersRef.current[idx]
      }
    })
    return fullTranscriptRef.current
  }

  const advance = () => {
    const idx = currentIndexRef.current
    const qs = questionsRef.current
    transcriptRef.current = ''
    setTranscript('')
    if (idx + 1 >= qs.length) finishRef.current?.()
    else setCurrentIndex(idx + 1)
  }

  const nextQuestion = () => {
    const answer = transcriptRef.current  // capture before stop clears it
    cancelSpeech()
    stopRecording()
    commitToTranscript(answer, false)
    advance()
  }

  const skip = () => {
    cancelSpeech()
    stopRecording()
    commitToTranscript('', true)
    advance()
  }

  const finish = useCallback(async () => {
    const answer = transcriptRef.current  // capture before stop clears it
    clearInterval(timerRef.current)
    cancelSpeech()
    stopRecording()
    commitToTranscript(answer, false)
    const fullTranscript = buildFinalTranscript()
    setFinishing(true)
    try {
      await axios.post(`${API}/api/interview/session/${sessionId}/complete`, {
        full_transcript: fullTranscript,
        questions: questionsRef.current,
      })
    } catch (e) { console.error(e) }
    if (tokenRef.current) {
      navigate('/thank-you')
    } else {
      navigate(`/report/${sessionId}`, { state: { isTest: true } })
    }
  }, [sessionId, navigate])

  useEffect(() => { finishRef.current = finish }, [finish])

  const q = questions[currentIndex]
  const progress = questions.length > 0 ? (currentIndex / questions.length) * 100 : 0

  const timerColor = isWrapUp
    ? 'text-amber-600'
    : timeLeft < 60
      ? 'text-red-600'
      : timeLeft < 300
        ? 'text-amber-500'
        : 'text-emerald-600'

  if (tokenError) return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4 p-6 text-center">
      <div className="w-12 h-12 rounded-full bg-red-100 flex items-center justify-center text-red-600 text-xl">✗</div>
      <h2 className="text-lg font-semibold text-slate-800">Interview Unavailable</h2>
      <p className="text-slate-500 text-sm max-w-sm">{tokenError}</p>
    </div>
  )

  if (!tokenChecked) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="spinner" />
    </div>
  )

  if (finishing) return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4 text-slate-500">
      <div className="spinner" />
      <p className="text-sm font-medium">Submitting your interview…</p>
    </div>
  )

  if (!q) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center text-slate-400 text-sm">
      Loading…
    </div>
  )

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col p-6 max-w-3xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <p className="text-sm font-medium text-slate-500">Question {currentIndex + 1} of {questions.length}</p>
          {isWrapUp && (
            <p className="text-xs text-amber-600 font-medium mt-0.5">Wrap-up time — finish your thought</p>
          )}
          {!isWrapUp && timeLeft < 60 && (
            <p className="text-xs text-red-500 mt-0.5">{formatTime(timeLeft)} left · 2:00 wrap-up follows</p>
          )}
        </div>
        <div className="text-right">
          <span className={`font-mono text-2xl font-bold ${timerColor}`}>{formatTime(timeLeft)}</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1.5 bg-slate-200 rounded-full mb-8">
        <div
          className="h-1.5 bg-primary-600 rounded-full transition-all duration-500"
          style={{ width: `${progress}%` }}
        />
      </div>

      {/* Question card */}
      <div className="card p-6 mb-6">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="badge badge-primary">{q.topic || 'Technical'}</span>
            {isSpeaking && (
              <span className="inline-flex items-center gap-1 text-xs text-indigo-500 font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 animate-pulse inline-block" />
                Speaking…
              </span>
            )}
            {isRecording && !isSpeaking && (
              <span className="inline-flex items-center gap-1 text-xs text-red-500 font-medium">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse inline-block" />
                Recording
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {/* Replay button — only show when not currently speaking */}
            {ttsEnabled && !isSpeaking && (
              <button
                onClick={replayQuestion}
                title="Replay question"
                className="p-1.5 rounded-lg text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 transition-colors text-sm"
              >
                ↺
              </button>
            )}
            {/* Mute/unmute toggle */}
            <button
              onClick={toggleTTS}
              title={ttsEnabled ? 'Mute voice (read questions yourself)' : 'Unmute voice'}
              className={`p-1.5 rounded-lg transition-colors text-sm ${
                ttsEnabled
                  ? 'text-indigo-600 hover:bg-indigo-50'
                  : 'text-slate-300 hover:text-slate-500 hover:bg-slate-100'
              }`}
            >
              {ttsEnabled ? '🔊' : '🔇'}
            </button>
          </div>
        </div>
        <p className="text-lg font-medium text-slate-800 leading-relaxed">{q.question}</p>
        {isSpeaking && (
          <p className="text-xs text-slate-400 mt-3 italic">Listening starts automatically after the question is read…</p>
        )}
      </div>

      {/* Transcript (debug) */}
      <div className="card p-4 mb-4 flex-1 min-h-32">
        {transcript ? (
          <p className="text-slate-700 text-sm leading-relaxed">{transcript}</p>
        ) : (
          <p className="text-slate-400 text-sm italic">
            {isRecording ? 'Listening… speak your answer' : 'Microphone inactive'}
          </p>
        )}
      </div>

      {/* Controls */}
      <div className="flex gap-3">
        <button onClick={nextQuestion} className="btn btn-primary flex-1">
          {currentIndex + 1 >= questions.length ? 'Finish Interview' : 'Next Question →'}
        </button>
        <button onClick={skip} className="btn btn-secondary px-5">
          Skip
        </button>
        <button onClick={finish} className="btn btn-danger px-5">
          End
        </button>
      </div>
    </div>
  )
}
