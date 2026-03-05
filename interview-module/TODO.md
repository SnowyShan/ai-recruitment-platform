# TalentBridge — Interview Module TODO
*Last updated: March 5, 2026*
*Use this file to come up to speed on the project before making changes.*

---

## Project Overview

TalentBridge is an AI-powered recruitment platform. The **interview module** is a standalone microservice that conducts AI-powered screening interviews with candidates via voice. It was built independently first, then integrated into TalentBridge.

### Architecture (Two Services)

```
TalentBridge (main)          Interview Module (standalone)
├── Frontend: localhost:5173  ├── Frontend: localhost:5174
├── Backend:  localhost:8000  └── Backend:  localhost:8001
└── DB: talentbridge.db           └── DB: interview.db
```

**How they connect:**
1. Recruiter clicks "Send Invite" in TalentBridge → `backend/app/routers/screening.py` calls interview module at `localhost:8001` to create a session
2. Interview module returns a `session_id`
3. TalentBridge generates a time-limited invite token, stores it, sends a real HTML email to the candidate via Gmail SMTP (`talentbridgerecruiterai@gmail.com`)
4. Candidate opens link: `localhost:5174/interview/{session_id}?token={invite_token}`
5. Interview module validates the token against TalentBridge (`localhost:8000/api/screenings/validate-token/{token}`)
6. Interview completes → interview module POSTs results back to TalentBridge (`localhost:8000/api/screenings/complete-from-interview`)
7. Recruiter sees report in TalentBridge JobDetail page under screening history → "View Report"

### Starting Both Services

```bash
# TalentBridge backend
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

# TalentBridge frontend
cd frontend && npm run dev

# Interview module backend
cd interview-module/backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8001

# Interview module frontend
cd interview-module/frontend && npm run dev -- --port 5174
```

---

## What Is Built ✅

### MVC — All Complete

- [x] **Task 1:** Question generation — Claude generates questions from resume + JD. Difficulty slider (1-5). Hardcoded question override supported. Behavioral questions derived from resume, technical from domain.
- [x] **Task 2:** Answer evaluation — Full transcript sent to Claude at end of session (NOT per-answer). Configurable seniority bar (junior/mid/senior/staff). Hardcoded acceptable answer override supported.
- [x] **Task 3:** Voice input — Web Speech API (Chrome only). Questions shown one at a time. Auto-recording starts on each new question. Manual "Next" button to advance.
- [x] **Task 4:** Auto-terminate — Countdown timer. When time expires, 2-minute wrap-up window given. After wrap-up, session auto-completes.
- [x] **Task 5:** Report generation — Full transcript + questions sent to Claude in one batch call at session end. Detailed report: per-question scores, overall pass/fail, strengths, weaknesses. Report POSTed back to TalentBridge and stored. Recruiter can view via "View Report" in JobDetail.

### Integration — Complete

- [x] TalentBridge screening flow creates interview sessions via API
- [x] Token-based invite system (time-limited, single-use, 48hr expiry)
- [x] Real email invites via Gmail SMTP (`talentbridgerecruiterai@gmail.com` + App Password in backend `.env`)
- [x] Token validation on interview start
- [x] Session marked `in_progress` when candidate starts
- [x] Callback to TalentBridge on completion with full report
- [x] "View Report" button in TalentBridge JobDetail screening history

### Settings — Complete
- [x] Settings page in interview module frontend
- [x] Custom evaluation prompt configurable per-deployment (stored in `interview.db`)
- [x] Prompt injected into Claude report generation call

### Test Data — Complete
- [x] iOS engineer test data (`testData/iOS/jd.txt` + `resume.txt`)
- [x] Junior data scientist test data (`testData/junior-data-science/`)
- [x] Setup page has dropdown to load test data with one click

### UI Polish — Complete (unstaged, not yet committed)
- [x] Interview page: auto-recording, wrap-up timer, clean layout
- [x] Report page: full redesign
- [x] Setup page: test data dropdown, difficulty slider, all config fields
- [x] Settings page: evaluation prompt editor
- [x] ThankYou page: shown after interview completes
- [x] TalentBridge JobDetail: loading spinner on invite button, re-invite after completion, View Report link

---

## What Is Remaining ❌

### V2 — Task 6: TTS (Read Questions Aloud)

**What:** System reads each question aloud when it appears. Candidate can disable it if they prefer to read.

---

#### Key Design Decisions

