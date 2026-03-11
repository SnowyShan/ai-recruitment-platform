from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
import uuid, json, os, httpx, io, math, random, tempfile
from datetime import datetime
from .database import get_conn, AUDIO_DIR
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


# ── Questions (ad-hoc generation) ─────────────────────────────────────────────

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


# ── Question Bank ──────────────────────────────────────────────────────────────

question_bank_router = APIRouter(prefix="/api/interview", tags=["QuestionBank"])

@question_bank_router.get("/question-bank")
def search_question_bank(
    domain: str,
    difficulty: Optional[int] = None,
    limit: int = Query(30, le=100),
):
    """Search the shared question bank by domain and difficulty.
    Pass domain='all' (or omit a specific domain) to return questions
    across all domains — used by the create-job modal on open.
    """
    conn = get_conn()
    all_domains = (domain.lower() == "all")
    if all_domains:
        if difficulty:
            rows = conn.execute(
                "SELECT * FROM questions WHERE difficulty=? ORDER BY created_at DESC LIMIT ?",
                (difficulty, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM questions ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
    elif difficulty:
        rows = conn.execute(
            "SELECT * FROM questions WHERE domain=? AND difficulty=? ORDER BY created_at DESC LIMIT ?",
            (domain, difficulty, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM questions WHERE domain=? ORDER BY created_at DESC LIMIT ?",
            (domain, limit)
        ).fetchall()
    conn.close()
    return {"questions": [dict(r) for r in rows], "domain": domain}


# ── Job Setup ──────────────────────────────────────────────────────────────────

job_setup_router = APIRouter(prefix="/api/interview", tags=["JobSetup"])

class JobSetupRequest(BaseModel):
    job_title: str
    job_description: str
    domain: str
    difficulty: int = 3
    seniority: str = "mid"
    num_technical: int = 7
    selected_question_ids: list[str] = []  # Pre-selected from question bank

@job_setup_router.post("/job/{job_id}/setup", status_code=202)
def setup_job(job_id: int, req: JobSetupRequest, background_tasks: BackgroundTasks):
    """Trigger background generation of technical questions + audio for a job."""
    conn = get_conn()
    existing = conn.execute("SELECT job_id FROM job_setup WHERE job_id=?", (job_id,)).fetchone()
    now = datetime.utcnow().isoformat()
    if existing:
        conn.execute(
            "UPDATE job_setup SET domain=?, difficulty=?, seniority=?, num_technical=?, "
            "status='generating', progress_current=0, progress_total=?, question_ids='[]', updated_at=? "
            "WHERE job_id=?",
            (req.domain, req.difficulty, req.seniority, req.num_technical, req.num_technical, now, job_id)
        )
    else:
        conn.execute(
            "INSERT INTO job_setup (job_id, domain, difficulty, seniority, num_technical, num_behavioral, "
            "status, progress_current, progress_total, question_ids, created_at, updated_at) "
            "VALUES (?,?,?,?,?,0,'generating',0,?,?,?,?)",
            (job_id, req.domain, req.difficulty, req.seniority, req.num_technical, req.num_technical, '[]', now, now)
        )
    conn.commit()
    conn.close()

    background_tasks.add_task(_run_job_setup, job_id=job_id, req=req)
    return {"status": "generating", "job_id": job_id}


@job_setup_router.get("/job/{job_id}/setup/status")
def get_job_setup_status(job_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM job_setup WHERE job_id=?", (job_id,)).fetchone()
    conn.close()
    if not row:
        return {"status": "not_found", "job_id": job_id, "progress_current": 0, "progress_total": 0}
    return {
        "job_id": job_id,
        "status": row["status"],
        "progress_current": row["progress_current"],
        "progress_total": row["progress_total"],
        "domain": row["domain"],
    }


def _run_job_setup(job_id: int, req: JobSetupRequest):
    """Background task: generate technical questions + TTS audio for a job."""
    try:
        selected_ids = list(req.selected_question_ids)

        # How many more questions need to be generated?
        needed = max(0, req.num_technical - len(selected_ids))

        if needed > 0:
            generated = ai.generate_questions(
                resume_text="",  # technical questions are candidate-independent
                job_description=req.job_description,
                difficulty=req.difficulty,
                num_questions=needed,
                hardcoded=None,
            )

            for q in generated:
                q_id = str(uuid.uuid4())
                audio_filename = f"{q_id}.mp3"
                audio_path = os.path.join(AUDIO_DIR, audio_filename)

                tts_ok = ai.generate_and_store_tts(
                    q.get("voice_text") or q["question"],
                    audio_path,
                )

                conn = get_conn()
                conn.execute(
                    "INSERT OR IGNORE INTO questions (id, domain, difficulty, question, voice_text, topic, audio_path, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (q_id, req.domain, req.difficulty, q["question"], q.get("voice_text", ""),
                     q.get("topic", ""), audio_filename if tts_ok else None, datetime.utcnow().isoformat())
                )
                selected_ids.append(q_id)
                conn.execute(
                    "UPDATE job_setup SET progress_current=?, question_ids=?, updated_at=? WHERE job_id=?",
                    (len(selected_ids), json.dumps(selected_ids), datetime.utcnow().isoformat(), job_id)
                )
                conn.commit()
                conn.close()

        # Mark ready
        conn = get_conn()
        conn.execute(
            "UPDATE job_setup SET status='ready', progress_current=?, progress_total=?, question_ids=?, updated_at=? WHERE job_id=?",
            (len(selected_ids), len(selected_ids), json.dumps(selected_ids), datetime.utcnow().isoformat(), job_id)
        )
        conn.commit()
        conn.close()
        print(f"[JOB SETUP] Job {job_id} ready — {len(selected_ids)} technical questions")

    except Exception as e:
        print(f"[JOB SETUP] Job {job_id} failed: {e}")
        conn = get_conn()
        conn.execute("UPDATE job_setup SET status='failed', updated_at=? WHERE job_id=?",
                     (datetime.utcnow().isoformat(), job_id))
        conn.commit()
        conn.close()


# ── Evaluate ───────────────────────────────────────────────────────────────────

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


# ── Report ─────────────────────────────────────────────────────────────────────

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


# ── TTS (on-demand streaming — used as fallback) ───────────────────────────────

tts_router = APIRouter(prefix="/api/interview", tags=["TTS"])

class TTSRequest(BaseModel):
    text: str
    voice: str = "nova"

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


@tts_router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe audio via OpenAI Whisper-1. Used for iOS/mobile where
    Web Speech API recognition is unavailable (Chrome iOS, Safari iOS)."""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")
    content_type = file.content_type or "audio/webm"
    ext = "m4a" if ("mp4" in content_type or "m4a" in content_type) else "webm"
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    with tempfile.NamedTemporaryFile(suffix=f".{ext}", delete=False) as tmp:
        tmp.write(audio_bytes)
        tmp_path = tmp.name
    try:
        import time as _time
        for attempt in range(2):  # retry once on empty result
            with open(tmp_path, "rb") as f:
                result = client.audio.transcriptions.create(model="whisper-1", file=f)
            text = result.text or ""
            if text.strip() or attempt == 1:
                return {"text": text}
            _time.sleep(0.5)
        return {"text": ""}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        try: os.unlink(tmp_path)
        except: pass


# ── Sessions ───────────────────────────────────────────────────────────────────

session_router = APIRouter(prefix="/api/interview", tags=["Sessions"])

class SessionCreate(BaseModel):
    job_description: str
    resume_text: str
    difficulty: int = 3
    seniority_bar: str = "senior"
    time_limit: int = 45
    num_questions: int = 8
    hardcoded_questions: Optional[list[str]] = None
    # New fields for question-bank-aware session creation
    job_id: Optional[int] = None
    behavioral_pct: int = 20  # % of questions that are behavioral/resume-based
    verify_coding_ability: bool = False


@session_router.post("/session")
def create_session(req: SessionCreate):
    from fastapi import HTTPException as _HTTPException
    session_id = str(uuid.uuid4())

    if not req.job_id:
        raise _HTTPException(status_code=400, detail="job_id is required")

    conn = get_conn()
    setup = conn.execute("SELECT * FROM job_setup WHERE job_id=?", (req.job_id,)).fetchone()
    conn.close()

    if not setup or setup["status"] != "ready":
        status = setup["status"] if setup else "not_found"
        raise _HTTPException(
            status_code=409,
            detail=f"Job question setup is not ready (status: {status}). "
                   "Wait for setup to complete before starting a session."
        )

    question_ids = json.loads(setup["question_ids"] or "[]")
    num_behavioral = math.ceil(req.num_questions * req.behavioral_pct / 100)
    num_technical = req.num_questions - num_behavioral

    # Fetch technical questions from bank
    conn = get_conn()
    technical_qs = []
    for q_id in question_ids[:num_technical]:
        row = conn.execute("SELECT * FROM questions WHERE id=?", (q_id,)).fetchone()
        if row:
            q = dict(row)
            q["type"] = "technical"
            q["audio_url"] = f"/audio/{q['audio_path']}" if q.get("audio_path") else None
            technical_qs.append(q)
    conn.close()

    # Generate behavioral questions from resume
    behavioral_qs = ai.generate_behavioral_questions(
        req.resume_text, req.job_description, num_behavioral
    )

    # Generate TTS for behavioral questions (store per-session)
    for i, q in enumerate(behavioral_qs):
        audio_filename = f"{session_id}_b{i}.mp3"
        audio_path = os.path.join(AUDIO_DIR, audio_filename)
        tts_ok = ai.generate_and_store_tts(q.get("voice_text") or q["question"], audio_path)
        q["audio_url"] = f"/audio/{audio_filename}" if tts_ok else None
        q["type"] = "behavioral"

    # Shuffle technical, append behavioral at end
    random.shuffle(technical_qs)
    questions = technical_qs + behavioral_qs

    # Generate coding question if requested
    if req.verify_coding_ability:
        coding_q = ai.generate_coding_question(req.job_description)
        # Generate TTS for coding question
        coding_audio_filename = f"{session_id}_coding.mp3"
        coding_audio_path = os.path.join(AUDIO_DIR, coding_audio_filename)
        tts_ok = ai.generate_and_store_tts(coding_q.get("voice_text") or coding_q["question"], coding_audio_path)
        coding_q["audio_url"] = f"/audio/{coding_audio_filename}" if tts_ok else None
        questions.append(coding_q)

    conn = get_conn()
    conn.execute(
        "INSERT INTO sessions (id, job_description, resume_text, difficulty, seniority_bar, "
        "time_limit, questions, answers, status, verify_coding_ability, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (session_id, req.job_description, req.resume_text, req.difficulty, req.seniority_bar,
         req.time_limit, json.dumps(questions), "{}", "active", 1 if req.verify_coding_ability else 0,
         datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return {"session_id": session_id, "questions": questions, "time_limit": req.time_limit,
            "verify_coding_ability": req.verify_coding_ability}


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
        "verify_coding_ability": bool(row["verify_coding_ability"]) if "verify_coding_ability" in row.keys() else False,
        "draw_answers": json.loads(row["draw_answers"]) if "draw_answers" in row.keys() and row["draw_answers"] else None,
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
    code_answers: Optional[dict] = None  # {questionIndex: codeString}
    draw_answers: Optional[list] = None  # [base64PngString | null, ...]

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
    code_answers = req.code_answers or {}
    draw_answers = req.draw_answers or []
    report = ai.generate_report_from_transcript(
        row["job_description"], row["resume_text"], questions, full_transcript, evaluation_prompt,
        code_answers=code_answers,
        draw_answers=draw_answers,
    )

    # Enrich per_question with answer_char_count extracted from full_transcript.
    # Transcript format produced by Interview.jsx / test:
    #   "[Q1: <question text>]\n<answer>\n\n[Q2: ...]"
    import re as _re
    segments: dict[int, str] = {}
    # Match [Q<n>: ...] capturing everything between the bracket pairs
    parts = _re.split(r'\[Q(\d+):[^\]]*\]', full_transcript)
    # parts = ['', '1', '<answer1>', '2', '<answer2>', ...]
    it = iter(parts[1:])  # skip leading empty string before first marker
    for qnum_str, answer_text in zip(it, it):
        segments[int(qnum_str)] = answer_text.strip()

    for i, pq in enumerate(report.get("per_question", []), start=1):
        answer_text = segments.get(i, "")
        # Strip [SKIPPED] markers before counting
        clean = answer_text.replace("[SKIPPED]", "").strip()
        pq["answer_char_count"] = len(clean)
        # Attach code submission to per_question entry if present
        code_key = str(i - 1)  # code_answers is 0-indexed
        if code_key in code_answers and code_answers[code_key].strip():
            pq["code_submission"] = code_answers[code_key]
        # Attach draw submission (base64 PNG) if present
        draw_idx = i - 1
        if draw_idx < len(draw_answers) and draw_answers[draw_idx]:
            pq["draw_submission"] = draw_answers[draw_idx]

    conn.execute(
        "UPDATE sessions SET status='completed', report=?, draw_answers=?, completed_at=? WHERE id=?",
        (json.dumps(report), json.dumps(draw_answers) if draw_answers else None, datetime.utcnow().isoformat(), session_id)
    )
    conn.commit()
    conn.close()
    _notify_talentbridge(session_id, report)
    return report


# ── Test Data ──────────────────────────────────────────────────────────────────

import os, random as _random

testdata_router = APIRouter(prefix="/api/interview", tags=["TestData"])
TESTDATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "testData")

@testdata_router.get("/testdata")
def list_testdata():
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


# ── Settings ───────────────────────────────────────────────────────────────────

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
    conn.execute(
        "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        ("evaluation_prompt", req.evaluation_prompt, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return SettingsResponse(evaluation_prompt=req.evaluation_prompt)
