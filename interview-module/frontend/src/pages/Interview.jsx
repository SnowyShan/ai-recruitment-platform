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
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [timeLeft, setTimeLeft] = useState((state?.timeLimit || 45) * 60)
  const [finishing, setFinishing] = useState(false)
  const [isWrapUp, setIsWrapUp] = useState(false)
  const isWrapUpRef = useRef(false)

  const [searchParams] = useSearchParams()
  const [tokenError, setTokenError] = useState(null)
  const [tokenChecked, setTokenChecked] = useState(false)
  const tokenRef = useRef(searchParams.get('token'))

  const timerRef = useRef(null)
  const finishRef = useRef(null)
  const currentIndexRef = useRef(0)
  const questionsRef = useRef(questions)
  const finishedRef = useRef(false)

  // Guard: track which question index we've already initiated speaking for.
  const spokenIndexRef = useRef(-1)

  // MediaRecorder + Whisper — used on all platforms
  const micStreamRef = useRef(null)       // persistent mic stream, acquired once on grant
  const mediaRecorderRef = useRef(null)
  const audioChunksRef = useRef([])
  const audioMimeTypeRef = useRef('audio/webm')
  const transcriptsRef = useRef({})       // keyed by question index, populated after each Whisper call

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
  // Map of question index → pre-fetched blob URL (all questions fetched in parallel during 'ready' phase)
  const prefetchedAudioMapRef = useRef({})

  const micReady  = introPhase === 'started'
  const started   = introPhase === 'started'

  const handleGrantMic = async () => {
    setIntroPhase('granting')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      micStreamRef.current = stream  // keep alive for entire interview — no repeated permission prompts
    } catch (_) {}  // denied gracefully — getUserMedia will re-prompt on first recording
    setIntroPhase('ready')
  }

  // Release mic stream on unmount
  useEffect(() => {
    return () => {
      micStreamRef.current?.getTracks().forEach(t => t.stop())
      micStreamRef.current = null
    }
  }, [])

  // Pre-fetch audio for ALL questions while user reads instructions.
  // Questions with audio_url (pre-generated on server) are fetched from there;
  // questions without audio_url fall back to on-demand TTS.
  // All fetches fire in parallel — whichever questions are ready first get cached first.
  useEffect(() => {
    if (introPhase !== 'ready' || questions.length === 0) return
    let cancelled = false

    const prefetchOne = async (idx) => {
      const q = questions[idx]
      if (!q) return
      try {
        let blobUrl
        if (q.audio_url) {
          // Pre-generated audio from question bank or session setup
          const res = await axios.get(`${API}${q.audio_url}`, { responseType: 'blob' })
          blobUrl = URL.createObjectURL(res.data)
        } else {
          // Fall back to on-demand TTS
          const text = q.voice_text || q.question || ''
          if (!text) return
          const res = await axios.post(`${API}/api/interview/tts`, { text }, { responseType: 'blob' })
          blobUrl = URL.createObjectURL(res.data)
        }
        if (!cancelled) prefetchedAudioMapRef.current[idx] = blobUrl
      } catch (_) {} // non-fatal — speakThenRecord falls back to TTS
    }

    // Fire all in parallel
    questions.forEach((_, idx) => prefetchOne(idx))

    return () => {
      // Only cancel in-flight fetches — do NOT revoke blob URLs here.
      // Blobs are revoked individually in playBlob's onended/onerror/catch handlers,
      // and any remaining are cleaned up on component unmount below.
      cancelled = true
    }
  }, [introPhase, questions])

  // Revoke any un-played cached blobs when the component unmounts
  useEffect(() => {
    return () => {
      Object.values(prefetchedAudioMapRef.current).forEach(url => {
        try { URL.revokeObjectURL(url) } catch (_) {}
      })
    }
  }, [])

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
      // Clear handlers BEFORE touching src — prevents stale onended from firing
      audioRef.current.onended = null
      audioRef.current.onerror = null
      audioRef.current.pause()
      audioRef.current.src = ''
      try { audioRef.current.load() } catch (_) {}  // force-abort iOS audio pipeline
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

    console.log('[speakThenRecord] q:', currentIndexRef.current,
      '| gen:', gen,
      '| cached:', !!prefetchedAudioMapRef.current[currentIndexRef.current],
      '| audio_url:', questionsRef.current[currentIndexRef.current]?.audio_url)

    // Use pre-fetched audio if available (Q0 is pre-fetched during instructions screen)
    const playBlob = (blobUrl) => {
      if (ttsGenRef.current !== gen || finishedRef.current) { URL.revokeObjectURL(blobUrl); return }
      const audio = new Audio(blobUrl)
      audioRef.current = audio
      const done = (evt) => {
        console.log('[TTS] done fired via', evt?.type, '| gen match:', ttsGenRef.current === gen)
        audio.onended = null  // one-shot: prevent double-fire if both onended + onerror fire
        audio.onerror = null
        URL.revokeObjectURL(blobUrl)
        audioRef.current = null
        setIsSpeaking(false)
        // Small delay: gives mobile Chrome time to release audio resources
        // before switching to mic input. Fixes "mic doesn't start on Q2+" on mobile.
        if (ttsGenRef.current === gen && !finishedRef.current) {
          setTimeout(() => {
            if (ttsGenRef.current === gen && !finishedRef.current) startRecording()
          }, 300)
        }
      }
      audio.onended = done
      audio.onerror = done
      audio.play()
        .then(() => { if (ttsGenRef.current === gen) setIsSpeaking(true) })
        .catch(() => {
          URL.revokeObjectURL(blobUrl)
          audioRef.current = null
          setIsSpeaking(false)
          if (ttsGenRef.current === gen && !finishedRef.current) startRecording()
        })
    }

    // Check pre-fetched map first (keyed by question index)
    const cachedUrl = prefetchedAudioMapRef.current[currentIndexRef.current]
    if (cachedUrl) {
      delete prefetchedAudioMapRef.current[currentIndexRef.current]
      playBlob(cachedUrl)
      return
    }

    // Check if current question has a server-side audio_url (play directly)
    const currentQ = questionsRef.current[currentIndexRef.current]
    if (currentQ?.audio_url) {
      axios.get(`${API}${currentQ.audio_url}`, { responseType: 'blob' })
        .then(res => {
          if (ttsGenRef.current !== gen) return
          playBlob(URL.createObjectURL(res.data))
        })
        .catch(() => {
          // Fall through to on-demand TTS
          fetchViaTTS()
        })
      return
    }

    fetchViaTTS()
    // eslint-disable-next-line no-inner-declarations
    function fetchViaTTS() {
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
        const synthDone = () => {
          setIsSpeaking(false)
          if (ttsGenRef.current === gen && !ttsCancelRef.current && !finishedRef.current) startRecording()
        }
        utterance.onend = synthDone
        utterance.onerror = synthDone
        window.speechSynthesis.speak(utterance)
      })
    } // end fetchViaTTS
  }, [])

  // Speak questions — gated on both micReady and started (user tapped "Tap to Begin").
  useEffect(() => {
    if (!micReady || !started) return
    if (questions.length === 0) return
    const q = questions[currentIndex]
    if (!q) return
    // Guard: only speak each question index once. Prevents re-triggering when
    // `questions` state updates mid-interview (API fetch completing after start).
    if (spokenIndexRef.current === currentIndex) return
    spokenIndexRef.current = currentIndex
    speakThenRecord(q?.voice_text || q?.question || '')
  }, [currentIndex, questions, speakThenRecord, micReady, started])

  const replayQuestion = async () => {
    const q = questionsRef.current[currentIndexRef.current]
    if (!q) return
    cancelSpeech()
    await stopRecording()        // discard recording — user is starting over
    audioChunksRef.current = []  // ensure clean slate
    spokenIndexRef.current = -1  // allow speak effect to re-trigger
    speakThenRecord(q.voice_text || q.question)
  }

  const toggleTTS = () => {
    if (isSpeaking) cancelSpeech()
    setTtsEnabled(v => !v)
  }

  // ── Recording (MediaRecorder + Whisper on all platforms) ─────────────────

  const startRecording = async () => {
    if (finishedRef.current) return
    try {
      // Reuse persistent stream if alive; re-acquire if not
      let stream = micStreamRef.current
      if (!stream || stream.getTracks().some(t => t.readyState === 'ended')) {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        micStreamRef.current = stream
      }
      const mimeType = MediaRecorder.isTypeSupported('audio/mp4')  ? 'audio/mp4'
                     : MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm'
                     : ''
      audioMimeTypeRef.current = mimeType || 'audio/webm'
      audioChunksRef.current = []
      const mr = new MediaRecorder(stream, mimeType ? { mimeType } : {})
      mr.ondataavailable = e => { if (e.data?.size > 0) audioChunksRef.current.push(e.data) }
      mr.start(1000)
      mediaRecorderRef.current = mr
      setIsRecording(true)
    } catch (err) {
      console.log('[Recording] failed to start:', err.message)
      setIsRecording(false)
    }
  }

  // Stops current recording. Returns Promise<Blob|null>.
  const stopRecording = () => new Promise(resolve => {
    const mr = mediaRecorderRef.current
    if (!mr || mr.state === 'inactive') {
      setIsRecording(false)
      resolve(null)
      return
    }
    mr.onstop = () => {
      // Note: we do NOT stop stream tracks here — micStreamRef stays alive for next question
      mediaRecorderRef.current = null
      setIsRecording(false)
      const chunks = audioChunksRef.current
      audioChunksRef.current = []
      resolve(chunks.length ? new Blob(chunks, { type: audioMimeTypeRef.current }) : null)
    }
    try { mr.stop() } catch (_) { setIsRecording(false); resolve(null) }
  })

  // Send blob to Whisper, return transcript text. Retries once on empty.
  const transcribeBlob = async (blob) => {
    if (!blob) return ''
    const ext = audioMimeTypeRef.current.includes('mp4') ? 'm4a' : 'webm'
    const doRequest = async () => {
      const fd = new FormData()
      fd.append('file', blob, `audio.${ext}`)
      const res = await axios.post(`${API}/api/interview/transcribe`, fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return res.data.text || ''
    }
    try {
      setIsTranscribing(true)
      let text = await doRequest()
      if (!text.trim()) {
        await new Promise(r => setTimeout(r, 800))
        text = await doRequest()
      }
      return text
    } catch (err) {
      console.log('[Whisper] transcription error:', err.message)
      return ''
    } finally {
      setIsTranscribing(false)
    }
  }

  const advance = () => {
    const idx = currentIndexRef.current
    const qs = questionsRef.current
    if (idx + 1 >= qs.length) finishRef.current?.()
    else setCurrentIndex(idx + 1)
  }

  const nextQuestion = async () => {
    cancelSpeech()
    const idx = currentIndexRef.current
    const blob = await stopRecording()
    const text = await transcribeBlob(blob)
    transcriptsRef.current[idx] = text
    advance()
  }

  const skip = async () => {
    cancelSpeech()
    const idx = currentIndexRef.current
    await stopRecording()  // discard audio
    transcriptsRef.current[idx] = '[SKIPPED]'
    advance()
  }

  const finish = useCallback(async () => {
    finishedRef.current = true
    clearInterval(timerRef.current)
    cancelSpeech()
    const idx = currentIndexRef.current

    // Only transcribe if this question hasn't already been handled.
    // nextQuestion() on the final question transcribes + stores BEFORE calling
    // advance() → finish(), so we must not overwrite it with a second empty call.
    if (transcriptsRef.current[idx] === undefined) {
      const blob = await stopRecording()
      const text = await transcribeBlob(blob)
      transcriptsRef.current[idx] = text
    } else {
      // Ensure any lingering MediaRecorder is cleaned up (safety)
      await stopRecording()
    }

    // Build full transcript — every question, in order.
    // Unvisited questions (user ended early) → '(no answer)'
    // Skipped questions → '[SKIPPED]'
    const qs = questionsRef.current
    let fullTranscript = ''
    qs.forEach((q, i) => {
      const ans = transcriptsRef.current[i]
      fullTranscript += `[Q${i + 1}: ${q.question}]\n${ans ?? '(no answer)'}\n\n`
    })

    setFinishing(true)
    try {
      await axios.post(`${API}/api/interview/session/${sessionId}/complete`, {
        full_transcript: fullTranscript,
        questions: qs,
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
              <span><strong className="text-slate-800">{numQuestions} questions.</strong> Each question is read aloud. Speak your answer — tap <strong className="text-slate-800">Next</strong> when done and your response is saved automatically.</span>
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

          <p className="text-xs text-slate-400 text-center">
            Best experienced on Chrome, Edge, or Safari on macOS.
          </p>

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
              Tap to Begin →
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
          <p className="text-xs text-slate-400 mt-3 italic">Recording starts automatically when the question finishes…</p>
        )}
      </div>

      {/* Transcribing status — shown briefly between questions while Whisper processes */}
      {isTranscribing && (
        <div className="card p-4 mb-4 flex items-center gap-3 text-slate-500 text-sm">
          <span className="inline-block w-2 h-2 rounded-full bg-indigo-400 animate-pulse flex-shrink-0" />
          Processing your answer…
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-2 sm:gap-3 mt-2">
        <button onClick={nextQuestion} disabled={isTranscribing || isSpeaking}
          className="btn btn-primary flex-1 text-sm sm:text-base py-3 disabled:opacity-50">
          {currentIndex + 1 >= questions.length ? 'Finish' : 'Next →'}
        </button>
        <button onClick={skip} disabled={isTranscribing || isSpeaking}
          className="btn btn-secondary px-4 sm:px-5 text-sm py-3 disabled:opacity-50">
          Skip
        </button>
        <button onClick={finish} disabled={isTranscribing}
          className="btn btn-danger px-4 sm:px-5 text-sm py-3 disabled:opacity-50">
          End
        </button>
      </div>
    </div>
  )
}