**1. Separate voice_text from screen text**
Questions have two text fields:
- `question` — shown on screen. Precise, technical, may include code formatting.
- `voice_text` — spoken aloud. Conversational phrasing, no symbols, more natural.

Example:
- Screen: `"Explain the difference between @escaping and non-escaping closures in Swift."`
- Voice: `"Can you walk me through escaping versus non-escaping closures in Swift, and give me a real example?"`

Claude generates both in the same question generation call — no extra cost.
If `voice_text` is absent, fall back to `question`.

**2. Pre-generate audio per question (not per session)**
Questions are the same across all candidates for a job. So TTS audio is generated ONCE when a question is created and reused for every candidate — not regenerated per session.

Two question types have different strategies:

| Type | When Generated | Same Across Candidates? | TTS Strategy |
|------|---------------|------------------------|--------------|
| Hardcoded (domain questions) | Question bank creation | ✅ Yes | Generate once, cache forever |
| Behavioral (resume-derived) | Session start | ❌ No — unique per resume | Generate at session creation |

**3. On/off toggle**
Candidate can disable TTS at any time. Preference stored in localStorage.
When muted: recording starts immediately (current behavior).
When unmuted: speaks question first, then recording starts.

**4. Replay button**
Candidate can replay the question audio at any time during their answer.

---

#### Three-Phase Implementation Plan

**Phase 1 — Browser speechSynthesis (DONE / IN PROGRESS)**
- Pure frontend change — no backend required
- Claude question gen prompt updated to return `voice_text` alongside `question`
- Frontend uses `window.speechSynthesis` with `voice_text`
- Flow: question appears → speak → recording starts automatically when speech ends
- Chrome keepalive fix required (speechSynthesis silently stops after ~15s without it)
- On macOS, prefer neural voices for less robotic sound
- On/off toggle + Replay button in UI
- Files changed: `Interview.jsx` (frontend) + `claude_client.py` (prompt only)
- Effort: ~3 hours

**Phase 2 — Pre-generated audio for hardcoded questions**
- Add `voice_text` (str) + `voice_audio_url` (str, nullable) to Question model in DB
- When recruiter saves/edits a question in TalentBridge:
  → Backend calls OpenAI TTS (tts-1 model, ~$0.002/question) with `voice_text`
  → Stores MP3 at `/static/audio/q_{id}.mp3`
  → Saves URL on the Question record
- When session is created, hardcoded questions flow through with their `voice_audio_url`
- Frontend: if `voice_audio_url` exists → play `<audio>` element; else → speechSynthesis fallback
- Files: TalentBridge `models.py`, `routers/jobs.py` (question save endpoint), Interview.jsx
- Estimated cost: ~$2 per 1,000 questions, paid once ever
- Effort: ~1 day

**Phase 3 — Session-time TTS for behavioral questions**
- Behavioral questions are candidate-specific (generated from resume) — can't pre-generate
- At session creation: after Claude generates behavioral questions, call TTS for each (2-4 questions)
- Store audio per-session (e.g. `/static/audio/session_{id}/q_{idx}.mp3`)
- Attach `voice_audio_url` to each behavioral question in the session object
- Files: `interview-module/backend/app/routers.py` (session creation endpoint)
- Effort: ~half day

---

#### Implementation Notes for Phase 1

**Flow change in Interview.jsx:**
```
currentIndex changes
  → window.speechSynthesis.cancel()   // stop any ongoing speech
  → speak(voice_text || question)
  → utterance.onend → startRecording()
  → if muted → startRecording() immediately
```

**Chrome speechSynthesis keepalive bug:**
Chrome silently stops speaking after ~15 seconds. Fix:
```js
setInterval(() => {
  if (window.speechSynthesis.speaking) {
    window.speechSynthesis.pause()
    window.speechSynthesis.resume()
  }
}, 10000)
```

**Cancel speech on advance:**
Add `window.speechSynthesis.cancel()` at the top of `nextQuestion()`, `skip()`, and `finish()`.

**Voice selection (macOS):**
```js
const voices = window.speechSynthesis.getVoices()
const preferred = voices.find(v => v.name.includes('Samantha') || v.name.includes('Alex'))
utterance.voice = preferred || voices[0]
```

**Data model change (Claude prompt):**
Update `generate_questions()` in `claude_client.py` to return:
```json
{
  "question": "screen text",
  "voice_text": "conversational spoken version",
  "topic": "...",
  "difficulty": 4
}
```

