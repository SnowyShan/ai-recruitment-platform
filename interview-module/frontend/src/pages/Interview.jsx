import React, { useState, useEffect, useRef, useCallback, lazy, Suspense } from 'react'
import { useParams, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import axios from 'axios'

const ExcalidrawWrapper = lazy(() =>
  import('@excalidraw/excalidraw')
    .then(mod => ({ default: mod.Excalidraw }))
    .catch(() => ({ default: () => <div className="flex items-center justify-center h-full text-slate-400 text-sm">Canvas unavailable on this device</div> }))
)

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

  // Code editor state
  const [verifyCoding, setVerifyCoding] = useState(state?.verify_coding_ability || false)
  const [codeAnswers, setCodeAnswers] = useState({})  // questionIndex → code string
  const codeAnswersRef = useRef({})
  const [activeTab, setActiveTab] = useState({})       // questionIndex → 'voice' | 'code' | 'draw'

  // Drawing (Excalidraw) state
  const drawElementsRef = useRef({})   // questionIndex → elements array
  const drawFilesRef = useRef({})      // questionIndex → files object
  const drawAppStateRef = useRef({})   // questionIndex → appState snapshot
  const excalidrawAPIRef = useRef(null)

  // Core competency probe state
  const [probePhase, setProbePhase] = useState(null)
  // null = not in probe mode
  // { probes: [...], probeIndex: 0 } = probing active
  const probePhaseRef = useRef(null)
  const probeTranscriptsRef = useRef({})  // questionIndex -> [probeAnswer0, probeAnswer1, ...]

  // Video interview state
  const [videoInterviewEnabled, setVideoInterviewEnabled] = useState(false)
  const videoRef = useRef(null)

  // ── Proctoring state ──────────────────────────────────────────────────────
  const proctoringEventsRef = useRef([])       // [{type, ts, ts_label, detail}]
  const proctoringSnapshotsRef = useRef([])    // [dataURL, ...] JPEG, max 20
  const identityPhotoRef = useRef(null)        // dataURL captured at start
  const camStreamRef = useRef(null)            // webcam MediaStream
  const camVideoRef = useRef(null)             // hidden <video> element for face-api
  const snapshotCanvasRef = useRef(null)       // hidden <canvas> for JPEG capture
  const faceApiLoadedRef = useRef(false)
  const previewVideoRef = useRef(null)       // camera preview on identity photo screen
  const identityDescriptorRef = useRef(null)    // Float32Array from identity photo
  const lastMismatchLoggedRef = useRef(0)        // timestamp of last face_mismatch log
  const snapshotTimerRef = useRef(null)
  const faceCheckTimerRef = useRef(null)
  const [camReady, setCamReady] = useState(false)
  const [identityPhotoCaptured, setIdentityPhotoCaptured] = useState(false)
  const [proctoringError, setProctoringError] = useState(null)

  // Face detection stats
  const faceDetectionRunsRef = useRef(0)
  const faceDetectedCountRef = useRef(0)
  const faceAbsentCountRef = useRef(0)
  const multipleFacesCountRef = useRef(0)
  const faceMismatchCountRef = useRef(0)
  const faceCheckRunsRef = useRef(0)
  const faceMatchCountRef = useRef(0)

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
  useEffect(() => { codeAnswersRef.current = codeAnswers }, [codeAnswers])

  useEffect(() => {
    if (!state?.questions) {
      axios.get(`${API}/api/interview/session/${sessionId}`).then(({ data }) => {
        setQuestions(data.questions)
        setTimeLeft(data.time_limit * 60)
        if (data.verify_coding_ability) setVerifyCoding(true)
        if (data.video_interview_enabled) setVideoInterviewEnabled(true)
      })
    }
  }, [sessionId])

  // Pre-interview intro phase:
  //   'intro'    → instructions screen, mic not yet requested
  //   'granting' → getUserMedia in flight, spinner on button
  //   'ready'    → mic granted/denied, "Start Interview" button shown, Q0 audio pre-fetching
  //   'started'  → interview running
  const [introPhase, setIntroPhase] = useState('intro')
  const [startingInterview, setStartingInterview] = useState(false)
  const micReady  = introPhase === 'started'
  const started   = introPhase === 'started'

  // Map of question index → pre-fetched blob URL (all questions fetched in parallel during 'ready' phase)
  const prefetchedAudioMapRef = useRef({})

  // ── Proctoring helpers ────────────────────────────────────────────────────

  const _logProctoringEvent = useCallback((type, detail = '') => {
    const now = new Date()
    const ts_label = now.toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
    proctoringEventsRef.current.push({ type, ts: now.toISOString(), ts_label, detail })
  }, [])

  const _captureSnapshot = useCallback(() => {
    const video = camVideoRef.current
    const canvas = snapshotCanvasRef.current
    if (!video || !canvas || video.readyState < 2) return
    try {
      canvas.width = 320
      canvas.height = 240
      const ctx = canvas.getContext('2d')
      ctx.drawImage(video, 0, 0, 320, 240)
      const dataUrl = canvas.toDataURL('image/jpeg', 0.6)
      if (proctoringSnapshotsRef.current.length < 20) {
        proctoringSnapshotsRef.current.push(dataUrl)
      }
    } catch (_) {}
  }, [_logProctoringEvent])

  // Start face detection interval every 5s (models already loaded in handleGrantMic)
  const _startFaceDetection = useCallback(async () => {
    if (!faceApiLoadedRef.current || !window.faceapi) return
    const faceapi = window.faceapi
    try {
      // Give the video a moment to reach readyState >= 2 before starting checks
      await new Promise(r => setTimeout(r, 500))
      faceCheckTimerRef.current = setInterval(async () => {
        const video = camVideoRef.current
        if (!video || video.readyState < 2 || finishedRef.current) return
        try {
          faceDetectionRunsRef.current++
          const detections = await faceapi.detectAllFaces(video, new faceapi.TinyFaceDetectorOptions())
          const count = detections.length
          if (count === 0) {
            faceAbsentCountRef.current++
            _logProctoringEvent('face_absent', 'No face detected in camera frame')
          } else if (count > 1) {
            multipleFacesCountRef.current++
            _logProctoringEvent('multiple_faces', `${count} faces detected`)
          } else {
            faceDetectedCountRef.current++
          }
          // Identity matching on live video — only when exactly 1 face and descriptor available
          if (count === 1 && identityDescriptorRef.current && faceapi.nets.faceRecognitionNet?.params) {
            faceCheckRunsRef.current++
            const det = await faceapi.detectSingleFace(video, new faceapi.TinyFaceDetectorOptions()).withFaceLandmarks().withFaceDescriptor()
            if (det) {
              const distance = faceapi.euclideanDistance(identityDescriptorRef.current, det.descriptor)
              if (distance <= 0.6) {
                faceMatchCountRef.current++
              } else {
                faceMismatchCountRef.current++
                const now = Date.now()
                if (now - lastMismatchLoggedRef.current > 30000) {
                  lastMismatchLoggedRef.current = now
                  _logProctoringEvent('face_mismatch', `Identity mismatch in live feed (distance: ${distance.toFixed(2)})`)
                }
              }
            }
          }
        } catch (_) {}
      }, 5000)
    } catch (err) {
      console.warn('[Proctoring] face-api failed to load:', err.message)
    }
  }, [_logProctoringEvent])

  const handleGrantMic = async () => {
    setIntroPhase('granting')
    try {
      // Request mic + camera together
      const audioStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      micStreamRef.current = audioStream

      // Camera for proctoring — mandatory
      try {
        const camStream = await navigator.mediaDevices.getUserMedia({ video: { width: 320, height: 240, facingMode: 'user' } })
        camStreamRef.current = camStream
        setCamReady(true)
      } catch (_) {
        _logProctoringEvent('camera_denied', 'Candidate denied camera access')
        setProctoringError("Camera access is required for this interview. Please allow camera access and reload the page.")
        setIntroPhase('ready')
        return
      }

      // Load face-api.js + models inline — mandatory for proctoring
      try {
        if (!window.faceapi) {
          await new Promise((resolve, reject) => {
            const script = document.createElement('script')
            script.src = 'https://cdn.jsdelivr.net/npm/face-api.js@0.22.2/dist/face-api.min.js'
            script.onload = resolve
            script.onerror = reject
            document.head.appendChild(script)
          })
        }
        const faceapi = window.faceapi
        const MODEL_URL = 'https://cdn.jsdelivr.net/npm/@vladmandic/face-api@1.7.13/model'
        await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL)
        await Promise.all([
          faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL),
          faceapi.nets.faceRecognitionNet.loadFromUri(MODEL_URL),
        ])
        faceApiLoadedRef.current = true
      } catch (_) {
        setProctoringError("Face verification could not be initialized. Please use a supported browser (Chrome, Edge, or Safari) and ensure you have an active internet connection.")
        setIntroPhase('ready')
        return
      }
    } catch (_) {}
    setIntroPhase('ready')
  }

  // Start face detection AFTER interview DOM is committed (introPhase === 'started')
  // This ensures camVideoRef.current points to the interview's video element, not the intro's
  useEffect(() => {
    if (introPhase !== 'started') return
    // Re-wire camera stream to the newly mounted video element
    if (camVideoRef.current && camStreamRef.current) {
      camVideoRef.current.srcObject = camStreamRef.current
      camVideoRef.current.play().catch(() => {})
    }
    _startFaceDetection()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [introPhase])

  // Wire camera stream to hidden video element once camReady
  useEffect(() => {
    if (!camReady || !camStreamRef.current) return
    // Use a small delay to let the hidden video element mount
    const t = setTimeout(() => {
      if (camVideoRef.current && camStreamRef.current) {
        camVideoRef.current.srcObject = camStreamRef.current
        camVideoRef.current.play().catch(() => {})
      }
    }, 200)
    return () => clearTimeout(t)
  }, [camReady])

  // Extract identity descriptor once identity photo is captured
  useEffect(() => {
    if (!identityPhotoCaptured || !identityPhotoRef.current) return
    if (!window.faceapi?.nets?.faceRecognitionNet?.params) return // recognition model not loaded
    const faceapi = window.faceapi
    const img = new Image()
    img.onload = async () => {
      try {
        const c = document.createElement('canvas')
        c.width = img.width; c.height = img.height
        c.getContext('2d').drawImage(img, 0, 0)
        const det = await faceapi.detectSingleFace(c, new faceapi.TinyFaceDetectorOptions()).withFaceLandmarks().withFaceDescriptor()
        if (det) {
          identityDescriptorRef.current = det.descriptor
        } else {
          console.warn('[Proctoring] No face detected in identity photo — matching disabled')
        }
      } catch (e) {
        console.warn('[Proctoring] Identity descriptor extraction failed:', e.message)
      }
    }
    img.src = identityPhotoRef.current
  }, [identityPhotoCaptured])

  // Release mic + camera streams on unmount, clear timers
  useEffect(() => {
    return () => {
      micStreamRef.current?.getTracks().forEach(t => t.stop())
      micStreamRef.current = null
      camStreamRef.current?.getTracks().forEach(t => t.stop())
      camStreamRef.current = null
      clearInterval(snapshotTimerRef.current)
      clearInterval(faceCheckTimerRef.current)
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
  const handleStart = () => {
    setStartingInterview(true)
    // Let React render the spinner first, then do the heavy work
    setTimeout(() => {
    setIntroPhase('started')

    // ── Proctoring: start when interview begins ────────────────────────────
    // 1. Request fullscreen
    try {
      const el = document.documentElement
      if (el.requestFullscreen) el.requestFullscreen()
      else if (el.webkitRequestFullscreen) el.webkitRequestFullscreen()
    } catch (_) {}

    // 2. Listen for fullscreen exit
    const onFullscreenChange = () => {
      if (!document.fullscreenElement && !document.webkitFullscreenElement) {
        _logProctoringEvent('fullscreen_exit', 'Candidate exited fullscreen')
      }
    }
    document.addEventListener('fullscreenchange', onFullscreenChange)
    document.addEventListener('webkitfullscreenchange', onFullscreenChange)

    // 3. Tab / window blur detection
    const onVisibilityChange = () => {
      if (document.visibilityState === 'hidden') {
        _logProctoringEvent('tab_hidden', 'Interview tab hidden / switched away')
      }
    }
    const onBlur = () => _logProctoringEvent('window_blur', 'Browser window lost focus')
    document.addEventListener('visibilitychange', onVisibilityChange)
    window.addEventListener('blur', onBlur)

    // 4. Start periodic snapshot (every 2 min)
    snapshotTimerRef.current = setInterval(() => {
      if (!finishedRef.current) _captureSnapshot()
    }, 2 * 60 * 1000)

    }, 50) // defer heavy work so spinner renders first
  }

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
  // When video interview is enabled AND the question has a video, the D-ID video
  // provides the audio — skip TTS and drive isSpeaking from video events instead.
  useEffect(() => {
    if (!micReady || !started) return
    if (questions.length === 0) return
    const q = questions[currentIndex]
    if (!q) return
    if (spokenIndexRef.current === currentIndex) return
    spokenIndexRef.current = currentIndex

    if (videoInterviewEnabled && q?.video_url) {
      // D-ID video has audio baked in — play it, skip TTS entirely
      // Defer one tick so the video element is guaranteed mounted in the DOM
      const playVideo = () => {
        const vid = videoRef.current
        if (!vid) {
          // Still not mounted — fall back to TTS
          speakThenRecord(q?.voice_text || q?.question || '')
          return
        }
        vid.src = `${API}${q.video_url}`
        vid.onended = () => {
          setIsSpeaking(false)
          if (!finishedRef.current) startRecording()
        }
        vid.onerror = () => {
          setIsSpeaking(false)
          speakThenRecord(q?.voice_text || q?.question || '')
        }
        vid.play()
          .then(() => setIsSpeaking(true))
          .catch(() => {
            setIsSpeaking(false)
            speakThenRecord(q?.voice_text || q?.question || '')
          })
      }
      // Defer one tick to ensure React has mounted the video element
      setTimeout(playVideo, 0)
    } else {
      speakThenRecord(q?.voice_text || q?.question || '')
    }
  }, [currentIndex, questions, speakThenRecord, micReady, started, videoInterviewEnabled])

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

  // ── Core competency probe helpers ──────────────────────────────────────────

  const speakProbeQuestion = useCallback((probe, _questionIndex) => {
    cancelSpeech()
    // Never switch tabs for probe questions — candidate always answers verbally.
    // Code snippets are rendered inline in the probe banner, not in the code tab.
    if (probe.audio_url) {
      // Play pre-generated audio (same pattern as regular questions)
      ttsGenRef.current += 1
      const gen = ttsGenRef.current
      axios.get(`${API}${probe.audio_url}`, { responseType: 'blob' })
        .then(res => {
          if (ttsGenRef.current !== gen || finishedRef.current) return
          const blobUrl = URL.createObjectURL(res.data)
          const audio = new Audio(blobUrl)
          audioRef.current = audio
          const done = () => {
            audio.onended = null
            audio.onerror = null
            URL.revokeObjectURL(blobUrl)
            audioRef.current = null
            setIsSpeaking(false)
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
        })
        .catch(() => {
          // Fallback to on-demand TTS if pre-generated audio fetch fails
          speakThenRecord(probe.voice_text || probe.question)
        })
    } else {
      // No pre-generated audio — fall back to on-demand TTS
      speakThenRecord(probe.voice_text || probe.question)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [speakThenRecord])

  const nextProbe = useCallback(async () => {
    cancelSpeech()
    const idx = currentIndexRef.current
    const blob = await stopRecording()
    const text = await transcribeBlob(blob)

    const ps = probePhaseRef.current
    if (!ps) return

    if (!probeTranscriptsRef.current[idx]) probeTranscriptsRef.current[idx] = []
    probeTranscriptsRef.current[idx].push(text)

    const nextProbeIdx = ps.probeIndex + 1

    if (nextProbeIdx >= ps.probes.length) {
      probePhaseRef.current = null
      setProbePhase(null)
      advance()
    } else {
      const updatedState = { ...ps, probeIndex: nextProbeIdx }
      probePhaseRef.current = updatedState
      setProbePhase({ ...updatedState })
      speakProbeQuestion(ps.probes[nextProbeIdx], idx)
    }
  }, [stopRecording, transcribeBlob, advance, speakProbeQuestion])

  const runCoreCompetencyProbes = useCallback(async (mainAnswerText, questionIndex) => {
    const q = questionsRef.current[questionIndex]
    if (!q?.is_core_competency || !q?.probe_questions?.length) {
      advance()
      return
    }

    // Quick assess
    let needsProbing = true
    try {
      const res = await axios.post(`${API}/api/interview/probe-assess`, {
        question: q.question,
        answer: mainAnswerText,
        job_description: '',
        seniority_bar: 'senior',
      })
      needsProbing = res.data.needs_probing
    } catch (_) {
      // default to probing on error
    }

    if (!needsProbing) {
      advance()
      return
    }

    // Enter probe mode
    const probeState = { probes: q.probe_questions, probeIndex: 0 }
    probePhaseRef.current = probeState
    setProbePhase({ ...probeState })

    // Speak first probe
    speakProbeQuestion(q.probe_questions[0], questionIndex)
  }, [speakProbeQuestion, advance])

  const nextQuestion = async () => {
    cancelSpeech()
    const idx = currentIndexRef.current
    const blob = await stopRecording()
    const text = await transcribeBlob(blob)
    transcriptsRef.current[idx] = text

    // If already in probe mode, delegate
    if (probePhaseRef.current) {
      await nextProbe()
      return
    }

    // Core competency fork
    const q = questionsRef.current[idx]
    if (q?.is_core_competency && q?.probe_questions?.length > 0) {
      await runCoreCompetencyProbes(text, idx)
      return
    }

    // Regular path — unchanged
    advance()
  }

  const skip = async () => {
    cancelSpeech()
    const idx = currentIndexRef.current
    await stopRecording()  // discard audio

    if (probePhaseRef.current) {
      // Skipping a probe — record [SKIPPED] for this probe answer, then advance
      // through probe state exactly as nextProbe would (without transcribing).
      const ps = probePhaseRef.current
      if (!probeTranscriptsRef.current[idx]) probeTranscriptsRef.current[idx] = []
      probeTranscriptsRef.current[idx].push('[SKIPPED]')

      const nextProbeIdx = ps.probeIndex + 1
      if (nextProbeIdx >= ps.probes.length) {
        // All probes done — exit probe mode and advance to next main question
        probePhaseRef.current = null
        setProbePhase(null)
        advance()
      } else {
        // Move to next probe
        const updatedState = { ...ps, probeIndex: nextProbeIdx }
        probePhaseRef.current = updatedState
        setProbePhase({ ...updatedState })
        speakProbeQuestion(ps.probes[nextProbeIdx], idx)
      }
    } else {
      // Regular skip — unchanged behaviour
      transcriptsRef.current[idx] = '[SKIPPED]'
      advance()
    }
  }

  const finish = useCallback(async () => {
    finishedRef.current = true
    clearInterval(timerRef.current)
    cancelSpeech()
    // Clear probe state — End was tapped mid-probe; we exit cleanly
    probePhaseRef.current = null
    setProbePhase(null)
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
      fullTranscript += `[Q${i + 1}: ${q.question}]${q.is_core_competency ? ' [CORE_COMPETENCY]' : ''}\n${ans ?? '(no answer)'}\n\n`

      const probeAnswers = probeTranscriptsRef.current[i]
      if (probeAnswers && probeAnswers.length > 0 && q.probe_questions) {
        q.probe_questions.forEach((probe, pi) => {
          const probeAns = probeAnswers[pi] ?? '(no answer)'
          fullTranscript += `[PROBE_${pi + 1}: ${probe.question}]\n${probeAns}\n\n`
        })
      }
    })

    setFinishing(true)

    // Export drawings to base64 PNGs
    let drawAnswers = null
    try {
      const { exportToBlob } = await import('@excalidraw/excalidraw')
      const entries = []
      for (let i = 0; i < qs.length; i++) {
        const els = drawElementsRef.current[i]
        const nonDeleted = els?.filter(e => !e.isDeleted)
        if (nonDeleted && nonDeleted.length > 0) {
          const blob = await exportToBlob({
            elements: nonDeleted,
            appState: drawAppStateRef.current[i] || {},
            files: drawFilesRef.current[i] || null,
            mimeType: 'image/png',
          })
          const buf = await blob.arrayBuffer()
          const bytes = new Uint8Array(buf)
          let binary = ''
          for (let j = 0; j < bytes.length; j++) binary += String.fromCharCode(bytes[j])
          const b64 = btoa(binary)
          entries.push(b64)
        } else {
          entries.push(null)
        }
      }
      if (entries.some(e => e !== null)) drawAnswers = entries
    } catch (err) {
      console.warn('[Draw export]', err)
    }

    // Take a final snapshot before submitting
    _captureSnapshot()
    // Exit fullscreen cleanly
    try {
      if (document.fullscreenElement) document.exitFullscreen()
      else if (document.webkitFullscreenElement) document.webkitExitFullscreen()
    } catch (_) {}
    clearInterval(snapshotTimerRef.current)
    clearInterval(faceCheckTimerRef.current)

    const proctoringPayload = {
      events: proctoringEventsRef.current,
      snapshots: proctoringSnapshotsRef.current,
      identity_photo: identityPhotoRef.current,
      face_detection_stats: {
        total_runs: faceDetectionRunsRef.current,
        face_detected: faceDetectedCountRef.current,
        face_absent: faceAbsentCountRef.current,
        multiple_faces: multipleFacesCountRef.current,
        identity_check_runs: faceCheckRunsRef.current,
        identity_match: faceMatchCountRef.current,
        identity_mismatch: faceMismatchCountRef.current,
      }
    }

    try {
      await axios.post(`${API}/api/interview/session/${sessionId}/complete`, {
        full_transcript: fullTranscript,
        questions: qs,
        code_answers: Object.keys(codeAnswersRef.current).length > 0 ? codeAnswersRef.current : undefined,
        draw_answers: drawAnswers,
        proctoring_data: proctoringPayload,
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
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center gap-4">
      <div className="spinner" />
      <p className="text-sm text-slate-400">Loading interview…</p>
    </div>
  )

  // Pre-interview instructions screen
  if (introPhase !== 'started') {
    const numQuestions = questions.length || '–'
    const minutes = Math.round((state?.timeLimit || 45))
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-6">
        {/* Hidden proctoring elements — must be mounted early so refs are available when stream wires up */}
        <video ref={camVideoRef} playsInline muted style={{ display: 'none' }} />
        <canvas ref={snapshotCanvasRef} style={{ display: 'none' }} />
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
              <span>Find a <strong className="text-slate-800">quiet place</strong> and speak clearly. The interview will ask for microphone and camera access.</span>
            </li>
            <li className="flex gap-3">
              <span className="text-2xl leading-none">📷</span>
              <span>This interview is <strong className="text-slate-800">proctored.</strong> Your camera and screen activity are monitored throughout to ensure a fair process.</span>
            </li>
          </ul>

          <p className="text-xs text-slate-400 text-center">
            Best experienced on Chrome, Edge, or Safari on macOS.
          </p>

          {proctoringError && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex flex-col gap-3">
              <p className="text-sm text-red-700">{proctoringError}</p>
              <button
                onClick={() => window.location.reload()}
                className="bg-red-600 hover:bg-red-700 text-white font-semibold px-5 py-2.5 rounded-xl text-sm shadow-sm active:scale-95 transition-transform"
              >
                Reload Page
              </button>
            </div>
          )}

          {/* Identity photo capture — shown after mic+camera granted */}
          {!proctoringError && introPhase === 'ready' && camReady && !identityPhotoCaptured && (
            <div className="flex flex-col items-center gap-3">
              <p className="text-sm text-slate-600 text-center">Please look at the camera and take a quick photo to verify your identity.</p>
              <div className="relative w-48 h-36 rounded-xl overflow-hidden bg-slate-100 border border-slate-200">
                <video
                  ref={el => {
                    if (el && previewVideoRef.current !== el) {
                      previewVideoRef.current = el
                      if (camStreamRef.current && !el.srcObject) {
                        el.srcObject = camStreamRef.current
                        el.play().catch(() => {})
                      }
                    }
                  }}
                  playsInline muted
                  className="w-full h-full object-cover"
                />
              </div>
              <button
                onClick={() => {
                  // Capture identity photo from the dedicated preview video ref
                  const vidEl = previewVideoRef.current
                  const canvas = snapshotCanvasRef.current || document.createElement('canvas')
                  if (vidEl && vidEl.readyState >= 2) {
                    canvas.width = 320; canvas.height = 240
                    canvas.getContext('2d').drawImage(vidEl, 0, 0, 320, 240)
                    identityPhotoRef.current = canvas.toDataURL('image/jpeg', 0.8)
                  }
                  setIdentityPhotoCaptured(true)
                }}
                className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-5 py-2.5 rounded-xl text-sm shadow-sm active:scale-95 transition-transform"
              >
                📷 Take Photo
              </button>
            </div>
          )}

          {!proctoringError && introPhase === 'ready' && camReady && identityPhotoCaptured && (
            <div className="flex items-center gap-2 text-emerald-600 text-sm justify-center">
              <span>✓</span> Identity photo captured
            </div>
          )}

          {!proctoringError && introPhase === 'intro' && (
            <button
              onClick={handleGrantMic}
              className="bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-4 rounded-xl text-base shadow-sm active:scale-95 transition-transform"
            >
              Allow Microphone & Camera
            </button>
          )}

          {!proctoringError && introPhase === 'granting' && (
            <button disabled className="bg-blue-400 text-white font-semibold px-6 py-4 rounded-xl text-base opacity-70 cursor-wait">
              Requesting access…
            </button>
          )}

          {!proctoringError && introPhase === 'ready' && (!camReady || identityPhotoCaptured) && (
            <button
              onClick={handleStart}
              disabled={startingInterview}
              className="bg-green-600 hover:bg-green-700 text-white font-semibold px-6 py-4 rounded-xl text-base shadow-sm active:scale-95 transition-transform disabled:opacity-80 disabled:cursor-wait flex items-center justify-center gap-2"
            >
              {startingInterview
                ? <><span className="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> Starting…</>
                : 'Tap to Begin →'
              }
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
          {/* Proctoring indicator — visible to candidate as deterrence */}
          <span className="inline-flex items-center gap-1 text-[10px] text-slate-400 mt-0.5 font-medium">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse inline-block" />
            ● REC  Monitored
          </span>
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
      <div className="card p-6 mb-6 relative">
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
        {/* data-probe-active is a hidden test hook — not visible to candidates */}
        {probePhase && <span data-probe-active="true" style={{display:'none'}} />}
        <p className="text-base sm:text-lg font-medium text-slate-800 leading-relaxed">
          {probePhase
            ? (probePhase.probes[probePhase.probeIndex]?.question || '').split(/```/)[0].trim()
            : q.question
          }
        </p>
        {probePhase && probePhase.probes[probePhase.probeIndex]?.code_snippet && (
          <pre className="mt-3 p-3 bg-slate-900 text-green-300 rounded-lg text-xs overflow-x-auto font-mono whitespace-pre-wrap">
            {probePhase.probes[probePhase.probeIndex].code_snippet}
          </pre>
        )}
        {isSpeaking && (
          <p className="text-xs text-slate-400 mt-3 italic">Recording starts automatically when the question finishes…</p>
        )}

        {/* Hidden proctoring elements — camera feed + snapshot canvas */}
        <video ref={camVideoRef} playsInline muted style={{ display: 'none' }} />
        <canvas ref={snapshotCanvasRef} style={{ display: 'none' }} />

        {/* Recruiter video bubble — always mounted when video mode on so ref is available immediately */}
        {videoInterviewEnabled && q?.video_url && (
          <video
            ref={videoRef}
            playsInline
            style={{
              position: 'absolute',
              bottom: 16,
              right: 16,
              width: 80,
              height: 80,
              borderRadius: 9999,
              objectFit: 'cover',
              boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
              pointerEvents: 'none',
              display: isSpeaking ? 'block' : 'none',  // shown while D-ID video plays
            }}
          />
        )}

        {/* Tab bar — always shown */}
        <div className="flex gap-1 mt-4 border-b border-slate-200">
          <button
            onClick={() => setActiveTab(t => ({ ...t, [currentIndex]: 'voice' }))}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              (activeTab[currentIndex] || 'voice') === 'voice'
                ? 'text-indigo-600 border-b-2 border-indigo-600'
                : 'text-slate-400 hover:text-slate-600'
            }`}
          >
            🎤 Voice
          </button>
          <button
            onClick={() => setActiveTab(t => ({ ...t, [currentIndex]: 'code' }))}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab[currentIndex] === 'code'
                ? 'text-indigo-600 border-b-2 border-indigo-600'
                : 'text-slate-400 hover:text-slate-600'
            }`}
          >
            💻 Code
          </button>
          <button
            onClick={() => setActiveTab(t => ({ ...t, [currentIndex]: 'draw' }))}
            className={`px-4 py-2 text-sm font-medium transition-colors ${
              activeTab[currentIndex] === 'draw'
                ? 'text-indigo-600 border-b-2 border-indigo-600'
                : 'text-slate-400 hover:text-slate-600'
            }`}
          >
            🎨 Draw
          </button>
        </div>

        {activeTab[currentIndex] === 'code' && (
          <textarea
            value={codeAnswers[currentIndex] || ''}
            onChange={e => setCodeAnswers(prev => ({ ...prev, [currentIndex]: e.target.value }))}
            placeholder="Write your code or solution here..."
            className="w-full min-h-[300px] mt-3 p-4 rounded-lg border border-slate-200 text-sm text-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-400 resize-y"
            style={{ fontFamily: 'monospace' }}
          />
        )}

        {activeTab[currentIndex] === 'draw' && (
          <div className="mt-3 border border-slate-200 rounded-lg overflow-hidden" style={{ height: 450 }}>
            <Suspense fallback={<div className="flex items-center justify-center h-full text-slate-400 text-sm">Loading canvas…</div>}>
              <ExcalidrawWrapper
                key={`excalidraw-${currentIndex}`}
                excalidrawAPI={(api) => {
                  excalidrawAPIRef.current = api
                  window.__excalidrawAPI = api
                  // Restore saved elements for this question
                  const saved = drawElementsRef.current[currentIndex]
                  if (saved && saved.length > 0) {
                    setTimeout(() => {
                      api.updateScene({ elements: saved })
                    }, 100)
                  }
                }}
                onChange={(elements, appState, files) => {
                  drawElementsRef.current[currentIndex] = [...elements]
                  drawAppStateRef.current[currentIndex] = appState
                  if (files && Object.keys(files).length > 0) {
                    drawFilesRef.current[currentIndex] = { ...files }
                  }
                }}
                UIOptions={{ canvasActions: { saveAsImage: false, loadScene: false, export: false } }}
              />
            </Suspense>
          </div>
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
          {probePhase
            ? (probePhase.probeIndex + 1 >= probePhase.probes.length && currentIndex + 1 >= questions.length ? 'Finish' : 'Next →')
            : (currentIndex + 1 >= questions.length ? 'Finish' : 'Next →')
          }
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
