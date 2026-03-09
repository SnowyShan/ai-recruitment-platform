# TalentBridge — Local Setup Guide

## Prerequisites

- Python 3.9+
- Node.js 18+
- Git

## 1. Clone the repo

```bash
git clone <repo-url>
cd ai-recruitment-platform
```

## 2. Backend (Main API — port 8000)

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Copy and fill in the env file:

```bash
cp .env.example .env
```

Edit `backend/.env` — the defaults are fine for local dev. No API keys needed here.

Initialize the database:

```bash
python3 -c "from app.database import engine; from app.models import Base; Base.metadata.create_all(engine)"
```

Start the server:

```bash
uvicorn app.main:app --reload --port 8000
```

---

## 3. Interview Module Backend (port 8001)

```bash
cd interview-module/backend
# Reuse the same venv or create a new one
source ../../backend/venv/bin/activate
pip install -r requirements.txt
```

Copy and fill in the env file:

```bash
cp .env.example .env
```

Edit `interview-module/backend/.env` and fill in your API keys:

```
ANTHROPIC_API_KEY=your-anthropic-key-here   # from console.anthropic.com
OPENAI_API_KEY=your-openai-key-here         # from platform.openai.com
DB_PATH=./interview.db
TALENTBRIDGE_API_URL=http://localhost:8000
```

Start the server:

```bash
uvicorn main:app --reload --port 8001
```

---

## 4. Main Frontend (port 5173)

```bash
cd frontend
npm install
npm run dev
```

No env file needed — defaults to `http://localhost:8000`.

---

## 5. Interview Module Frontend (port 5174)

```bash
cd interview-module/frontend
npm install
cp .env.example .env   # already points to localhost:8001 and localhost:8000
npm run build
npx serve dist -p 5174
```

---

## 6. Verify everything is running

Open your browser and check:

- Main app: http://localhost:5173
- Interview module: http://localhost:5174

All four services must be running at the same time for the full flow to work.

---

## 7. Create your first recruiter account

Go to http://localhost:5173 and sign up. There is no pre-seeded admin account — just register directly.

---

## Running the E2E test

The E2E test validates the full interview flow (auth → job setup → question generation → interview → scoring).

```bash
cd backend
source venv/bin/activate
pip install playwright
playwright install chromium
python3 ../tests/test_e2e_interview_flow.py
```

Add `--record` to open a real browser window and record a video of the session:

```bash
python3 ../tests/test_e2e_interview_flow.py --record
```

Recordings are saved to `tests/recordings/`.

> **Note:** The `--record` flag uses BlackHole 2ch for clean audio loopback if installed.
> Install it from https://existential.audio/blackhole/ for best results.

---

## API Keys

| Key | Where to get it |
|-----|----------------|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com |
| `OPENAI_API_KEY` | https://platform.openai.com/api-keys |

Both are required. The interview module uses Anthropic for question generation and scoring, and OpenAI Whisper for speech-to-text transcription and TTS for question audio.
