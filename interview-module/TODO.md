# TalentBridge — Interview Module TODO
*Last updated: March 28, 2026*
*Use this file to come up to speed on the project before making changes.*

---

## Project Overview

TalentBridge is an AI-powered recruitment platform. The **interview module** is a standalone microservice that conducts AI-powered screening interviews with candidates via voice. Built independently, then integrated into TalentBridge.

### Architecture (Two Services)

```
TalentBridge (main)           Interview Module (standalone)
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

### Starting All 4 Services

```bash
# Tab 1 — TalentBridge backend (port 8000)
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Tab 2 — Interview backend (port 8001)
cd interview-module/backend && source ../../backend/venv/bin/activate && uvicorn app.main:app --reload --port 8001

# Tab 3 — TalentBridge frontend (port 5173)
cd frontend && npm run dev

# Tab 4 — Interview frontend (port 5174)
cd interview-module/frontend && npm run dev -- --port 5174
```

---

## What Is Built ✅

### MVC — All Complete

- [x] **Task 1:** Question generation — Claude generates questions from resume + JD. Difficulty slider (1-5). Behavioral questions derived from resume, technical from domain.
- [x] **Task 2:** Answer evaluation — Full transcript sent to Claude at end of session (NOT per-answer). Configurable seniority bar (junior/mid/senior/staff).
- [x] **Task 3:** Voice input — MediaRecorder + OpenAI Whisper on all platforms. Works on iOS (Chrome + Safari), Android Chrome, desktop Chrome/Firefox/Safari.
- [x] **Task 4:** Auto-terminate — Countdown timer. When time expires, 2-minute wrap-up window given. After wrap-up, session auto-completes.
- [x] **Task 5:** Report generation — Full transcript + questions sent to Claude in one batch call at session end. Detailed report: per-question scores, overall pass/fail, strengths, weaknesses. Report POSTed back to TalentBridge and stored.

### V2 — Voice Out ✅ Complete

- [x] **Task 6 Phase 1:** Browser TTS (speechSynthesis) — questions read aloud, mute toggle, replay button.
- [x] **Task 6 Phase 2:** OpenAI TTS (`tts-1`, voice `nova`) — backend `/api/interview/tts` streams audio/mpeg per question. Falls back to speechSynthesis on error.
- [x] **Task 6 Phase 3:** Pre-generated audio question bank — TTS generated once at job creation, stored on disk, reused per candidate. Behavioral questions generated fresh per candidate (resume-tailored).
- [x] **Task 7:** Replaced Web Speech API with MediaRecorder + OpenAI Whisper — cross-browser, server-side transcription, works on iOS/Safari/Firefox.

### V3 — Natural Conversation + Follow-ups ✅ Complete

- [x] **Task 8:** Natural conversational tone — small talk intro, transition phrases between questions.
- [x] **Task 9 / Task 13 (Core Competency Probes):** When a question is flagged ⭐ Core in the question bank, the system pre-generates narrow follow-up probes. If the candidate's answer is shallow, the probe fires automatically (max 2 probes per question). Probes can include code snippets. Probe answers included in evaluation context. Full browser-driven E2E test: 20/20 checks, real BlackHole audio, Playwright, video recording.

### V4 — Multimodal Input ✅ Complete

- [x] **Task 10/11:** Excalidraw drawing canvas + plain code editor tab in `Interview.jsx`. Tab bar `[ Voice | Code | Draw ]`. On submit: Excalidraw JSON + PNG exported and attached to Claude evaluation context.

### V5 — Video ✅ Complete

- [x] **Task 12 / Task 15 (AI Video Avatar):** Recruiter video feed via D-ID (provider-swappable; HeyGen also supported). Video interview is a job-level config (off by default). When enabled, video fully replaces TTS — recruiter avatar speaks each question. Provider selector in Settings.

### Infrastructure / Integration ✅ Complete

- [x] TalentBridge screening flow creates interview sessions via API
- [x] Token-based invite system (time-limited, single-use, 48hr expiry)
- [x] Real email invites via Gmail SMTP
- [x] Token validation on interview start
- [x] Session rejoin — candidate can rejoin an `in_progress` session
- [x] Callback to TalentBridge on completion with full report
- [x] "View Report" in TalentBridge JobDetail screening history
- [x] Mock Interview button — recruiter can launch a test interview from JobDetail
- [x] Question bank scoped per job (job_id filter on `/question-bank`)
- [x] Pre-interview instructions screen
- [x] Mobile-responsive UI (all pages)
- [x] Safari/iOS compatibility

### Testing ✅

- [x] Full E2E test suite (`tests/`) — Playwright + BlackHole, real Whisper, real Claude
- [x] Core Competency Probes E2E (`tests/test_core_competency.py`) — 20 checks, browser-driven, video recording

---

## What Is Remaining ❌

### Task 14: Basic Proctoring

**What:** Detect signs of cheating or unusual conditions during the interview.

**Features to implement:**
- Tab switch / window blur detection (log + flag in report)
- Multiple faces detected via webcam (warn candidate + log)
- Unusual audio (long silences, background voices) — flag in transcript

**Plan:**
- Frontend: `visibilitychange` + `blur` events for tab switching
- Webcam face detection: browser-side with `face-api.js` or similar (no server round-trip)
- Proctoring events stored on session, surfaced in evaluation report as a "Proctoring Notes" section

**Effort:** Medium — frontend-heavy, no new backend endpoints needed except storing events

---

### Task 13 (tone): Tone of Voice Analysis

**What:** Analyse the candidate's vocal tone (confidence, hesitation, pace) as a supplementary signal alongside the transcript.

**Plan:**
- Send audio clips to a tone/emotion API (e.g. Hume AI, or a self-hosted Whisper + prosody model)
- Include tone summary as supplementary context in Claude evaluation prompt
- NOT a primary hiring signal — clearly labelled as supplementary

**Effort:** High — requires audio pipeline changes and a new external API integration

---

## Known Issues / Tech Debt

1. **Per-answer `/answer` endpoint exists but is unused** — frontend calls `/complete` at end with full transcript. Can be removed.
2. **SQLite in production** — fine for development. Needs PostgreSQL before real production use.
3. **Audio files not in repo** — `interview-module/backend/audio/*.mp3` gitignored. Generated at runtime. Move to S3/CDN before production.
4. **D-ID / HeyGen video** requires paid API keys — video mode is off by default; falls back gracefully to TTS when keys not configured.

---

## Current State (March 28, 2026)

- **HEAD:** `59c2dd9` — 12 commits ahead of `origin/main` (not pushed)
- **Last work:** CC probe E2E test — fixed wrong number input targeting, fixed behavioral_pct ordering
- **All 4 services running** on standard ports (8000, 8001, 5173, 5174)
- **Stable rollback point:** `d1c85db` (`test: Test 7 — in_progress re-entry regression + full interview launch`)

---

## File Map (Key Files)

```
interview-module/
├── PRODUCT.md              — Full product vision + design decisions
├── TODO.md                 — This file
├── backend/
│   ├── app/
│   │   ├── main.py         — FastAPI app entry, mounts all routers
│   │   ├── routers.py      — All API endpoints
│   │   ├── claude_client.py — All Claude API calls
│   │   ├── video_client.py — D-ID / HeyGen video generation
│   │   └── database.py     — SQLite setup
│   └── requirements.txt
└── frontend/
    └── src/pages/
        ├── Setup.jsx        — Interview setup form
        ├── Interview.jsx    — Main interview UI (voice, code, draw tabs; CC probes; video mode)
        ├── Report.jsx       — Post-interview report display
        ├── Settings.jsx     — Evaluation prompt editor + video provider selector
        └── ThankYou.jsx     — Shown after interview completes

tests/
├── test_e2e_interview_flow.py   — Full interview flow E2E (7 tests)
├── test_core_competency.py      — CC probe E2E (20 checks, browser-driven)
└── recordings/                  — WebM recordings from --record runs
```
