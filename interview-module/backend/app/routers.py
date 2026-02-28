from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid, json
from datetime import datetime
from .database import get_conn
from . import claude_client as ai

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

@session_router.post("/session/{session_id}/complete")
def complete_session(session_id: str):
    conn = get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Session not found")
    questions = json.loads(row["questions"])
    answers = json.loads(row["answers"])
    qa_pairs = []
    for i, q in enumerate(questions):
        ans = answers.get(str(i), {})
        qa_pairs.append({
            "question": q["question"],
            "answer": ans.get("answer", "(no answer)"),
            "score": ans.get("score", 0),
            "feedback": ans.get("feedback", "Not answered"),
        })
    report = ai.generate_report(row["job_description"], row["resume_text"], qa_pairs)
    conn.execute("UPDATE sessions SET status = 'completed', report = ?, completed_at = ? WHERE id = ?",
        (json.dumps(report), datetime.utcnow().isoformat(), session_id))
    conn.commit()
    conn.close()
    return report