---

### V3 — Task 7: Natural Conversation + Small Talk

**What:** Interview feels like a real conversation. Light small talk at start ("Hi, how are you feeling today?"). Natural pacing between questions ("Thanks for that answer, let's move on to...").

**Plan:**
- Add a "welcome" phase before questions start — Claude generates a short greeting based on candidate name + role
- Add transition phrases between questions — can be templated, doesn't need Claude
- File to edit: `Interview.jsx` (state machine) + `interview-module/backend/app/claude_client.py` (prompt)

**Effort:** Medium — needs state machine changes in frontend

---

### V3 — Task 9: Follow-Up Questions

**What:** When an answer is too short, off-topic, or unclear, system asks a follow-up (max 1 per question).

**Plan:**
- After candidate submits answer, send it to a lightweight Claude/Haiku call to check if it's substantive
- If not: generate a follow-up question, display + speak it
- Max 1 follow-up per question to avoid interrogation feel
- File to edit: `Interview.jsx` + new backend endpoint `/api/interview/followup`

**Effort:** Medium-high — new backend endpoint + frontend state changes

---

### V3 — Task 8 (from PRODUCT.md): Replace Web Speech API with Whisper

**What:** Server-side STT so interview works in Firefox/Safari and transcripts are stored server-side.

**Plan:**
- Send audio blob to backend after each answer
- Backend transcribes via OpenAI Whisper API
- Return transcript text to frontend
- Eliminates Chrome-only limitation

**Effort:** High — significant frontend + backend changes

---

### V4 — Task 11: Drawing Canvas (Excalidraw)

**What:** For system design questions, candidate can draw diagrams in addition to speaking.

**Plan:**
- Embed Excalidraw as an optional panel alongside voice input
- Export drawing as image/JSON at answer submission
- Include drawing in evaluation context sent to Claude

**Effort:** High — Excalidraw embed + backend changes to handle multimodal input

---

### V5 — Task 12-14: Video + Tone + Proctoring

**What:**
- Task 12: WebRTC video feed capture
- Task 13: Tone of voice analysis as supplementary signal
- Task 14: Basic proctoring (tab switch detection, multiple faces)

**Note from PRODUCT.md:** Video body language is low signal value; proctoring is the primary use case here.

**Effort:** Very high — not started

---

### Stretch — Task 15: AI Video Avatar

**What:** AI video avatar (HeyGen or similar) as the interviewer instead of text on screen.

**Effort:** Very high — not started

---

## Known Issues / Tech Debt

1. **Per-answer `/answer` endpoint exists but is unused by frontend** — frontend calls `/complete` at the end with full transcript. The `/answer` endpoint can be removed or kept for future use (e.g. follow-up logic in V3).

2. **Web Speech API is Chrome-only** — noted, will be replaced by Whisper in V3.

3. **No candidate authentication** — invite token is the only auth mechanism. By design (see PRODUCT.md — candidate auth is out of scope for interview module, handled by TalentBridge invite link).

4. **SQLite in production** — `interview.db` is fine for development. Needs PostgreSQL before real production use.

---

## File Map (Key Files)

```
interview-module/
├── PRODUCT.md              — Full product vision + design decisions
├── TODO.md                 — This file
├── backend/
│   ├── app/
│   │   ├── main.py         — FastAPI app entry, mounts all routers
│   │   ├── routers.py      — All API endpoints (questions, session, evaluate, report, settings, testdata)
│   │   ├── claude_client.py — All Claude API calls (question gen, evaluation, report)
│   │   └── database.py     — SQLite setup (sessions, settings tables)
│   └── requirements.txt
└── frontend/
    └── src/pages/
        ├── Setup.jsx        — Interview setup form (resume, JD, config, test data)
        ├── Interview.jsx    — Main interview UI (voice input, timer, question flow)
        ├── Report.jsx       — Post-interview report display
        ├── Settings.jsx     — Evaluation prompt editor
        └── ThankYou.jsx     — Shown after interview completes (new, unstaged)
```

---

## Next Task to Build

**Task 6 Phase 1: Browser TTS (in progress)**

Files to edit:
1. `interview-module/backend/app/claude_client.py` — update question gen prompt to return `voice_text`
2. `interview-module/frontend/src/pages/Interview.jsx` — add TTS logic, mute toggle, replay button

See full implementation notes in the Task 6 section above.
