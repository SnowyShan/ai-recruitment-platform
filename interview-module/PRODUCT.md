# AI Interview Module — Product Requirements

> **Status:** MVC implemented. V2+ planned.
> **Last updated:** 2026-02-28

---

## Overview

A standalone AI-powered interview module that conducts structured technical and behavioral interviews with candidates via voice. Designed as a standalone microservice that integrates with TalentBridge but can be wired into any ATS.

---

## Core Design Philosophy

- **Evaluation quality cannot be compromised.** The system must reliably distinguish strong candidates from weak ones. Model and prompt choices for evaluation should prioritize accuracy over cost savings.
- **Consistency over creativity for questions.** Companies want to maintain the same hiring bar across candidates. Questions should be predictable and structured, not randomly generated each time.
- **Voice-first.** The primary input is voice. Text and drawing are additive signals, not replacements.
- **Costs should scale with usage.** Most compute is spent on evaluation (post-interview), not question serving. Question generation can be done offline or cached.

---

## Inputs

| Input | Format | Notes |
|---|---|---|
| Resume | PDF, DOCX, or plain text | Parsed server-side |
| Job Description | Plain text | Provided by recruiter or system |
| Domain | String (e.g., `ios`, `backend`, `data`) | Determines question bank |
| Difficulty | Integer 1–5 | 1=intern, 2=junior, 3=mid, 4=senior, 5=staff/principal |
| Seniority bar | Enum: junior/mid/senior/staff | Used as evaluation threshold |
| Time limit | Integer (minutes) | Session auto-terminates at limit |
| Hardcoded questions | Optional list of strings | Pinned questions that always appear |
| Hardcoded acceptable answers | Optional map question→answer | For factual questions with known correct answers |
| Number of questions | Integer | How many questions to include in session |

---

## Outputs

| Output | Format | Notes |
|---|---|---|
| Interview session | JSON | Questions, answers, timestamps, per-answer scores |
| Evaluation report | JSON + human-readable | Per-question scores, overall pass/fail, strengths, weaknesses, recommendation |
| Transcript | Text | Full candidate speech-to-text |

---

## Question Architecture

### Two question types

**1. Hardcoded (domain questions)**
- Authored once, stored in the question bank
- Consistent across all candidates for a role
- Example: *"What is the difference between struct and class in Swift?"*
- Have an optional known-good answer for strict evaluation
- Maintains hiring bar consistency

**2. Behavioral / resume-derived**
- Generated from the candidate's resume at session start (one Claude/Haiku call)
- Anchored to specific projects, roles, or experiences in the resume
- Example: *"You mentioned leading a team of 4 at Acme Corp — tell me about a time that team disagreed on a technical direction. How did you handle it?"*
- Small in number (2–4 per session)

### Question bank
- Questions are owned by the company (tenant)
- Stored in DB, editable by recruiters
- Recruiter selects questions per job posting from the company's bank
- New questions added by a recruiter are saved to the bank for reuse
- Questions have: category, subcategory, domain, difficulty, expected answer points, active flag

---

## Interview Session Flow

```
1. Session created
   → Resume + JD + config provided
   → Behavioral questions generated from resume (1 Claude/Haiku call)
   → Hardcoded questions fetched from bank
   → Full question list assembled and stored

2. Candidate receives interview link (via email, from TalentBridge)

3. Interview begins
   → Questions shown one at a time
   → Candidate responds via voice
   → STT transcribes response in real time
   → [V2+] System reads question aloud via TTS

4. Per-question flow
   → Candidate speaks answer
   → Stops recording (or auto-detected pause)
   → [V3+] Follow-up if answer is unclear
   → Next question

5. Session ends (all questions answered OR time limit reached)
   → Full transcript assembled

6. Evaluation (single Claude/Sonnet call)
   → Full transcript + question set + rubric → structured report
   → Report stored, linked to session

7. Report available to recruiter via TalentBridge
```

---

## Recruiter Configuration

Per job posting, a recruiter can configure:

```json
{
  "domain": "ios",
  "question_ids": [12, 47, 83],
  "behavioral_question_count": 3,
  "difficulty": 4,
  "seniority_bar": "senior",
  "time_limit_minutes": 45,
  "auto_invite_on_match": true,
  "auto_invite_threshold": 75
}
```

- Questions are selected from the company's bank
- New questions can be authored inline and saved to the bank
- Auto-invite sends the interview link when resume match score exceeds threshold

---

## AI Model Strategy

