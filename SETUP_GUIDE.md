# TalentBridge AI — Complete Setup & Integration Guide

## Table of Contents

1. [Quick Start — Clean Empty Platform](#1-quick-start)
2. [Working Search Bar](#2-working-search-bar)
3. [Gmail SMTP — Sending Invite Emails](#3-gmail-smtp)
4. [Claude — AI Interview Questions & Evaluation](#4-claude-ai-interviews)
5. [Wispr Flow — Speech-to-Text for Candidate Answers](#5-wispr-flow-stt)
6. [OpenAI — TTS Voice & Whisper STT Fallback](#6-openai-tts--whisper)
7. [End-to-End Flow: Apply → Match → Auto-Invite → Interview](#7-end-to-end-flow)
8. [Architecture & API Keys Summary](#8-architecture)

---

## 1. Quick Start

### Reset the database (removes ALL seed/fake data)

```bash
cd backend
python reset_db.py
```

Creates one admin user:

| Field    | Value                      |
|----------|----------------------------|
| Email    | `admin@talentbridge.com`   |
| Password | `admin123`                 |

Customize in `backend/.env` via `ADMIN_EMAIL`, `ADMIN_PASSWORD`, etc.

### Start all four services

```bash
# Terminal 1 — TalentBridge Backend
cd backend
pip install -r requirements.txt
python reset_db.py              # first time only
uvicorn app.main:app --reload --port 8000

# Terminal 2 — TalentBridge Frontend
cd frontend
npm install
npm run dev

# Terminal 3 — Interview Module Backend
cd interview-module/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001

# Terminal 4 — Interview Module Frontend
cd interview-module/frontend
npm install
npm run dev -- --port 5174
```

---

## 2. Working Search Bar

The search bar in the top header searches across **Jobs**, **Candidates**, and **Applications** simultaneously. It uses debounced API calls (300ms), shows a categorized dropdown, and supports `⌘K` / `Ctrl+K` to focus.

**File changed:** `frontend/src/components/common/Layout.jsx`

No backend changes needed — the existing `/api/jobs`, `/api/candidates`, and `/api/applications` endpoints already support `?search=` query parameters.

---

## 3. Gmail SMTP

Gmail sends real screening invite emails to candidates.

### Setup

1. Go to https://myaccount.google.com → **Security**
2. Enable **2-Step Verification** (if not already)
3. Under 2-Step Verification → **App passwords**
4. Generate a password for **Mail**
5. Copy the 16-character password

### Configure

In `backend/.env`:

```env
GMAIL_USER=yourname@gmail.com
GMAIL_APP_PASSWORD=abcdefghijklmnop
```

### When emails are sent

- **Manual invite**: Click "Invite to Screening" on an application
- **Auto-invite**: Candidate applies with resume score ≥ threshold
- **Bulk invite**: Select multiple applications → "Bulk Invite"

### What the email contains

- Candidate name + job title
- Branded HTML template
- "Start Interview →" button with a unique tokenized link
- 48-hour expiry notice

### If not configured

The system logs what would be sent to the console:
```
[EMAIL MOCK] Would send invite to jane@example.com — link: http://localhost:5174/interview/abc?token=xyz
```

### Using other email providers

Edit `backend/app/email_utils.py`:

```python
# SendGrid example:
from sendgrid import SendGridAPIClient
sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))

# Outlook/Office365:
with smtplib.SMTP("smtp.office365.com", 587) as server:
    server.starttls()
    server.login(email, password)
```

---

## 4. Claude — AI Interviews

Claude (Anthropic) powers the entire AI interview intelligence:

| Function | What Claude Does |
|----------|-----------------|
| **Question Generation** | Creates tailored technical + behavioral questions from job description + resume |
| **Answer Evaluation** | Scores each candidate answer on accuracy, depth, communication |
| **Final Report** | Produces overall score, strengths, weaknesses, pass/fail recommendation |

### Get your API key

1. Go to https://console.anthropic.com
2. **Settings** → **API Keys** → **Create Key**
3. Copy the key (starts with `sk-ant-...`)

### Configure

In `interview-module/backend/.env`:

```env
ANTHROPIC_API_KEY=sk-ant-api03-your-key-here
```

### How it's used in code

File: `interview-module/backend/app/claude_client.py`

```python
from anthropic import Anthropic

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=4096,
    system="You are a technical interviewer...",
    messages=[{"role": "user", "content": prompt}]
)
```

### Cost

~$0.05–0.15 per interview (8 questions + evaluation + report).

---

## 5. Wispr Flow — Speech-to-Text

Wispr Flow is the **primary STT provider** for transcribing candidate voice answers during interviews. It's superior to standard STT because it:

- Auto-edits (removes filler words like "um", "uh")
- Corrects self-corrections ("6pm, actually 7pm" → "7pm")
- Is context-aware (understands technical jargon)
- Supports 100+ languages

### Get API access

Wispr Flow API is currently **exclusive access**:

1. Email `enterprise@wisprflow.ai` to request access
2. Once approved, log in at https://platform.wisprflow.ai
3. Go to **API Keys** → **Create new key**
4. Copy the key

### Configure

In `interview-module/backend/.env`:

```env
WISPR_API_KEY=your-wispr-api-key-here
```

### How it works

File: `interview-module/backend/app/wispr_client.py`

The integration supports two modes:

**REST API** (used by default):
```python
response = httpx.post(
    "https://platform-api.wisprflow.ai/api/v1/transcribe",
    headers={"Authorization": f"Bearer {WISPR_API_KEY}"},
    files={"audio": ("audio.webm", audio_file, "audio/webm")},
)
text = response.json()["text"]
```

**WebSocket API** (lower latency, streaming):
```python
ws = websocket.connect(
    "wss://platform-api.wisprflow.ai/api/v1/dash/ws?api_key=Bearer%20<KEY>"
)
# Stream audio chunks → receive partial + final transcription
```

### Fallback behavior

The `/api/interview/transcribe` endpoint automatically falls back:

```
1. Try Wispr Flow (if WISPR_API_KEY is set)
2. If Wispr fails or returns empty → try OpenAI Whisper
3. If neither is configured → return error
```

### Check active provider

```bash
curl http://localhost:8001/api/interview/stt-status
```

Returns:
```json
{
  "wispr_flow": true,
  "openai_whisper": true,
  "active_provider": "wispr_flow"
}
```

---

## 6. OpenAI — TTS & Whisper

OpenAI serves two roles:

| Function | API | What It Does |
|----------|-----|-------------|
| **TTS (Text-to-Speech)** | `tts-1` | Reads interview questions aloud to candidates |
| **Whisper STT (fallback)** | `whisper-1` | Transcribes answers if Wispr Flow is unavailable |

### Get your API key

1. Go to https://platform.openai.com
2. **API Keys** → **Create new secret key**
3. Copy the key (starts with `sk-...`)

### Configure

In `interview-module/backend/.env`:

```env
OPENAI_API_KEY=sk-your-openai-key-here
```

### TTS voices available

`alloy`, `echo`, `fable`, `onyx`, `nova` (default), `shimmer`

### Cost

~$0.02–0.05 per interview for TTS + ~$0.01–0.03 for Whisper fallback.

---

## 7. End-to-End Flow

Here's the complete flow from candidate application to interview results:

```
┌─────────────────────────────────────────────────────────────┐
│  1. CANDIDATE APPLIES                                        │
│     Browse Jobs → Apply → Upload Resume                      │
│     POST /api/public/apply                                   │
├─────────────────────────────────────────────────────────────┤
│  2. RESUME MATCHING (automatic)                              │
│     Extract text (pdfplumber) → Embed (sentence-transformers)│
│     → Cosine similarity → match_score, skills_match          │
│     → AI recommendation (strong_yes / yes / maybe / no)      │
├─────────────────────────────────────────────────────────────┤
│  3. AUTO-INVITE (if enabled on job)                          │
│     IF match_score ≥ threshold:                              │
│       → Create interview session (Claude generates Qs)       │
│       → Create Screening record                              │
│       → Send invite email (Gmail SMTP)                       │
├─────────────────────────────────────────────────────────────┤
│  4. CANDIDATE OPENS INTERVIEW LINK                           │
│     Token validated → Interview Module Frontend loads        │
│     Claude's questions played via OpenAI TTS                 │
├─────────────────────────────────────────────────────────────┤
│  5. CANDIDATE SPEAKS ANSWERS                                 │
│     Browser records audio (MediaRecorder)                    │
│     → Sent to /api/interview/transcribe                      │
│     → Wispr Flow transcribes (or Whisper fallback)           │
├─────────────────────────────────────────────────────────────┤
│  6. ANSWER EVALUATION (per question)                         │
│     Claude evaluates: accuracy, depth, communication         │
│     → Score 0-10 per question                                │
├─────────────────────────────────────────────────────────────┤
│  7. FINAL REPORT (automatic)                                 │
│     Claude generates: overall score, strengths, weaknesses,  │
│     hiring recommendation, pass/fail                         │
│     → POST /api/screenings/complete-from-interview           │
├─────────────────────────────────────────────────────────────┤
│  8. RESULTS IN DASHBOARD                                     │
│     Application status updated (shortlisted/rejected)        │
│     Scores visible in Screenings page                        │
│     Notification bell shows completion                       │
└─────────────────────────────────────────────────────────────┘
```

### How to test the full flow

1. **Create a job** in the dashboard with auto-invite enabled (threshold: 60)
2. **Publish** the job
3. Open `http://localhost:5173/browse-jobs` in an incognito window
4. **Apply** with a resume PDF that matches the job description
5. Check the dashboard — you'll see the application with an AI score
6. If score ≥ 60, check your email (or console for mock) for the invite link
7. Open the interview link → complete the AI interview
8. Check the Screenings page — scores appear automatically

---

## 8. Architecture

### Services

| Service | Port | Purpose |
|---------|------|---------|
| TalentBridge Backend | 8000 | Main API — jobs, candidates, applications, Gmail |
| TalentBridge Frontend | 5173 | Recruiter dashboard |
| Interview Module Backend | 8001 | AI interviews — Claude, OpenAI TTS, Wispr Flow STT |
| Interview Module Frontend | 5174 | Candidate interview UI |

### All API Keys Summary

| Key | Where to get it | Put it in | Used for |
|-----|----------------|-----------|----------|
| `GMAIL_USER` | Your Gmail address | `backend/.env` | Sending invite emails |
| `GMAIL_APP_PASSWORD` | Google Account → App Passwords | `backend/.env` | Gmail SMTP auth |
| `ANTHROPIC_API_KEY` | console.anthropic.com | `interview-module/backend/.env` | Interview questions + evaluation |
| `OPENAI_API_KEY` | platform.openai.com | `interview-module/backend/.env` | TTS voice + Whisper STT fallback |
| `WISPR_API_KEY` | platform.wisprflow.ai | `interview-module/backend/.env` | Primary STT (candidate answers) |

### Cost per interview

| Service | Usage | Cost |
|---------|-------|------|
| Claude Sonnet | Questions + evaluation + report | ~$0.05–0.15 |
| OpenAI TTS | 8 audio clips | ~$0.02–0.05 |
| Wispr Flow | ~30 min audio transcription | Varies by plan |
| **Total** | | **~$0.10–0.25** |

### Files Changed/Added

| File | Change |
|------|--------|
| `frontend/src/components/common/Layout.jsx` | Working search bar across all features |
| `backend/reset_db.py` | NEW — Clears all data, creates admin user |
| `backend/.env` | Gmail SMTP + interview module config |
| `interview-module/backend/.env` | Claude + OpenAI + Wispr Flow keys |
| `interview-module/backend/app/wispr_client.py` | NEW — Wispr Flow STT integration |
| `interview-module/backend/app/routers.py` | Updated transcribe endpoint (Wispr → Whisper fallback) |
| `interview-module/backend/requirements.txt` | Added `websockets>=12.0` |
| `SETUP_GUIDE.md` | This file |
