# TalentBridge Capstone Polish — Implementation Plan

**Estimated time:** 3–4 days  
**Goal:** Polish TalentBridge for a capstone presentation by adding three high-impact features  
**Repo:** `~/Documents/projects/ai-recruitment-platform`  
**Stack:** FastAPI (Python) backends, React + Vite frontends, SQLite DBs, Claude Sonnet for AI

---

## Architecture Overview

The project has two separate services:

| Service | Backend Port | Frontend Port | DB |
|---|---|---|---|
| TalentBridge main | 8000 | 5173 | `talentbridge.db` |
| Interview module | 8001 | 5174 | `interview.db` |

Start all 4 before testing:
```bash
cd ~/Documents/projects/ai-recruitment-platform/backend && uvicorn main:app --port 8000 --reload
cd ~/Documents/projects/ai-recruitment-platform/frontend && npm run dev
cd ~/Documents/projects/ai-recruitment-platform/interview-module/backend && uvicorn main:app --port 8001 --reload
cd ~/Documents/projects/ai-recruitment-platform/interview-module/frontend && npm run dev
```

---

## Feature 1: Interview Insights Dashboard

**Time estimate:** 2 days  
**Impact:** Highest — turns TalentBridge from a per-candidate tool into a hiring intelligence platform  
**Location:** Main app (`backend/` + `frontend/src/`)

### What it does
A recruiter dashboard showing aggregate analytics across all candidates for a job posting:
- Score distribution histogram (overall + per-dimension)
- Common strengths and weaknesses across the cohort (Claude-derived)
- Ranked candidate list with one-click "Advance" / "Reject" status
- Side-by-side comparison of top N candidates

---

### Backend changes

#### 1. New endpoint: `GET /jobs/{job_id}/insights`

**File:** `backend/main.py` (or a new `backend/routers/insights.py`)

```python
@app.get("/jobs/{job_id}/insights")
async def get_job_insights(job_id: int, db: Session = Depends(get_db)):
    """
    Returns aggregate analytics for all completed interviews for a job.
    """
    # 1. Fetch all interview sessions for this job with status='completed'
    interviews = db.query(InterviewSession).filter(
        InterviewSession.job_id == job_id,
        InterviewSession.status == 'completed'
    ).all()

    if not interviews:
        return {"job_id": job_id, "candidate_count": 0, "insights": None}

    # 2. Fetch evaluation reports for each interview
    reports = []
    for iv in interviews:
        report = db.query(EvaluationReport).filter(
            EvaluationReport.interview_id == iv.id
        ).first()
        if report:
            reports.append({
                "candidate_id": iv.candidate_id,
                "candidate_name": iv.candidate.name,  # join
                "overall_score": report.overall_score,
                "dimension_scores": json.loads(report.dimension_scores),  # dict
                "strengths": report.strengths,
                "weaknesses": report.weaknesses,
                "recommendation": report.recommendation,
                "interview_id": iv.id
            })

    # 3. Compute aggregate stats
    scores = [r["overall_score"] for r in reports]
    avg_score = sum(scores) / len(scores)

    # Score distribution buckets: 0-2, 2-4, 4-6, 6-8, 8-10
    distribution = {"0-2": 0, "2-4": 0, "4-6": 0, "6-8": 0, "8-10": 0}
    for s in scores:
        if s < 2: distribution["0-2"] += 1
        elif s < 4: distribution["2-4"] += 1
        elif s < 6: distribution["4-6"] += 1
        elif s < 8: distribution["6-8"] += 1
        else: distribution["8-10"] += 1

    # Dimension averages
    dimension_keys = list(reports[0]["dimension_scores"].keys()) if reports else []
    dimension_averages = {}
    for key in dimension_keys:
        vals = [r["dimension_scores"].get(key, 0) for r in reports]
        dimension_averages[key] = round(sum(vals) / len(vals), 2)

    # 4. Call Claude to synthesize cohort-level strengths/weaknesses
    cohort_summary = await synthesize_cohort_insights(reports)

    return {
        "job_id": job_id,
        "candidate_count": len(reports),
        "average_score": round(avg_score, 2),
        "score_distribution": distribution,
        "dimension_averages": dimension_averages,
        "cohort_summary": cohort_summary,
        "candidates": sorted(reports, key=lambda r: r["overall_score"], reverse=True)
    }
```

#### 2. New helper: `synthesize_cohort_insights(reports)`

**File:** `backend/ai_utils.py` (or inline in `main.py` near other Claude calls)

