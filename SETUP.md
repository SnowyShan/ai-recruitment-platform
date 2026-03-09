# TalentBridge — Local Setup Guide

## Prerequisites

- Python 3.9+
- Node.js 18+
- Git
- Two API keys: Anthropic (`console.anthropic.com`) and OpenAI (`platform.openai.com`)

---

## Step 1 — Clone

```bash
git clone <repo-url>
cd ai-recruitment-platform
```

---

## Step 2 — Python environment

One virtual environment is shared by both backends:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r ../interview-module/backend/requirements.txt
```

---

## Step 3 — Environment files

```bash
# Main backend — defaults work, no changes needed
cp .env.example .env

# Interview backend — fill in your API keys
cp ../interview-module/backend/.env.example ../interview-module/backend/.env
```

Edit `interview-module/backend/.env` and fill in:

```
ANTHROPIC_API_KEY=sk-ant-...    # from console.anthropic.com
OPENAI_API_KEY=sk-proj-...      # from platform.openai.com
```

```bash
# Interview frontend — already points to localhost, no changes needed
cp ../interview-module/frontend/.env.example ../interview-module/frontend/.env
```

---

## Step 4 — Main frontend env

```bash
cp frontend/.env.example frontend/.env
# VITE_API_URL is intentionally blank — Vite's dev proxy routes /api → localhost:8000
# Only fill in VITE_INTERVIEW_API_URL and VITE_INTERVIEW_URL if different from defaults
```

## Step 5 — Node dependencies

```bash
cd frontend && npm install
cd ../interview-module/frontend && npm install
```

---

## Step 5 — Start all 4 services

Open 4 terminal tabs and run one command in each:

```bash
# Tab 1 — Main backend (port 8000)
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Tab 2 — Interview backend (port 8001)
cd interview-module/backend && source ../../backend/venv/bin/activate && uvicorn app.main:app --reload --port 8001

# Tab 3 — Main frontend (port 5173)
cd frontend && npm run dev

# Tab 4 — Interview frontend (port 5174)
cd interview-module/frontend && npm run dev
```

Databases are created automatically on first startup — no manual migration needed.

---

## Step 6 — Open the app

- Main app: http://localhost:5173
- Click **Sign Up** and create a recruiter account
- You're in

---

## Step 7 — Run the E2E test (optional)

Verifies the full interview flow works end-to-end:

```bash
cd backend
source venv/bin/activate
pip install playwright && playwright install chromium
python3 ../tests/test_e2e_interview_flow.py
```

Add `--record` to open a real browser window and save a video of the session:

```bash
python3 ../tests/test_e2e_interview_flow.py --record
```

Recordings are saved to `tests/recordings/`.

> **Tip:** Install [BlackHole 2ch](https://existential.audio/blackhole/) for clean audio loopback during the recorded test. Without it the test still passes but uses your Mac's speakers/mic.
