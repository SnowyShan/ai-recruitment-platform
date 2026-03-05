from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import uuid, json, os, httpx, io
from datetime import datetime
from .database import get_conn
from . import claude_client as ai
from openai import OpenAI

TALENTBRIDGE_API_URL = os.getenv("TALENTBRIDGE_API_URL", "http://localhost:8000")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")


def _notify_talentbridge(session_id: str, report: dict):
    """Post interview results back to TalentBridge."""
    try:
        httpx.post(
            f"{TALENTBRIDGE_API_URL}/api/screenings/complete-from-interview",
            json={"interview_session_id": session_id, **report},
            timeout=10.0,
        )
    except Exception as e:
        print(f"[TALENTBRIDGE CALLBACK] Failed: {e}")

# ── Questions ──────────────────────────────────────────────────

questions_router = APIRouter(prefix="/api/interview", tags=["Questions"])

class QuestionsRequest(BaseModel):
    resume_text: str
    job_description: str
    difficulty: int = 3
    num_questions: int = 8
    hardcoded_questions: Optional[list[str]] = None

@questions_router.post("/questions")
def generate_questions(req: QuestionsRequest):
    questions = ai.generate_questions(req.resume_text, req.job_description, req.difficulty, req.num_questions, req.hardcoded_questions)
    return {"questions": questions}

# ── Evaluate ───────────────────────────────────────────────────

evaluate_router = APIRouter(prefix="/api/interview", tags=["Evaluate"])

class EvaluateRequest(BaseModel):
    question: str
    candidate_answer: str
    job_description: str
    seniority_bar: str = "senior"
    hardcoded_acceptable_answer: Optional[str] = None

@evaluate_router.post("/evaluate")
def evaluate_answer(req: EvaluateRequest):
    result = ai.evaluate_answer(req.question, req.candidate_answer, req.job_description, req.seniority_bar, req.hardcoded_acceptable_answer)
    return result

# ── Report ─────────────────────────────────────────────────────

report_router = APIRouter(prefix="/api/interview", tags=["Report"])

class QAPair(BaseModel):
    question: str
    answer: str
    score: int
    feedback: str

class ReportRequest(BaseModel):
    job_description: str
    resume_text: str
    qa_pairs: list[QAPair]

@report_router.post("/report")
def generate_report(req: ReportRequest):
    pairs = [p.model_dump() for p in req.qa_pairs]
    report = ai.generate_report(req.job_description, req.resume_text, pairs)
    return report

# ── TTS ────────────────────────────────────────────────────────

tts_router = APIRouter(prefix="/api/interview", tags=["TTS"])

class TTSRequest(BaseModel):
    text: str
    voice: str = "nova"  # nova sounds natural and professional

@tts_router.post("/tts")
def synthesize_speech(req: TTSRequest):
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="TTS not configured")
    if not req.text.strip():
        raise HTTPException(status_code=400, detail="No text provided")
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.audio.speech.create(
        model="tts-1",
        voice=req.voice,
        input=req.text.strip(),
    )
    audio_bytes = response.read()
    return StreamingResponse(io.BytesIO(audio_bytes), media_type="audio/mpeg")


# ── Sessions ───────────────────────────────────────────────────

session_router = APIRouter(prefix="/api/interview", tags=["Sessions"])

class SessionCreate(BaseModel):
    job_description: str
    resume_text: str
    difficulty: int = 3
    seniority_bar: str = "senior"
    time_limit: int = 45
    num_questions: int = 8
    hardcoded_questions: Optional[list[str]] = None

