# TalentBridge E2E Tests

## Setup

```bash
pip install playwright requests pytest
playwright install chromium
```

## Tests

### `test_e2e_interview_flow.py` — Full Interview Flow

The most important test. Covers the entire critical path:

```
Login → Job Detail → Mock Interview → Interview Module → Report Accuracy
```

**What it tests:**
- Auth (register/login)
- Job creation and publishing
- Job setup (question bank generation)
- Mock interview launch (new window via `window.open`)
- Full interview UI flow (instructions → questions → finish)
- Report generation
- Report **accuracy**: alternates known GOOD (iOS expertise) and BAD (wrong domain) answers, then asserts the AI scored them correctly

**Answer strategy:**
- GOOD: detailed, correct Swift/iOS/UIKit answer — scores high regardless of specific question
- BAD: Python/ML/Django answer — wrong domain for iOS role, scores near-zero
- Pattern: Q1=GOOD, Q2=BAD, Q3=GOOD, Q4=BAD, …
- Assert: avg(GOOD) > 40, avg(BAD) < 50, gap ≥ 25

**Audio/mic mocking:**
- `getUserMedia` replaced with silent `AudioContext` stream
- `/api/interview/transcribe` intercepted by Playwright — returns predetermined text
- TTS disabled via `localStorage` — no waiting for audio playback

**Run:**
```bash
# Make sure all 4 services are running first:
#   localhost:8000 (TB backend)
#   localhost:5173 (TB frontend)
#   localhost:8001 (Interview backend)
#   localhost:5174 (Interview frontend)

python3 tests/test_e2e_interview_flow.py

# Or via pytest:
pytest tests/test_e2e_interview_flow.py -v
```

**Expected output (passing):**
```
✅ TB backend: 200
✅ Interview backend: 200
✅ TB frontend: 200
✅ Interview frontend: 200
...
✅ ALL ASSERTIONS PASSED — flow and report accuracy verified
```