| Task | Model | Rationale |
|---|---|---|
| Resume match scoring | Local embeddings (sentence-transformers) | No API cost, fast, sufficient for ranking |
| Behavioral question generation (session start) | claude-haiku-3-5 | Structured output, low stakes |
| Per-answer evaluation (MVC only, to be replaced) | claude-haiku-3-5 | Temporary; batched report preferred |
| Full transcript evaluation + report | claude-sonnet-4-5 | Quality matters here; sonnet is the right balance |
| TTS (V2) | Browser SpeechSynthesis → ElevenLabs (V3+) | Progressive enhancement |
| STT (MVC) | Web Speech API | Browser-native, no cost, Chrome only |
| STT (V2+) | OpenAI Whisper | Cross-browser, server-side, storable transcript |

**Key principle:** Evaluate once, at the end. Do not call Claude after every answer in production — batch the full transcript into one evaluation call. Cheaper and produces better holistic judgment.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite (standalone) |
| Backend | FastAPI (standalone microservice) |
| Database | SQLite (MVC) → PostgreSQL (production) |
| AI | Anthropic Claude API |
| STT | Web Speech API (MVC) → OpenAI Whisper |
| TTS | Browser SpeechSynthesis (V2) → ElevenLabs (V3+) |
| Drawing | Excalidraw (V4) |
| Video | WebRTC (V5) |

---

## Implementation Phases

### MVC — Minimum Viable Core ✅ (implemented)

- [x] **Task 1:** Question generation from resume + JD (difficulty slider + hardcoded override)
- [x] **Task 2:** Answer evaluation with configurable seniority bar + hardcoded answer override
- [x] **Task 3:** Show questions on screen one by one, accept voice input (Web Speech API)
- [x] **Task 4:** Auto-terminate on completion or timeout
- [x] **Task 5:** Generate detailed report, pass/fail score, log result

**Known MVC limitations to address before production:**
- Per-answer Claude calls should be replaced with single end-of-session evaluation
- Web Speech API is Chrome-only and does not store server-side transcripts
- Questions are generated dynamically each session (should be fetched from question bank)
- Model choice: opus used for question gen and report (should be downgraded to sonnet/haiku)

### V2 — Voice Out

- [ ] **Task 6:** System reads questions aloud (TTS) — browser SpeechSynthesis first, then ElevenLabs
- [ ] **Task 7:** Replace Web Speech API with server-side Whisper for STT (cross-browser + stored transcripts)

### V3 — Natural Conversation

- [ ] **Task 8:** Natural, conversational tone — small talk at start, human pacing between questions
- [ ] **Task 9:** Follow-up questions when answer is too short, off-topic, or unclear (max 1 follow-up per question)

### V4 — Multimodal Input

- [ ] **Task 10:** Excalidraw-style drawing canvas for system design questions
- [ ] **Task 11:** Text editor input alongside voice (for code snippets, structured lists)
- [ ] Drawing + transcript included together in the evaluation context

### V5 — Video + Signals

- [ ] **Task 12:** Video feed capture via WebRTC
- [ ] **Task 13:** Tone of voice analysis as supplementary signal (not primary hiring signal)
- [ ] **Task 14:** Basic proctoring — detect tab switching, multiple faces, unusual audio
- [ ] Note: Video body language is low signal value; proctoring is the primary use case

### Stretch

- [ ] **Task 15:** AI video avatar as the interviewer (HeyGen or similar)

---

## Data Model (Interview Module)

```
Session
  ├── id (UUID)
  ├── job_description
  ├── resume_text
  ├── domain
  ├── difficulty (1-5)
  ├── seniority_bar
  ├── time_limit
  ├── status (active | completed | timed_out)
  ├── questions (JSON array)
  ├── answers (JSON map, index → answer + evaluation)
  ├── transcript (full text, V2+)
  ├── report (JSON, generated at completion)
  ├── created_at
  └── completed_at

Question (bank)
  ├── id
  ├── company_id (tenant)
  ├── domain
  ├── category (technical | behavioral | situational)
  ├── question (text)
  ├── expected_answer_points (JSON)
  ├── hardcoded_acceptable_answer (optional)
  ├── difficulty (1-5)
  ├── is_active
  └── created_by (recruiter)

JobQuestionSet
  ├── job_id
  └── question_ids (selected subset from bank)
```

---

## Out of Scope (for interview module itself)

- Candidate authentication (handled by TalentBridge or invite link token)
- Email delivery (handled by TalentBridge)
- Resume match scoring (handled by TalentBridge main backend)
- Recruiter dashboard and report viewer (handled by TalentBridge frontend)
- Webhook ingestion from external job boards (handled by TalentBridge)

---

## Open Questions

1. **Evaluation batching rollout** — When do we switch from per-answer to end-of-session evaluation? Answer: before any real candidate uses the system.
2. **Whisper hosting** — Self-hosted (faster, free after infra) or OpenAI API (pay-per-use, simpler)?
3. **Interview link token** — How is a candidate authenticated to a specific session? Proposal: time-limited signed token in the invite email URL.
4. **Follow-up question depth (V3)** — Max 1 follow-up per question to avoid interrogation feel.