@session_router.post("/session")
def create_session(req: SessionCreate):
    session_id = str(uuid.uuid4())
    questions = ai.generate_questions(req.resume_text, req.job_description, req.difficulty, req.num_questions, req.hardcoded_questions)
    conn = get_conn()
    conn.execute("""INSERT INTO sessions (id, job_description, resume_text, difficulty, seniority_bar, time_limit, questions, answers, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', ?)""",
        (session_id, req.job_description, req.resume_text, req.difficulty, req.seniority_bar, req.time_limit, json.dumps(questions), "{}", datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return {"session_id": session_id, "questions": questions, "time_limit": req.time_limit}

@session_router.get("/session/{session_id}")
def get_session(session_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": row["id"],
        "status": row["status"],
        "questions": json.loads(row["questions"]),
        "answers": json.loads(row["answers"]),
        "time_limit": row["time_limit"],
        "seniority_bar": row["seniority_bar"],
        "report": json.loads(row["report"]) if row["report"] else None,
    }

class AnswerSubmit(BaseModel):
    question_index: int
    answer: str

@session_router.post("/session/{session_id}/answer")
def submit_answer(session_id: str, req: AnswerSubmit):
    conn = get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    questions = json.loads(row["questions"])
    answers = json.loads(row["answers"])
    q = questions[req.question_index]
    evaluation = ai.evaluate_answer(q["question"], req.answer, row["job_description"], row["seniority_bar"], None)
    answers[str(req.question_index)] = {"answer": req.answer, **evaluation}
    conn.execute("UPDATE sessions SET answers = ? WHERE id = ?", (json.dumps(answers), session_id))
    conn.commit()
    conn.close()
    return {"question_index": req.question_index, "evaluation": evaluation}

class CompleteRequest(BaseModel):
    full_transcript: Optional[str] = None
    questions: Optional[list] = None

@session_router.post("/session/{session_id}/complete")
def complete_session(session_id: str, req: CompleteRequest = CompleteRequest()):
    conn = get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    questions = req.questions or json.loads(row["questions"])
    full_transcript = req.full_transcript or ""
    settings_row = conn.execute("SELECT value FROM settings WHERE key = 'evaluation_prompt'").fetchone()
    evaluation_prompt = settings_row["value"] if settings_row else ""
    report = ai.generate_report_from_transcript(row["job_description"], row["resume_text"], questions, full_transcript, evaluation_prompt)
    conn.execute("UPDATE sessions SET status = 'completed', report = ?, completed_at = ? WHERE id = ?",
        (json.dumps(report), datetime.utcnow().isoformat(), session_id))
    conn.commit()
    conn.close()
    # Notify TalentBridge
    _notify_talentbridge(session_id, report)
    return report

# ── Test Data ──────────────────────────────────────────────────

import os, random

testdata_router = APIRouter(prefix="/api/interview", tags=["TestData"])

TESTDATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "testData")

@testdata_router.get("/testdata")
def list_testdata():
    """List available test data folders."""
    base = os.path.abspath(TESTDATA_DIR)
    folders = sorted([f for f in os.listdir(base) if os.path.isdir(os.path.join(base, f))])
    return {"folders": folders}

@testdata_router.get("/testdata/{folder}")
def get_testdata(folder: str):
    base = os.path.abspath(TESTDATA_DIR)
    folder_path = os.path.join(base, folder)
    if not os.path.isdir(folder_path):
        raise HTTPException(status_code=404, detail=f"Test data folder '{folder}' not found")
    jd_path = os.path.join(folder_path, "jd.txt")
    resume_path = os.path.join(folder_path, "resume.txt")
    if not os.path.exists(jd_path) or not os.path.exists(resume_path):
        raise HTTPException(status_code=404, detail=f"Missing jd.txt or resume.txt in {folder}")
    return {
        "folder": folder,
        "job_description": open(jd_path).read(),
        "resume": open(resume_path).read(),
    }


# ── Settings ───────────────────────────────────────────────────

settings_router = APIRouter(prefix="/api/interview", tags=["Settings"])

class SettingsResponse(BaseModel):
    evaluation_prompt: str

class SettingsUpdate(BaseModel):
    evaluation_prompt: str

@settings_router.get("/settings")
def get_settings():
    conn = get_conn()
    row = conn.execute("SELECT value FROM settings WHERE key = 'evaluation_prompt'").fetchone()
    conn.close()
    return SettingsResponse(evaluation_prompt=row["value"] if row else "")

@settings_router.put("/settings")
def update_settings(req: SettingsUpdate):
    conn = get_conn()
    conn.execute("""INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
        ("evaluation_prompt", req.evaluation_prompt, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return SettingsResponse(evaluation_prompt=req.evaluation_prompt)
