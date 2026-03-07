from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
from .. import models, schemas, auth
from ..database import get_db
from ..email_utils import send_screening_invite
import json, uuid, os, httpx

router = APIRouter(prefix="/api/screenings", tags=["Screenings"])

INTERVIEW_API_URL = os.getenv("INTERVIEW_API_URL", "http://localhost:8001")
INVITE_EXPIRY_HOURS = 48


# ── helpers ───────────────────────────────────────────────────────────────────

def _create_interview_session(
    job_description: str,
    resume_text: str,
    difficulty: int = 3,
    seniority_bar: str = "mid",
    time_limit: int = 45,
    num_questions: int = 8,
    job_id: Optional[int] = None,
    behavioral_pct: int = 20,
) -> Optional[str]:
    """Call interview module to create a session. Returns session_id or None."""
    try:
        payload = {
            "job_description": job_description,
            "resume_text": resume_text or "",
            "difficulty": difficulty,
            "seniority_bar": seniority_bar,
            "time_limit": time_limit,
            "num_questions": num_questions,
            "behavioral_pct": behavioral_pct,
        }
        if job_id:
            payload["job_id"] = job_id
        resp = httpx.post(
            f"{INTERVIEW_API_URL}/api/interview/session",
            json=payload,
            timeout=60.0,  # increased: behavioral TTS generation takes time
        )
        resp.raise_for_status()
        return resp.json()["session_id"]
    except Exception as e:
        print(f"[INTERVIEW MODULE] Failed to create session: {e}")
        return None


def _invalidate_pending_tokens(db: Session, application_id: int):
    """Invalidate any scheduled/unused invite tokens for this application."""
    db.query(models.Screening).filter(
        models.Screening.application_id == application_id,
        models.Screening.status == "scheduled",
        models.Screening.invite_used == False,
    ).update({"invite_used": True})
    db.commit()


def log_activity(db, user_id, action, entity_type=None, entity_id=None, details=None):
    db.add(models.ActivityLog(
        user_id=user_id, action=action,
        entity_type=entity_type, entity_id=entity_id, details=details
    ))
    db.commit()


# ── create / invite ───────────────────────────────────────────────────────────