```python
async def synthesize_cohort_insights(reports: list) -> dict:
    """
    Uses Claude to identify common patterns across all candidate reports.
    Returns: { "common_strengths": [...], "common_weaknesses": [...], "hiring_recommendation": str }
    """
    summaries = []
    for r in reports:
        summaries.append(
            f"Candidate: {r['candidate_name']} | Score: {r['overall_score']}/10\n"
            f"Strengths: {r['strengths']}\nWeaknesses: {r['weaknesses']}"
        )

    prompt = f"""You are analyzing a cohort of {len(reports)} candidates who interviewed for the same role.

Here are their individual evaluations:

{chr(10).join(summaries)}

Based on all candidates:
1. What are the 2-3 most common STRENGTHS across this cohort?
2. What are the 2-3 most common WEAKNESSES or gaps?
3. Give a 1-sentence hiring recommendation (e.g., "Strong cohort — top 3 candidates are ready to advance" or "Weak pipeline — consider re-sourcing")

Respond as JSON:
{{
  "common_strengths": ["...", "..."],
  "common_weaknesses": ["...", "..."],
  "hiring_recommendation": "..."
}}"""

    response = await call_claude(prompt)  # use existing Claude wrapper in the codebase
    return json.loads(response)
```

#### 3. New endpoint: `PATCH /interviews/{interview_id}/status`

Allows recruiter to advance or reject a candidate with one click.

```python
class StatusUpdateRequest(BaseModel):
    status: str  # "advanced" | "rejected" | "pending"

@app.patch("/interviews/{interview_id}/status")
async def update_interview_status(
    interview_id: int,
    body: StatusUpdateRequest,
    db: Session = Depends(get_db)
):
    interview = db.query(InterviewSession).filter(InterviewSession.id == interview_id).first()
    if not interview:
        raise HTTPException(404, "Interview not found")
    interview.recruiter_status = body.status
    db.commit()
    return {"interview_id": interview_id, "status": body.status}
```

**DB migration needed** — add `recruiter_status` column to interview sessions:

```python
# In backend/models.py, add to InterviewSession model:
recruiter_status = Column(String, default="pending")  # "pending" | "advanced" | "rejected"

# Also run this SQL against talentbridge.db if not using alembic:
# ALTER TABLE interview_sessions ADD COLUMN recruiter_status VARCHAR DEFAULT 'pending'
```

---

### Frontend changes

#### 1. New page: `InsightsDashboard.jsx`

**File:** `frontend/src/pages/InsightsDashboard.jsx`

**Install dependency first:**
```bash
cd frontend && npm install recharts
```

