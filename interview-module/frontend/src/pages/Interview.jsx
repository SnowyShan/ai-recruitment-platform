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

    // Pre-interview intro phase:
  //   'intro'    → instructions screen, mic not yet requested
  //   'granting' → getUserMedia in flight, spinner on button
  //   'ready'    → mic granted/denied, "Start Interview" button shown, Q0 audio pre-fetching
  //   'started'  → interview running
  const [introPhase, setIntroPhase] = useState('intro')
  const prefetchedAudioRef = useRef(null)

  const micReady  = introPhase === 'started'
  const started   = introPhase === 'started'

  const handleGrantMic = async () => {
    setIntroPhase('granting')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.getTracks().forEach(t => t.stop())
    } catch (_) {}  // denied — Web Speech API fallback will handle it
    setIntroPhase('ready')
  }

  // Pre-fetch Q0 audio while user reads instructions (after mic granted).
  // Cleanup cancels the store if introPhase changes before the fetch completes —
  // otherwise the stale blob lands in prefetchedAudioRef and gets played for Q2.
  useEffect(() => {
    if (introPhase !== 'ready' || questions.length === 0) return
    const text = questions[0]?.voice_text || questions[0]?.question || ''
    if (!text) return
    let cancelled = false
    axios.post(`${API}/api/interview/tts`, { text }, { responseType: 'blob' })
      .then(res => {
        if (!cancelled) prefetchedAudioRef.current = URL.createObjectURL(res.data)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [introPhase, questions])

  // "Start Interview" tap — this IS the user gesture that unlocks iOS audio autoplay
  const handleStart = () => setIntroPhase('started')

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

  const audioRef = useRef(null)   // current playing HTMLAudioElement
  const ttsGenRef = useRef(0)     // incremented on every cancel — stale axios responses self-discard

  const cancelSpeech = () => {
    ttsGenRef.current++            // invalidate any in-flight TTS requests
    ttsCancelRef.current = true
    clearInterval(ttsKeepaliveRef.current)
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.src = ''
      audioRef.current = null
    }
    window.speechSynthesis?.cancel()
    setIsSpeaking(false)
  }

  const speakThenRecord = useCallback((text) => {
    cancelSpeech()
    if (!ttsEnabledRef.current) {
      startRecording()
      return
    }

    ttsCancelRef.current = false
    const gen = ++ttsGenRef.current  // capture this call's generation

    // Use pre-fetched audio if available (Q0 is pre-fetched during instructions screen)
    const playBlob = (blobUrl) => {
      if (ttsGenRef.current !== gen) { URL.revokeObjectURL(blobUrl); return }  // stale — discard
      const audio = new Audio(blobUrl)
      audioRef.current = audio
      audio.onended = () => {
        URL.revokeObjectURL(blobUrl)
        audioRef.current = null
        setIsSpeaking(false)
        if (ttsGenRef.current === gen) startRecording()
      }
      audio.onerror = () => {
        URL.revokeObjectURL(blobUrl)
        audioRef.current = null
        setIsSpeaking(false)
        if (ttsGenRef.current === gen) startRecording()
      }
      audio.play()
        .then(() => { if (ttsGenRef.current === gen) setIsSpeaking(true) })
        .catch(() => {
          URL.revokeObjectURL(blobUrl)
          audioRef.current = null
          setIsSpeaking(false)
          if (ttsGenRef.current === gen) startRecording()
        })
    }

    if (prefetchedAudioRef.current) {
      const blobUrl = prefetchedAudioRef.current
      prefetchedAudioRef.current = null
      playBlob(blobUrl)
      return
    }

    // Fetch TTS audio from backend
    axios.post(`${API}/api/interview/tts`, { text }, { responseType: 'blob' })
      .then(res => {
        if (ttsGenRef.current !== gen) return  // stale — discard
        playBlob(URL.createObjectURL(res.data))
      })
      .catch(() => {
        // OpenAI TTS failed — fall back to browser speechSynthesis
        if (ttsCancelRef.current) return
        if (!window.speechSynthesis) {
          setIsSpeaking(false)
          startRecording()
          return
        }
        const utterance = new SpeechSynthesisUtterance(text)
        utterance.rate = 0.92
        const voice = getBestVoice()
        if (voice) utterance.voice = voice
        utterance.onend = () => { setIsSpeaking(false); if (!ttsCancelRef.current) startRecording() }
        utterance.onerror = () => { setIsSpeaking(false); if (!ttsCancelRef.current) startRecording() }
        window.speechSynthesis.speak(utterance)
      })
  }, [])

  // Speak questions — gated on both micReady and started (user tapped "Tap to Begin").
  useEffect(() => {
    if (!micReady || !started) return
    if (questions.length === 0) return
    transcriptRef.current = ''
    setTranscript('')
    const q = questions[currentIndex]
    if (!q) return
    speakThenRecord(q?.voice_text || q?.question || '')
  }, [currentIndex, questions, speakThenRecord, micReady, started])

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

  // Pre-interview instructions screen
  if (introPhase !== 'started') {
    const numQuestions = questions.length || '–'
    const minutes = Math.round((state?.timeLimit || 45))
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 max-w-md w-full p-8 flex flex-col gap-6">
          <div>
            <p className="text-blue-600 text-sm font-medium mb-1">AI Screening Interview</p>
            <h1 className="text-2xl font-semibold text-slate-800">Before you begin</h1>
          </div>

          <ul className="flex flex-col gap-4 text-slate-600 text-sm">
            <li className="flex gap-3">
              <span className="text-2xl leading-none">🕐</span>
              <span><strong className="text-slate-800">{minutes} minutes total.</strong> A 2-minute wrap-up is given when time runs out.</span>
            </li>
            <li className="flex gap-3">
              <span className="text-2xl leading-none">💬</span>
              <span><strong className="text-slate-800">{numQuestions} questions.</strong> Each question is read aloud. Answer by speaking — your response is transcribed automatically.</span>
            </li>
            <li className="flex gap-3">
              <span className="text-2xl leading-none">⏭</span>
              <span>Tap <strong className="text-slate-800">Next</strong> when you're done with an answer, or <strong className="text-slate-800">Skip</strong> to move on. You can replay a question at any time.</span>
            </li>
            <li className="flex gap-3">
              <span className="text-2xl leading-none">🎙</span>
              <span>Find a <strong className="text-slate-800">quiet place</strong> and speak clearly. The interview will ask for microphone access.</span>
            </li>
          </ul>

          {introPhase === 'intro' && (
            <button
              onClick={handleGrantMic}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-4 rounded-xl text-base shadow-sm active:scale-95 transition-transform"
            >
              Allow Microphone & Continue
            </button>
          )}

          {introPhase === 'granting' && (
            <button disabled className="bg-blue-400 text-white font-semibold px-6 py-4 rounded-xl text-base opacity-70 cursor-wait">
              Requesting access…
            </button>
          )}

          {introPhase === 'ready' && (
            <button
              onClick={handleStart}
              className="bg-green-600 hover:bg-green-700 text-white font-semibold px-6 py-4 rounded-xl text-base shadow-sm active:scale-95 transition-transform"
            >
              {prefetchedAudioRef.current ? 'Start Interview →' : 'Start Interview →'}
            </button>
          )}
        </div>
      </div>
    )
  }

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
    <div className="min-h-screen bg-slate-50 flex flex-col p-4 sm:p-6 max-w-3xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-4 sm:mb-6">
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
          <span className={`font-mono text-xl sm:text-2xl font-bold ${timerColor}`}>{formatTime(timeLeft)}</span>
        </div>
      </div>

      {/* Progress bar */}
      <div className="w-full h-1.5 bg-slate-200 rounded-full mb-5 sm:mb-8">
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
        <p className="text-base sm:text-lg font-medium text-slate-800 leading-relaxed">{q.question}</p>
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
      <div className="flex gap-2 sm:gap-3 mt-2">
        <button onClick={nextQuestion} className="btn btn-primary flex-1 text-sm sm:text-base py-3">
          {currentIndex + 1 >= questions.length ? 'Finish' : 'Next →'}
        </button>
        <button onClick={skip} className="btn btn-secondary px-4 sm:px-5 text-sm py-3">
          Skip
        </button>
        <button onClick={finish} className="btn btn-danger px-4 sm:px-5 text-sm py-3">
          End
        </button>
      </div>
    </div>
  )
}