@router.post("/", response_model=schemas.ScreeningResponse, status_code=status.HTTP_201_CREATED)
async def create_screening(
    screening_data: schemas.ScreeningCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Schedule a screening and send invite email to candidate."""
    application = db.query(models.Application).options(
        joinedload(models.Application.candidate),
        joinedload(models.Application.job),
    ).filter(models.Application.id == screening_data.application_id).first()

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    # Block if interview is actively in progress
    in_progress = db.query(models.Screening).filter(
        models.Screening.application_id == screening_data.application_id,
        models.Screening.status == "in_progress",
    ).first()
    if in_progress:
        raise HTTPException(status_code=400, detail="An interview is currently in progress for this candidate")

    # Resolve job now so we can check setup_status
    job = application.job

    # Block if job questions are still being generated
    if job.setup_status == "generating":
        raise HTTPException(
            status_code=400,
            detail="Interview questions for this job are still being generated. Please try again in a moment."
        )

    # Invalidate any pending (unused) tokens for this application
    _invalidate_pending_tokens(db, screening_data.application_id)

    # Create interview session in interview module
    job_desc = job.description or ""
    resume_text = application.candidate.resume_text or ""
    session_id = _create_interview_session(
        job_description=job_desc,
        resume_text=resume_text,
        difficulty=job.interview_difficulty or 3,
        seniority_bar=job.interview_seniority or "mid",
        time_limit=job.interview_time_limit or 45,
        num_questions=job.interview_num_questions or 8,
        job_id=job.id,
        behavioral_pct=job.interview_behavioral_pct or 20,
    )

    # Generate invite token
    invite_token = str(uuid.uuid4())
    now = datetime.utcnow()

    new_screening = models.Screening(
        application_id=screening_data.application_id,
        scheduled_at=screening_data.scheduled_at or now,
        status="scheduled",
        source="manual",
        interview_session_id=session_id,
        invite_token=invite_token,
        invite_sent_at=now,
        invite_expires_at=now + timedelta(hours=INVITE_EXPIRY_HOURS),
        invite_used=False,
    )
    db.add(new_screening)
    application.status = "screening"
    db.commit()
    db.refresh(new_screening)

    # Send invite email
    send_screening_invite(
        candidate_name=application.candidate.full_name,
        candidate_email=application.candidate.email,
        job_title=application.job.title,
        company_name=current_user.company_name or "TalentBridge",
        session_id=session_id or "pending",
        invite_token=invite_token,
        expires_hours=INVITE_EXPIRY_HOURS,
    )

    log_activity(db, current_user.id, "screening_invite_sent", "screening", new_screening.id)
    return new_screening


# ── token validation (called by interview module frontend) ────────────────────

@router.get("/validate-token/{token}")
async def validate_token(token: str, db: Session = Depends(get_db)):
    """Public endpoint — validate an invite token before starting interview."""
    screening = db.query(models.Screening).filter(
        models.Screening.invite_token == token
    ).first()

    if not screening:
        return {"valid": False, "reason": "Invalid link. Please contact the recruiter."}
    if screening.invite_used:
        return {"valid": False, "reason": "This interview link has already been used."}
    if screening.invite_expires_at and datetime.utcnow() > screening.invite_expires_at:
        return {"valid": False, "reason": "This interview link has expired. Please ask the recruiter for a new one."}
    if screening.status == "in_progress":
        return {"valid": False, "reason": "An interview session is already in progress."}

    return {
        "valid": True,
        "session_id": screening.interview_session_id,
        "screening_id": screening.id,
    }


# ── callback from interview module ────────────────────────────────────────────

@router.post("/complete-from-interview")
async def complete_from_interview(payload: dict, db: Session = Depends(get_db)):
    """
    Called by interview module when candidate completes their session.
    Writes real scores back to the Screening record.
    """
    session_id = payload.get("interview_session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="interview_session_id required")

    screening = db.query(models.Screening).filter(
        models.Screening.interview_session_id == session_id
    ).first()
    if not screening:
        raise HTTPException(status_code=404, detail="Screening not found for this session")

    # Extract scores from report
    overall = payload.get("overall_score", 0)
    per_q = payload.get("per_question", [])
    technical_score = (
        sum(q.get("score", 0) for q in per_q) / len(per_q)
        if per_q else overall
    )

    screening.status = "completed"
    screening.completed_at = datetime.utcnow()
    screening.overall_score = overall
    screening.technical_score = round(technical_score, 1)
    screening.communication_score = None   # not separately scored yet
    screening.cultural_fit_score = None
    screening.recommendation = "pass" if payload.get("pass") else "fail"
    screening.ai_evaluation = json.dumps({
        "summary": payload.get("summary"),
        "strengths": payload.get("strengths", []),
        "weaknesses": payload.get("weaknesses", []),
        "hiring_recommendation": payload.get("hiring_recommendation"),
        "per_question": per_q,
    })
    screening.invite_used = True

    # Update application status
    application = db.query(models.Application).filter(
        models.Application.id == screening.application_id
    ).first()
    if application:
        application.status = "shortlisted" if payload.get("pass") else "rejected"

    db.commit()
    return {"ok": True}


# ── mark in_progress when candidate starts ───────────────────────────────────

@router.post("/start-from-token/{token}")
async def start_from_token(token: str, db: Session = Depends(get_db)):
    """Called when candidate starts the interview. Marks screening in_progress."""
    screening = db.query(models.Screening).filter(
        models.Screening.invite_token == token
    ).first()
    if not screening:
        raise HTTPException(status_code=404, detail="Not found")
    screening.status = "in_progress"
    screening.started_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


# ── standard CRUD ─────────────────────────────────────────────────────────────

@router.get("/", response_model=List[schemas.ScreeningResponse])
async def get_screenings(
    status: Optional[str] = None,
    application_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.Screening)
    if status:
        query = query.filter(models.Screening.status == status)
    if application_id:
        query = query.filter(models.Screening.application_id == application_id)
    return query.order_by(models.Screening.scheduled_at.desc()).offset(skip).limit(limit).all()


@router.get("/stats")
async def get_screening_stats(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    total = db.query(models.Screening).count()
    scheduled = db.query(models.Screening).filter(models.Screening.status == "scheduled").count()
    in_progress = db.query(models.Screening).filter(models.Screening.status == "in_progress").count()
    completed = db.query(models.Screening).filter(models.Screening.status == "completed").count()
    cancelled = db.query(models.Screening).filter(models.Screening.status == "cancelled").count()
    avg_overall = db.query(func.avg(models.Screening.overall_score)).filter(
        models.Screening.overall_score.isnot(None)
    ).scalar() or 0
    return {
        "total": total, "scheduled": scheduled, "in_progress": in_progress,
        "completed": completed, "cancelled": cancelled,
        "average_overall_score": round(avg_overall, 1),
    }


@router.get("/{screening_id}", response_model=schemas.ScreeningResponse)
async def get_screening(
    screening_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    s = db.query(models.Screening).filter(models.Screening.id == screening_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Screening not found")
    return s


@router.post("/{screening_id}/cancel", response_model=schemas.ScreeningResponse)
async def cancel_screening(
    screening_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    s = db.query(models.Screening).filter(models.Screening.id == screening_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Screening not found")
    if s.status not in ["scheduled", "in_progress"]:
        raise HTTPException(status_code=400, detail="Screening cannot be cancelled")
    s.status = "cancelled"
    s.invite_used = True
    application = db.query(models.Application).filter(models.Application.id == s.application_id).first()
    if application and application.status == "screening":
        application.status = "pending"
    db.commit()
    db.refresh(s)
    log_activity(db, current_user.id, "screening_cancelled", "screening", s.id)
    return s


@router.put("/{screening_id}", response_model=schemas.ScreeningResponse)
async def update_screening(
    screening_id: int,
    screening_update: schemas.ScreeningUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    s = db.query(models.Screening).filter(models.Screening.id == screening_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Screening not found")
    for field, value in screening_update.model_dump(exclude_unset=True).items():
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    return s