```jsx
import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function InsightsDashboard() {
  const { jobId } = useParams();
  const navigate = useNavigate();
  const [insights, setInsights] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`http://localhost:8000/jobs/${jobId}/insights`)
      .then(r => r.json())
      .then(data => { setInsights(data); setLoading(false); });
  }, [jobId]);

  const handleStatusChange = async (interviewId, status) => {
    await fetch(`http://localhost:8000/interviews/${interviewId}/status`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status })
    });
    setInsights(prev => ({
      ...prev,
      candidates: prev.candidates.map(c =>
        c.interview_id === interviewId ? { ...c, recruiter_status: status } : c
      )
    }));
  };

  if (loading) return <div className="loading">Loading insights...</div>;
  if (!insights || insights.candidate_count === 0) {
    return <div className="empty-state">No completed interviews yet for this role.</div>;
  }

  const distData = Object.entries(insights.score_distribution).map(([range, count]) => ({ range, count }));
  const dimData = Object.entries(insights.dimension_averages).map(([dim, avg]) => ({ dim, avg }));

  return (
    <div className="insights-dashboard p-6">
      <button onClick={() => navigate(-1)} className="btn-back">← Back</button>
      <h1 className="text-2xl font-bold mb-1">Hiring Insights</h1>
      <p className="text-gray-500 mb-6">{insights.candidate_count} candidates · Avg score: <strong>{insights.average_score}/10</strong></p>

      {/* Claude cohort summary */}
      <section className="card mb-6">
        <h2 className="section-title">Cohort Analysis</h2>
        <p className="hiring-rec text-lg mb-4">💡 {insights.cohort_summary.hiring_recommendation}</p>
        <div className="grid grid-cols-2 gap-4">
          <div>
            <h3 className="font-semibold mb-2">Common Strengths</h3>
            <ul className="list-disc pl-4">
              {insights.cohort_summary.common_strengths.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          </div>
          <div>
            <h3 className="font-semibold mb-2">Common Gaps</h3>
            <ul className="list-disc pl-4">
              {insights.cohort_summary.common_weaknesses.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          </div>
        </div>
      </section>

      {/* Score distribution */}
      <section className="card mb-6">
        <h2 className="section-title">Score Distribution</h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={distData}>
            <XAxis dataKey="range" />
            <YAxis allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="count" fill="#6366f1" radius={[4,4,0,0]} />
          </BarChart>
        </ResponsiveContainer>
      </section>

      {/* Dimension averages */}
      {dimData.length > 0 && (
        <section className="card mb-6">
          <h2 className="section-title">Dimension Averages</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={dimData} layout="vertical">
              <XAxis type="number" domain={[0, 10]} />
              <YAxis dataKey="dim" type="category" width={180} />
              <Tooltip />
              <Bar dataKey="avg" fill="#10b981" radius={[0,4,4,0]} />
            </BarChart>
          </ResponsiveContainer>
        </section>
      )}

      {/* Ranked candidate list */}
      <section className="card">
        <h2 className="section-title">Candidates (ranked by score)</h2>
        <table className="w-full">
          <thead>
            <tr className="text-left border-b">
              <th className="py-2">Name</th>
              <th>Score</th>
              <th>Recommendation</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {insights.candidates.map(c => (
              <tr key={c.interview_id} className="border-b hover:bg-gray-50">
                <td className="py-3 font-medium">{c.candidate_name}</td>
                <td>
                  <span className={`badge ${c.overall_score >= 7 ? 'badge-green' : c.overall_score >= 5 ? 'badge-yellow' : 'badge-red'}`}>
                    {c.overall_score}/10
                  </span>
                </td>
                <td className="text-sm text-gray-600 max-w-xs">{c.recommendation}</td>
                <td>
                  {c.recruiter_status === 'advanced' && <span className="badge badge-green">✓ Advanced</span>}
                  {c.recruiter_status === 'rejected' && <span className="badge badge-red">✗ Rejected</span>}
                  {(!c.recruiter_status || c.recruiter_status === 'pending') && <span className="badge badge-gray">Pending</span>}
                </td>
                <td className="flex gap-2 py-2">
                  <button
                    onClick={() => handleStatusChange(c.interview_id, 'advanced')}
                    className="btn-sm btn-green"
                  >Advance</button>
                  <button
                    onClick={() => handleStatusChange(c.interview_id, 'rejected')}
                    className="btn-sm btn-red"
                  >Reject</button>
                  <button
                    onClick={() => navigate(`/interviews/${c.interview_id}/report`)}
                    className="btn-sm btn-outline"
                  >Report</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
```

#### 2. Add route in `App.jsx`

```jsx
import InsightsDashboard from './pages/InsightsDashboard';
// Add to router:
<Route path="/jobs/:jobId/insights" element={<InsightsDashboard />} />
```

#### 3. Add "View Insights" button on `JobDetail.jsx`

```jsx
import { useNavigate } from 'react-router-dom';
const navigate = useNavigate();

// Add near the screening/candidates section:
<button
  onClick={() => navigate(`/jobs/${job.id}/insights`)}
  className="btn-primary"
>
  📊 View Hiring Insights
</button>
```

---

## Feature 2: AI Job Description Generator

**Time estimate:** ~3–4 hours  
**Impact:** High demo wow factor  
**Location:** Main app (`backend/` + `frontend/src/`)

### What it does
On the job creation/edit page, recruiter types a short prompt and Claude generates a full professional JD.

---

### Backend changes

**File:** `backend/main.py`

```python
class JDGenerateRequest(BaseModel):
    prompt: str

@app.post("/jobs/generate-description")
async def generate_job_description(request: JDGenerateRequest):
    """
    Takes a short recruiter prompt and returns a full professional job description.
    """
    claude_prompt = f"""You are an expert technical recruiter. Generate a professional job description based on this brief:

"{request.prompt}"

Format the output as:
## [Job Title]

**About the Role**
[2-3 sentence overview]

**What You'll Do**
- [responsibility]
- [responsibility]
- [responsibility]
- [responsibility]
- [responsibility]

**What We're Looking For**
- [requirement]
- [requirement]
- [requirement]
- [requirement]
- [requirement]

**Nice to Have**
- [optional requirement]
- [optional requirement]

Be specific and realistic. Use the tech stack and seniority level implied by the prompt. Avoid buzzword inflation."""

    result = await call_claude(claude_prompt)  # reuse existing Claude wrapper
    return {"description": result}
```

---

### Frontend changes

**File:** `frontend/src/pages/CreateJob.jsx` (or `Jobs.jsx` / wherever job creation form lives)

Find the job description textarea and add a generator above it:

```jsx
const [jdPrompt, setJdPrompt] = useState('');
const [generating, setGenerating] = useState(false);

const generateDescription = async () => {
  if (!jdPrompt.trim()) return;
  setGenerating(true);
  try {
    const res = await fetch('http://localhost:8000/jobs/generate-description', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: jdPrompt })
    });
    const data = await res.json();
    // Update your form state — adjust field name to match existing form
    setFormData(prev => ({ ...prev, description: data.description }));
  } finally {
    setGenerating(false);
  }
};

// Add this JSX above the description textarea:
<div className="jd-generator mb-3">
  <label className="block text-sm font-medium mb-1">✨ Generate with AI</label>
  <div className="flex gap-2">
    <input
      type="text"
      className="input flex-1"
      placeholder='e.g. "Senior iOS Engineer, SwiftUI + on-device ML, 5+ years"'
      value={jdPrompt}
      onChange={e => setJdPrompt(e.target.value)}
      onKeyDown={e => e.key === 'Enter' && generateDescription()}
    />
    <button
      type="button"
      onClick={generateDescription}
      disabled={generating}
      className="btn-primary whitespace-nowrap"
    >
      {generating ? '⏳ Generating...' : '✨ Generate'}
    </button>
  </div>
  <p className="text-xs text-gray-400 mt-1">Or write your own description below</p>
</div>
```

---

## Feature 3: Candidate Experience Polish

**Time estimate:** ~4–5 hours  
**Note:** No candidate feedback emails — TalentBridge is white-label and companies control that flow.

### 3a. Pre-interview briefing page

**File:** Create `interview-module/frontend/src/pages/InterviewBriefing.jsx`

```jsx
export default function InterviewBriefing({ onStart, jobTitle }) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg max-w-lg w-full p-8">
        <h1 className="text-2xl font-bold mb-2">Ready for your interview?</h1>
        {jobTitle && <p className="text-gray-500 mb-6">Position: <strong>{jobTitle}</strong></p>}

        <div className="mb-6">
          <h2 className="font-semibold mb-3">Before you begin:</h2>
          <ul className="space-y-2">
            {[
              "Find a quiet place with no background noise",
              "Make sure your microphone is working",
              "You'll have time to think before answering each question",
              "Answer as you would in a real interview — be specific, use examples",
              "The interview takes approximately 20–30 minutes",
            ].map((item, i) => (
              <li key={i} className="flex items-start gap-2">
                <span className="text-green-500 mt-0.5">✓</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-6 text-sm text-amber-800">
          ⚠️ This interview is monitored. Keep this tab open and stay in frame throughout.
        </div>

        <button
          onClick={onStart}
          className="w-full bg-indigo-600 text-white py-3 rounded-xl font-semibold hover:bg-indigo-700 transition"
        >
          Start Interview →
        </button>
      </div>
    </div>
  );
}
```

**Wire up in the interview flow** — find where the interview session starts (likely `Setup.jsx` → `Interview.jsx` transition) and insert the briefing page before the interview begins:

```jsx
// In App.jsx or interview router:
// Add a state: const [showBriefing, setShowBriefing] = useState(true);
// Render InterviewBriefing first, then Interview when showBriefing === false
```

### 3b. Progress indicator during interview

**File:** `interview-module/frontend/src/pages/Interview.jsx`

Find where the current question is displayed and add above it:

```jsx
{/* Add to interview header */}
<div className="mb-4">
  <div className="flex justify-between text-sm text-gray-500 mb-1">
    <span>Question {currentQuestionIndex + 1} of {questions.length}</span>
    <span>{Math.round(((currentQuestionIndex + 1) / questions.length) * 100)}% complete</span>
  </div>
  <div className="w-full bg-gray-200 rounded-full h-2">
    <div
      className="bg-indigo-600 h-2 rounded-full transition-all duration-500"
      style={{ width: `${((currentQuestionIndex + 1) / questions.length) * 100}%` }}
    />
  </div>
</div>
```

### 3c. Polished completion screen

**File:** `interview-module/frontend/src/pages/ThankYou.jsx` (already exists — polish it)

Replace or enhance the existing ThankYou page:

```jsx
export default function ThankYou({ candidateName }) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="bg-white rounded-2xl shadow-lg max-w-md w-full p-10 text-center">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <span className="text-3xl">✓</span>
        </div>
        <h1 className="text-2xl font-bold mb-2">Interview Complete</h1>
        {candidateName && <p className="text-gray-500 mb-4">Thank you, {candidateName}.</p>}
        <p className="text-gray-600 mb-6">
          Your responses have been submitted for review. The hiring team will be in touch regarding next steps.
        </p>
        <p className="text-sm text-gray-400">You can close this window.</p>
      </div>
    </div>
  );
}
```

---

## Implementation Order (recommended)

| Day | Task | Est. Time |
|---|---|---|
| Day 1 AM | Feature 2: JD Generator (backend + frontend) | ~4 hrs |
| Day 1 PM | Feature 3: Candidate experience polish (briefing + progress + thank you) | ~4 hrs |
| Day 2–3 | Feature 1: Insights Dashboard backend (endpoint + Claude synthesis + DB migration) | ~1 day |
| Day 4 | Feature 1: Insights Dashboard frontend (charts + table + status buttons) | ~1 day |

---

## Key Files Reference

```
ai-recruitment-platform/
├── backend/
│   ├── main.py              ← Add all new backend routes here
│   ├── models.py            ← Add recruiter_status column to InterviewSession
│   ├── database.py          ← DB setup / get_db dependency
│   └── [claude util file]   ← Find existing call_claude() wrapper, reuse it
├── frontend/
│   └── src/
│       ├── App.jsx          ← Add route for /jobs/:jobId/insights
│       └── pages/
│           ├── JobDetail.jsx        ← Add "View Insights" button
│           ├── CreateJob.jsx        ← Add JD Generator
│           └── InsightsDashboard.jsx  ← CREATE THIS FILE
└── interview-module/
    └── frontend/
        └── src/
            └── pages/
                ├── Interview.jsx         ← Add progress bar
                ├── ThankYou.jsx          ← Polish completion screen
                └── InterviewBriefing.jsx ← CREATE THIS FILE
```

---

## Notes for the Implementing Agent

1. **Find the Claude wrapper first** — search `backend/main.py` for `anthropic` or `claude`. There's already a function that calls Claude. Reuse it for both new endpoints. Don't create a new Anthropic client.

2. **Check actual DB model field names** — look at `models.py` for the exact column names on `InterviewSession` and `EvaluationReport`. The field names in this doc are illustrative.

3. **Don't break existing tests** — run `pytest` before starting. Run again after each feature. There's a full E2E test suite.

4. **Match existing frontend patterns** — check how existing forms manage state (useState, context, etc.) and follow the same pattern. Don't introduce new state management libraries.

5. **Install recharts** — `cd frontend && npm install recharts` before implementing the dashboard.

6. **CORS is already handled** — all new backend endpoints are in the same FastAPI app.

7. **No candidate emails** — TalentBridge is a white-label platform. Companies control candidate communication. Do not add any email-to-candidate feature.

---

## Feature 4: Conversational Core Competency Probes (Feature-Flagged)

**Time estimate:** 1.5–2 days  
**Flag name:** `CONVERSATIONAL_PROBES`  
**Default:** `false` (existing behavior preserved)  
**Location:** Interview module frontend only (`interview-module/frontend/src/pages/Interview.jsx`) + one eval prompt tweak in `claude_client.py`

### Behavior

| Mode | CC question behavior | Next/Skip behavior |
|---|---|---|
| `CONVERSATIONAL_PROBES=false` | Existing: probe fires on next screen if signal weak | Existing: may show probe screen |
| `CONVERSATIONAL_PROBES=true` | Silence detection → probe fires inline, same screen | Always advances to next question or end — never shows probe screen |

### What stays the same (both modes)
- Non-CC questions: completely unchanged
- Next/Skip buttons: always present on every question
- Backend `probe-assess` endpoint: unchanged
- Probe generation and storage: unchanged

---

### Implementation

#### 1. Feature flag — `interview-module/frontend/src/config.js` (create if not exists)

```js
// Feature flags — set via .env or hardcode for demo
export const CONVERSATIONAL_PROBES = 
  import.meta.env.VITE_CONVERSATIONAL_PROBES === 'true';
```

Add to `interview-module/frontend/.env` (and `.env.example`):
```
VITE_CONVERSATIONAL_PROBES=false
```

---

#### 2. Silence detection — add to `Interview.jsx`

Add silence detection using Web Audio API's `AnalyserNode`. Wire it up only when `CONVERSATIONAL_PROBES=true` AND current question is a CC question.

```js
import { CONVERSATIONAL_PROBES } from '../config.js';

// Add these refs near other refs at top of component:
const analyserRef = useRef(null);
const silenceTimerRef = useRef(null);
const audioCtxRef = useRef(null);
const SILENCE_THRESHOLD = 10;      // RMS amplitude (0-255), tune if needed
const SILENCE_DURATION_MS = 1800;  // 1.8s of silence triggers probe check

// Call this after MediaRecorder starts recording (find where mediaRecorderRef.current.start() is called)
function startSilenceDetection(stream) {
  if (!CONVERSATIONAL_PROBES) return;
  const q = questions[questionIndex];
  if (!q?.is_core_competency) return;

  audioCtxRef.current = new AudioContext();
  const source = audioCtxRef.current.createMediaStreamSource(stream);
  const analyser = audioCtxRef.current.createAnalyser();
  analyser.fftSize = 512;
  source.connect(analyser);
  analyserRef.current = analyser;

  const dataArray = new Uint8Array(analyser.frequencyBinCount);

  const checkSilence = () => {
    if (!analyserRef.current) return;
    analyserRef.current.getByteTimeDomainData(dataArray);
    // Compute RMS
    const rms = Math.sqrt(
      dataArray.reduce((sum, v) => sum + (v - 128) ** 2, 0) / dataArray.length
    );

    if (rms < SILENCE_THRESHOLD) {
      if (!silenceTimerRef.current) {
        silenceTimerRef.current = setTimeout(() => {
          stopSilenceDetection();
          handleSilenceTrigger();  // defined below
        }, SILENCE_DURATION_MS);
      }
    } else {
      // Sound detected — reset silence timer
      if (silenceTimerRef.current) {
        clearTimeout(silenceTimerRef.current);
        silenceTimerRef.current = null;
      }
    }
    requestAnimationFrame(checkSilence);
  };

  requestAnimationFrame(checkSilence);
}

function stopSilenceDetection() {
  if (silenceTimerRef.current) {
    clearTimeout(silenceTimerRef.current);
    silenceTimerRef.current = null;
  }
  if (audioCtxRef.current) {
    audioCtxRef.current.close();
    audioCtxRef.current = null;
  }
  analyserRef.current = null;
}
```

Call `startSilenceDetection(stream)` right after `mediaRecorderRef.current.start()`.
Call `stopSilenceDetection()` in the recording stop handler and on cleanup/unmount.

---

#### 3. Silence trigger handler — `handleSilenceTrigger`

This fires when silence is detected mid-recording on a CC question. It stops recording, sends to Whisper, evaluates depth, and either fires a probe inline or does nothing (lets candidate continue).

```js
// Add these state/refs near probe state:
const conversationalProbeIndexRef = useRef(0);  // which probe we're on (0 or 1)
const conversationalSignalResolvedRef = useRef(false);  // true once signal is strong enough

async function handleSilenceTrigger() {
  if (!CONVERSATIONAL_PROBES) return;
  const q = questions[questionIndex];
  if (!q?.is_core_competency) return;
  if (conversationalSignalResolvedRef.current) return;  // already got signal, don't re-probe

  const probes = q.probe_questions || [];
  if (conversationalProbeIndexRef.current >= probes.length) return;  // out of probes

  // Stop current recording and transcribe
  // (mirror the existing stop-and-transcribe flow)
  stopRecording();  // stops MediaRecorder, triggers existing onstop → Whisper flow

  // Wait for transcript to be available (existing flow puts it in transcriptRef or similar)
  // Then assess depth:
  const currentAnswer = getCurrentTranscript();  // use whatever ref/state holds the running transcript

  try {
    const res = await axios.post(`${API}/api/interview/probe-assess`, {
      question: q.question,
      answer: currentAnswer,
      job_description: sessionData?.job_description || '',
      seniority_bar: sessionData?.seniority_bar || 'mid',
    });

    if (!res.data.needs_probing) {
      // Signal is strong — mark resolved, let candidate tap Next when ready
      conversationalSignalResolvedRef.current = true;
      // Optionally: brief TTS acknowledgement e.g. "Great answer, feel free to move on"
      return;
    }

    // Signal weak — fire next probe inline
    const probe = probes[conversationalProbeIndexRef.current];
    conversationalProbeIndexRef.current += 1;

    // Append probe to transcript with [PROBE_N] marker (same format as existing code)
    appendToTranscript(`[PROBE_${conversationalProbeIndexRef.current}: ${probe.question}]`);

    // Speak probe via TTS and restart recording
    await speakProbeQuestion(probe, questionIndex);  // existing function
    startRecording();  // restart recording for candidate's probe answer
    startSilenceDetection(currentStream);  // re-arm silence detection

  } catch (e) {
    console.error('[ConversationalProbe] assess failed', e);
    // On error: just restart recording, let candidate continue
    startRecording();
    startSilenceDetection(currentStream);
  }
}
```

---

#### 4. Reset conversational probe state on question advance

When moving to a new question, reset the conversational probe state:

```js
// In the function that advances to next question (find where questionIndex increments):
conversationalProbeIndexRef.current = 0;
conversationalSignalResolvedRef.current = false;
stopSilenceDetection();
```

---

#### 5. Bypass next-screen probe when flag is on — `Interview.jsx`

Find the existing Next button handler where it checks `is_core_competency` and decides whether to show a probe on the next screen. Wrap that block:

```js
// BEFORE (existing logic, simplified):
if (q.is_core_competency && q.probe_questions?.length && !signalResolved) {
  // show probe on next screen
  enterProbeMode(q.probe_questions);
  return;
}
advanceToNextQuestion();

// AFTER:
if (!CONVERSATIONAL_PROBES && q.is_core_competency && q.probe_questions?.length && !signalResolved) {
  // existing next-screen probe flow — only when flag is OFF
  enterProbeMode(q.probe_questions);
  return;
}
// Flag is ON, or not CC, or signal already resolved — just advance
advanceToNextQuestion();
```

---

#### 6. Eval prompt tweak — `claude_client.py`

In the `core_competency_guidelines` string (line ~487), add:

```python
core_competency_guidelines = """
For questions marked [CORE_COMPETENCY] in the transcript, also return a "core_competency_probes" 
array in that question's per_question entry: [{"question": "...", "candidate_answer": "...", 
"expected_answer": "...", "pass": true/false}]. Parse these from [PROBE_N: ...] markers in the 
transcript.

When CONVERSATIONAL_PROBES mode was used, the probe answers immediately follow each [PROBE_N] 
marker as the next spoken segment. Parse accordingly.

Do NOT assign a numeric overall_score to [CORE_COMPETENCY] questions — their evaluation is 
captured entirely in the core_competency_probes array. Exclude them from aggregate score 
calculation."""
```

Note: the eval prompt doesn't know which mode was used — it just parses what's in the transcript. The `[PROBE_N]` markers are written the same way in both modes, so this works without any flag-passing to the backend.

---

### Key implementation notes for the agent

1. **Find the exact recording start/stop functions** in `Interview.jsx` — the codebase uses `mediaRecorderRef`. Search for `mediaRecorderRef.current.start()` to find where to call `startSilenceDetection`.

2. **The running transcript** — look for how the current answer text is accumulated during recording (likely a `ref` updated by the Whisper response handler). Use that same ref in `handleSilenceTrigger` to get `currentAnswer`.

3. **`speakProbeQuestion` already exists** — it's defined in the current `Interview.jsx`. Reuse it exactly, don't rewrite it.

4. **`currentStream`** — the MediaStream from `getUserMedia` is likely stored in a ref already. Find it and pass it to `startSilenceDetection`.

5. **Silence threshold tuning** — `SILENCE_THRESHOLD = 10` is a starting point. In a quiet room it may be too sensitive; in a noisy room too loose. Make it an env var: `VITE_SILENCE_THRESHOLD=10`.

6. **Don't silence-detect during TTS playback** — when the system is speaking a probe, you don't want silence detection firing. Call `stopSilenceDetection()` before TTS starts, `startSilenceDetection()` after TTS ends and recording restarts.

7. **Max probes guard** — `probe_questions` has exactly 2 items (generated by Claude). `conversationalProbeIndexRef` naturally stops at 2. No extra guard needed beyond the length check.

8. **Run existing tests after** — `pytest tests/test_core_competency.py` — all 20 checks should still pass since flag defaults to false.

---

## Testing Strategy

### Existing test suite (must not break)

All existing tests use **real dev API keys** (Anthropic, OpenAI) and real services running locally. Run before and after every feature.

| File | What it covers |
|---|---|
| `tests/test_e2e_interview_flow.py` | Auth → create job → generate questions → run interview with macOS `say` → Whisper → Claude report → assert score gap ≥25pts |
| `tests/test_core_competency.py` | CC probe flow browser-driven: BlackHole loopback, shallow answer triggers probe, probe in transcript, report has core_competency_probes array (20 checks) |
| `tests/test_interview_buttons.py` | All button scenarios A–F: Next, Skip, End mid-probe, skip probe, re-entry regression |
| `tests/test_regression.py` | Trailing slash, question generation, mock interview launch, question bank, candidate application flow, interview launch |
| `tests/test_e2e_navigation.py` | Frontend navigation, route transitions |

**Run baseline before touching any code:**
```bash
python tests/test_regression.py
python tests/test_e2e_interview_flow.py
python tests/test_core_competency.py
python tests/test_interview_buttons.py
```
All must pass. If anything is already broken, fix it first.

---

### New tests to write

#### `tests/test_insights_dashboard.py` — Feature 1

```python
"""
E2E test for the Interview Insights Dashboard.

Tests (API, no browser):
  1. GET /jobs/{job_id}/insights returns 200 with correct structure
  2. Returns candidate_count=0 when no completed interviews
  3. cohort_summary has common_strengths, common_weaknesses, hiring_recommendation (Claude)
  4. candidates array sorted by overall_score descending
  5. PATCH /interviews/{interview_id}/status → 200, persists on re-fetch
  6. score_distribution buckets sum to candidate_count
  7. dimension_averages contains all expected dimensions

Tests (browser):
  8. "View Insights" button visible on JobDetail when interviews exist
  9. InsightsDashboard page loads at /jobs/:id/insights with charts
  10. Advance/Reject buttons update status without page reload

REQUIREMENTS: All 4 services running. 2+ completed interviews for test job.
Real Claude key required (cohort_summary calls Claude).
"""

# Key assertions:
assert r.status_code == 200
data = r.json()
assert "candidate_count" in data
assert "cohort_summary" in data
assert isinstance(data["cohort_summary"]["common_strengths"], list)
assert len(data["cohort_summary"]["hiring_recommendation"]) > 10
scores = [c["overall_score"] for c in data["candidates"]]
assert scores == sorted(scores, reverse=True), "Must be sorted descending"
assert sum(data["score_distribution"].values()) == data["candidate_count"]

# Status update:
r = requests.patch(f"{TB_API}/interviews/{iid}/status", json={"status": "advanced"})
assert r.status_code == 200
refetch = requests.get(f"{TB_API}/jobs/{job_id}/insights").json()
c = next(x for x in refetch["candidates"] if x["interview_id"] == iid)
assert c["recruiter_status"] == "advanced"
```

---

#### `tests/test_jd_generator.py` — Feature 2

```python
"""
E2E test for AI Job Description Generator.

Tests (API only, fast):
  1. POST /jobs/generate-description with valid prompt → 200 + description len > 200
  2. Description contains tech keywords from prompt
  3. Description has responsibilities + requirements sections
  4. Empty prompt → 422 validation error
  5. Response time < 30 seconds

Tests (browser):
  6. Generate button visible on job creation form
  7. Clicking Generate fills the description textarea

REQUIREMENTS: All 4 services running. Real Claude key.
"""

r = requests.post(f"{TB_API}/jobs/generate-description",
    json={"prompt": "Senior iOS Engineer, SwiftUI + on-device ML, 5+ years"})
assert r.status_code == 200
desc = r.json()["description"]
assert len(desc) > 200
assert "iOS" in desc or "Swift" in desc
assert any(s in desc for s in ["What You'll Do", "Responsibilities", "You will"])
assert any(s in desc for s in ["What We're Looking For", "Requirements", "You have"])

r_empty = requests.post(f"{TB_API}/jobs/generate-description", json={"prompt": ""})
assert r_empty.status_code == 422
```

---

#### `tests/test_candidate_experience.py` — Feature 3

```python
"""
Browser-driven E2E for candidate experience improvements.

Tests:
  1. Briefing page loads before interview (checklist, proctoring notice, Start button)
  2. Clicking Start transitions to interview UI
  3. Progress bar visible: shows "Question 1 of N", increases after Next
  4. ThankYou page has "Interview Complete", no email/feedback promise

REQUIREMENTS: playwright + chromium, BlackHole 2ch, all 4 services, valid session link.
"""

# Briefing page
page.goto(interview_url)
assert page.locator("text=Before you begin").is_visible(timeout=5000)
assert page.locator("text=quiet place").is_visible()
assert page.locator("text=Start Interview").is_visible()
assert not page.locator("[data-testid='question-text']").is_visible()

# Transition to interview
page.click("text=Start Interview")
page.wait_for_selector("[data-testid='question-text']", timeout=10000)
assert not page.locator("text=Before you begin").is_visible()

# Progress bar
assert page.locator("[data-testid='progress-bar']").is_visible()
assert "Question 1 of" in page.locator("[data-testid='progress-label']").inner_text()

# ThankYou — no email promise (white-label platform)
page.goto(thankyou_url)
assert page.locator("text=Interview Complete").is_visible()
assert not page.locator("text=email").is_visible()
```

---

#### `tests/test_conversational_probes.py` — Feature 4

```python
"""
E2E test for conversational CC probes (VITE_CONVERSATIONAL_PROBES feature flag).

FLAG=OFF tests (existing behavior — always run):
  1. probe-assess returns needs_probing=true for "I don't know"
  2. probe-assess returns needs_probing=false for detailed 3+ sentence answer
  3. probe-assess response time < 10 seconds
  4. Browser (flag=off): shallow answer on CC question → probe appears on NEXT screen

FLAG=ON tests (run with --flag-on, requires frontend restart with env var):
  5. Browser: Next on CC question ALWAYS advances — never shows probe screen
  6. Browser: after shallow answer + silence, transcript contains [PROBE_1] marker
  7. Browser: after thorough answer, no [PROBE_N] markers in transcript

REQUIREMENTS: All 4 services. BlackHole 2ch. CC-marked question in test job bank.
For flag-on tests: VITE_CONVERSATIONAL_PROBES=true in interview-module/frontend/.env
"""

# Backend probe-assess shallow
r = requests.post(f"{INTERVIEW_API}/api/interview/probe-assess", json={
    "question": "Explain ARC memory management in Swift",
    "answer": "I don't know.",
    "job_description": JOB_DESC,
    "seniority_bar": "senior"
})
assert r.status_code == 200
assert r.json()["needs_probing"] == True

# Backend probe-assess thorough
r = requests.post(f"{INTERVIEW_API}/api/interview/probe-assess", json={
    "question": "Explain ARC memory management in Swift",
    "answer": (
        "ARC automatically manages memory by tracking strong, weak, and unowned references. "
        "Strong references increment the retain count; weak and unowned prevent retain cycles. "
        "I use weak self in closures to avoid capturing self strongly, and Instruments' Leaks "
        "tool helps identify cycles in production code."
    ),
    "job_description": JOB_DESC,
    "seniority_bar": "senior"
})
assert r.json()["needs_probing"] == False

# FLAG=ON browser: Next must always advance, never show probe screen
page.click("[data-testid='btn-next']")
page.wait_for_timeout(1500)
assert not page.locator("[data-testid='probe-banner']").is_visible(), \
    "With CONVERSATIONAL_PROBES=true, Next must never trigger probe screen"
new_idx = int(page.locator("[data-testid='question-index']").inner_text())
assert new_idx > prev_idx
```

---

### data-testid hooks required (add to JSX when implementing)

The new tests reference these attributes — they must be added to the components:

| Attribute | Component | Element |
|---|---|---|
| `data-testid="progress-bar"` | `Interview.jsx` | Progress bar div |
| `data-testid="progress-label"` | `Interview.jsx` | "Question N of M" text span |
| `data-testid="probe-banner"` | `Interview.jsx` | Inline probe UI container |
| `data-testid="question-index"` | `Interview.jsx` | Current question index (can be hidden span) |
| `data-testid="btn-next"` | `Interview.jsx` | Next button (may already exist) |
| `data-testid="question-text"` | `Interview.jsx` | Question display text (may already exist) |

---

### General testing rules (do not deviate)

1. **No mocking Claude** — if Claude fails, the test fails. Use real API keys from `.env`.
2. **No XCTSkip / silent skips** — if a dependency is missing, print a clear error and `sys.exit(1)`.
3. **No canned data** — if Whisper transcription or a real step fails, the test must fail.
4. **Unique run IDs** — every test that creates jobs/users uses `_RUN_ID = uuid.uuid4().hex[:8]` as a suffix to avoid collisions.
5. **Clean up** — each test deletes the jobs/sessions it created. Check existing tests for the cleanup pattern (look for `DELETE /api/jobs/{id}`).
6. **Timeout values** — Claude Sonnet calls: up to 120s. Claude Haiku: up to 15s. Whisper: up to 30s.
