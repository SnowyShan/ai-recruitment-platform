# TalentBridge — Interview Module TODO
*Last updated: March 7, 2026*
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
- [x] **Task 6 Phase 1:** Browser TTS (speechSynthesis) — questions read aloud via `window.speechSynthesis`, mute toggle, replay button, Chrome keepalive fix, Safari restart bug fixed (keepalive disabled on non-Chrome), auto-record starts after speech ends.
- [x] **Task 6 Phase 2:** OpenAI TTS (`tts-1`, voice `nova`) — backend `/api/interview/tts` endpoint streams audio/mpeg on demand per question. Frontend plays `<audio>` element; falls back to speechSynthesis on error. Generation counter prevents stale in-flight responses from playing after user advances. Pre-interview instructions screen handles iOS autoplay gate — Q0 audio pre-fetched while user reads instructions, plays instantly on "Start Interview" tap.
- [x] **Task 6 Phase 3: Pre-generated audio question bank** — Backend generates TTS audio for all technical questions at job creation time (background job). New `questions` table stores question bank with `audio_path` per entry; new `job_setup` table tracks generation status per job. Interview module serves pre-built audio as static files (`/audio`). Session creation uses bank questions + freshly generated behavioral questions (resume-tailored). Frontend pre-fetches audio for all questions in parallel during "ready" phase; falls back to on-demand TTS if no pre-generated audio. On-the-fly question generation at session creation time removed — `create_session` now requires a ready `job_setup` (returns 400/409 otherwise). TalentBridge: publish and invite blocked while `setup_status='generating'`; JobDetail shows live progress bar (polls every 3s); CreateJobModal has behavioral split slider (default 20%).
- [x] **Pre-interview instructions screen** — shows duration, question count, usage tips. "Allow Microphone & Continue" requests mic permission. "Start Interview" tap is the iOS user gesture that unlocks audio autoplay. No "Tap to Begin" needed inside the interview itself.
- [x] **Safari/iOS compatibility** — TDZ crash fixed (declaration reorder), transcript capture race condition fixed (`questionAnswersRef` updated live on every `onresult`), production build via `npx serve` instead of vite dev server, mic permission requested upfront.
- [x] **Mobile responsive layout** — all pages (Setup, Interview, Report, Settings, ThankYou) fully responsive.

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

5. **Audio files committed to repo** — pre-generated `.mp3` files land in `interview-module/backend/audio/`. Should be gitignored and stored externally (S3/CDN) before production.

---

## Recent Fixes (post March 5)

- **Duplicate transcript entries** — Web Speech API race condition causing duplicate `onresult` events written to transcript. Fixed by deduplicating on result index (`0b717fe`, `d8c2a32`).
- **Per-question report deduplication** — fixed duplicate entries in evaluation report (`d8c2a32`).
- **Blank screen after mic grant** — stale `prefetchedAudioRef` reference after question bank refactor. Fixed (`4f64f0e`).
- **Mock interview delay + pre-fetch audio destroyed on start** — timing bug in mock interview flow; pre-fetched audio was being torn down before playback. Fixed (`8217754`).
- **Overlapping audio / audio-after-End** — audio kept playing past interview end or overlapped on question advance. Fixed (`42c9f0e`).
- **UnboundLocalError in `create_screening`** — `job` variable referenced before assignment in error path. Fixed (`7539e77`).
- **Applications list 500** — `CandidateResponse.email` was `EmailStr`, rejecting test emails like `matt@bat`. Changed to `str` (`f034fd1`).
- **Publish button / screening config during generation** — Jobs list now shows amber "Generating…" pill; screening config grayed out with `pointer-events-none` while setup in progress (`f034fd1`).
- **Auto-trigger setup for old jobs** — jobs created before `setup_status` column existed now auto-trigger setup on first load (`05cf0a1`).
- **Question type badge removed** — cleaned up from interview UI (`cc1af65`).

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

**Task 7: Natural Conversation — small talk intro + transition phrases between questions**

See Task 7 section below for implementation plan.
