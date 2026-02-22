from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_
from typing import Optional
from .. import models
from ..database import get_db
from ..ai import extract_text_from_pdf, extract_text_from_docx, analyze_resume
import json

router = APIRouter(prefix="/api/public", tags=["Public"])


@router.get("/jobs")
async def list_public_jobs(
    search: Optional[str] = None,
    job_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """List active jobs — no authentication required"""
    query = db.query(models.Job).filter(models.Job.status == "active")

    if search:
        term = f"%{search}%"
        query = query.filter(
            or_(
                models.Job.title.ilike(term),
                models.Job.department.ilike(term),
                models.Job.location.ilike(term),
                models.Job.description.ilike(term),
            )
        )

    if job_type:
        query = query.filter(models.Job.job_type == job_type)

    query = query.order_by(models.Job.created_at.desc())
    jobs = query.offset(skip).limit(limit).all()

    return [
        {
            "id": job.id,
            "title": job.title,
            "department": job.department,
            "location": job.location,
            "job_type": job.job_type,
            "experience_level": job.experience_level,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "description": job.description,
            "skills_required": job.skills_required,
            "created_at": job.created_at,
            "deadline": job.deadline,
        }
        for job in jobs
    ]


@router.get("/jobs/{job_id}")
async def get_public_job(job_id: int, db: Session = Depends(get_db)):
    """Get a single active job — no authentication required"""
    job = db.query(models.Job).filter(
        models.Job.id == job_id,
        models.Job.status == "active"
    ).first()

    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return {
        "id": job.id,
        "title": job.title,
        "department": job.department,
        "location": job.location,
        "job_type": job.job_type,
        "experience_level": job.experience_level,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "description": job.description,
        "requirements": job.requirements,
        "responsibilities": job.responsibilities,
        "skills_required": job.skills_required,
        "benefits": job.benefits,
        "created_at": job.created_at,
        "deadline": job.deadline,
    }


@router.post("/apply", status_code=status.HTTP_201_CREATED)
async def public_apply(
    job_id: int = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    phone: Optional[str] = Form(None),
    cover_letter: Optional[str] = Form(None),
    resume: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Submit a job application — no authentication required"""
    # Validate job exists and is active
    job = db.query(models.Job).filter(
        models.Job.id == job_id,
        models.Job.status == "active"
    ).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # ── Parse resume in-memory (no file written to disk) ─────────────────────
    resume_text = None
    extracted = None

    if resume:
        allowed_types = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]
        if resume.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF and Word documents are allowed"
            )

        file_bytes = await resume.read()

        try:
            if resume.content_type == "application/pdf":
                resume_text = extract_text_from_pdf(file_bytes)
            else:
                resume_text = extract_text_from_docx(file_bytes)
        except Exception:
            resume_text = None  # parsing failed — continue without it

        if resume_text:
            try:
                extracted = analyze_resume(resume_text, job)
            except Exception:
                extracted = None  # Claude unavailable — fall back to random scorer

    # ── Find or create candidate ──────────────────────────────────────────────
    candidate = db.query(models.Candidate).filter(
        models.Candidate.email == email
    ).first()

    if not candidate:
        candidate = models.Candidate(
            email=email,
            full_name=full_name,
            phone=phone,
            source="public_apply",
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

    # Persist extracted profile fields (text + structured data, not the file)
    if extracted:
        candidate.resume_text = resume_text
        candidate.skills = json.dumps(extracted.get("skills", []))
        candidate.experience_years = extracted.get("experience_years")
        candidate.education = extracted.get("education")
        candidate.summary = extracted.get("summary")
        db.commit()

    # ── Guard against duplicate application ───────────────────────────────────
    existing = db.query(models.Application).filter(
        models.Application.job_id == job_id,
        models.Application.candidate_id == candidate.id
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You have already applied for this job"
        )

    # ── Build application — scores are null when no resume was provided ───────
    application = models.Application(
        job_id=job_id,
        candidate_id=candidate.id,
        cover_letter=cover_letter,
        status="pending",
        match_score=extracted["match_score"] if extracted else None,
        skills_match=extracted["skills_match"] if extracted else None,
        experience_match=extracted["experience_match"] if extracted else None,
        ai_summary=extracted["ai_summary"] if extracted else None,
        ai_recommendation=extracted["recommendation"] if extracted else None,
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    log_activity(db, None, "public_application_submitted", "application", application.id)

    return {
        "message": "Application submitted successfully. We'll be in touch!",
        "application_id": application.id,
    }


@router.get("/status")
async def check_application_status(
    email: str = Query(..., description="Email address used when applying"),
    db: Session = Depends(get_db)
):
    """Return all applications for a given email — no authentication required"""
    candidate = db.query(models.Candidate).filter(
        models.Candidate.email == email
    ).first()

    if not candidate:
        return []

    applications = (
        db.query(models.Application)
        .options(joinedload(models.Application.job))
        .filter(models.Application.candidate_id == candidate.id)
        .order_by(models.Application.applied_at.desc())
        .all()
    )

    return [
        {
            "id": app.id,
            "job_title": app.job.title if app.job else None,
            "job_department": app.job.department if app.job else None,
            "status": app.status,
            "applied_at": app.applied_at,
        }
        for app in applications
    ]


def log_activity(db: Session, user_id, action: str, entity_type: str = None, entity_id: int = None, details: str = None):
    """Log activity (user_id may be None for public actions)"""
    activity = models.ActivityLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
    )
    db.add(activity)
    db.commit()
