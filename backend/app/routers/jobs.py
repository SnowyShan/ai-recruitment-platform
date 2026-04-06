from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional
from .. import models, schemas, auth
from ..database import get_db
import json, os, httpx

INTERVIEW_API_URL = os.getenv("INTERVIEW_API_URL", "http://localhost:8001")

_SCREENING_CONFIG_FIELDS = {
    "interview_time_limit", "interview_num_questions",
    "interview_difficulty", "interview_seniority", "interview_behavioral_pct",
}

_DOMAIN_KEYWORDS = {
    'ios':       ['ios', 'swift', 'objective-c', 'xcode', 'uikit', 'swiftui', 'apple'],
    'android':   ['android', 'kotlin'],
    'backend':   ['backend', 'back-end', 'python', 'django', 'fastapi', 'node.js', 'golang', 'rust', 'api developer', 'server-side'],
    'frontend':  ['frontend', 'front-end', 'react', 'vue', 'angular', 'typescript developer', 'ui engineer'],
    'fullstack': ['full stack', 'fullstack', 'full-stack'],
    'data':      ['data scientist', 'machine learning', 'ml engineer', 'ai engineer', 'data engineer'],
    'devops':    ['devops', 'site reliability', 'sre ', 'kubernetes', 'docker', 'cloud engineer', 'platform engineer'],
    'mobile':    ['mobile developer', 'react native', 'flutter'],
    'security':  ['security engineer', 'cybersecurity', 'appsec', 'infosec'],
}

def _infer_domain(job_title: str) -> str:
    t = job_title.lower()
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return domain
    return 'general'


def _trigger_job_setup(job: models.Job, selected_question_ids: list = None):
    """Call interview module to (re)generate technical questions + audio for a job."""
    num_q = job.interview_num_questions or 8
    behavioral_pct = job.interview_behavioral_pct or 20
    num_behavioral = max(1, round(num_q * behavioral_pct / 100))
    num_technical = num_q - num_behavioral

    try:
        httpx.post(
            f"{INTERVIEW_API_URL}/api/interview/job/{job.id}/setup",
            json={
                "job_title": job.title,
                "job_description": job.description or job.title,
                "domain": job.domain or "general",
                "difficulty": job.interview_difficulty or 3,
                "seniority": job.interview_seniority or "mid",
                "num_technical": max(1, num_technical),
                "selected_question_ids": selected_question_ids or [],
            },
            timeout=5.0,
        )
    except Exception as e:
        print(f"[JOB SETUP] Failed to trigger setup for job {job.id}: {e}")

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post("", response_model=schemas.JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: schemas.JobCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new job posting and trigger background question setup."""
    # Pop fields that aren't on the Job model
    data = job_data.model_dump()
    selected_question_ids = data.pop("selected_question_ids", []) or []

    # Infer domain from job title
    domain = _infer_domain(data.get("title", ""))

    new_job = models.Job(
        **data,
        domain=domain,
        setup_status="generating",
        created_by=current_user.id,
        status="draft",
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    # Trigger background question + audio generation
    _trigger_job_setup(new_job, selected_question_ids)

    log_activity(db, current_user.id, "job_created", "job", new_job.id, json.dumps({"title": new_job.title}))
    return new_job


@router.get("", response_model=List[schemas.JobResponse])
async def get_jobs(
    status: Optional[str] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get all jobs with optional filtering"""
    query = db.query(models.Job)
    
    # Filter by status
    if status:
        query = query.filter(models.Job.status == status)
    
    # Search in title, description, department
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                models.Job.title.ilike(search_term),
                models.Job.description.ilike(search_term),
                models.Job.department.ilike(search_term),
                models.Job.location.ilike(search_term)
            )
        )
    
    # Order by created_at descending
    query = query.order_by(models.Job.created_at.desc())
    
    jobs = query.offset(skip).limit(limit).all()
    
    # Add applications count to each job
    for job in jobs:
        job.applications_count = db.query(models.Application).filter(
            models.Application.job_id == job.id
        ).count()
    
    return jobs


@router.get("/stats")
async def get_job_stats(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get job statistics"""
    total_jobs = db.query(models.Job).count()
    active_jobs = db.query(models.Job).filter(models.Job.status == "active").count()
    draft_jobs = db.query(models.Job).filter(models.Job.status == "draft").count()
    closed_jobs = db.query(models.Job).filter(models.Job.status == "closed").count()
    
    return {
        "total_jobs": total_jobs,
        "active_jobs": active_jobs,
        "draft_jobs": draft_jobs,
        "closed_jobs": closed_jobs
    }


@router.get("/{job_id}/pipeline")
async def get_job_pipeline(
    job_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get pipeline funnel data for a specific job"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    applications = db.query(models.Application).filter(models.Application.job_id == job_id)
    total = applications.count()

    avg_score = db.query(func.avg(models.Application.match_score)).filter(
        models.Application.job_id == job_id,
        models.Application.match_score.isnot(None)
    ).scalar() or 0

    counts = {}
    for row in (
        db.query(models.Application.status, func.count(models.Application.id))
        .filter(models.Application.job_id == job_id)
        .group_by(models.Application.status)
        .all()
    ):
        counts[row[0]] = row[1]

    return {
        "total": total,
        "avg_match_score": round(avg_score, 1),
        "funnel": [
            {"stage": "applied",     "count": total},
            {"stage": "screening",   "count": counts.get("screening", 0)},
            {"stage": "shortlisted", "count": counts.get("shortlisted", 0)},
            {"stage": "rejected",    "count": counts.get("rejected", 0)},
        ]
    }


@router.get("/{job_id}", response_model=schemas.JobResponse)
async def get_job(
    job_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific job by ID"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    job.applications_count = db.query(models.Application).filter(
        models.Application.job_id == job.id
    ).count()
    
    return job


@router.put("/{job_id}", response_model=schemas.JobResponse)
async def update_job(
    job_id: int,
    job_update: schemas.JobUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Update a job posting"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    update_data = job_update.model_dump(exclude_unset=True)
    selected_question_ids = update_data.pop("selected_question_ids", None)

    # Detect if any screening config field changed — triggers re-setup
    screening_config_changed = bool(_SCREENING_CONFIG_FIELDS & set(update_data.keys()))

    for field, value in update_data.items():
        setattr(job, field, value)

    if screening_config_changed:
        job.setup_status = "generating"

    db.commit()
    db.refresh(job)

    if screening_config_changed:
        _trigger_job_setup(job, selected_question_ids or [])

    log_activity(db, current_user.id, "job_updated", "job", job.id)
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a job posting"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    # Delete associated applications first
    db.query(models.Application).filter(models.Application.job_id == job_id).delete()
    
    db.delete(job)
    db.commit()
    
    # Log activity
    log_activity(db, current_user.id, "job_deleted", "job", job_id)
    
    return None


@router.post("/{job_id}/publish", response_model=schemas.JobResponse)
async def publish_job(
    job_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Publish a draft job — blocked while interview questions are still generating."""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Auto-trigger setup for old jobs that were never set up
    if job.setup_status is None:
        job.setup_status = "generating"
        job.domain = job.domain or _infer_domain(job.title)
        db.commit()
        _trigger_job_setup(job, [])
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Interview questions are being set up for this job. Please wait a moment and try again."
        )

    if job.setup_status == "generating":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot publish: interview questions are still being generated. Please wait."
        )

    # Sync setup status from interview module before allowing publish
    if job.setup_status != "ready":
        try:
            resp = httpx.get(f"{INTERVIEW_API_URL}/api/interview/job/{job_id}/setup/status", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "ready":
                    job.setup_status = "ready"
                    db.commit()
                elif data.get("status") == "generating":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Cannot publish: interview questions are still being generated."
                    )
        except HTTPException:
            raise
        except Exception:
            pass  # If interview module unreachable, allow publish anyway

    job.status = "active"
    db.commit()
    db.refresh(job)
    log_activity(db, current_user.id, "job_published", "job", job.id)
    return job


@router.get("/{job_id}/setup-status")
async def get_setup_status(
    job_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Poll interview question setup progress for a job."""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Fetch live progress from interview module
    try:
        resp = httpx.get(f"{INTERVIEW_API_URL}/api/interview/job/{job_id}/setup/status", timeout=3.0)
        if resp.status_code == 200:
            data = resp.json()
            im_status = data.get("status")
            # Sync to TalentBridge DB if status changed
            if im_status in ("ready", "failed") and job.setup_status != im_status:
                job.setup_status = im_status
                db.commit()
            return {
                "job_id": job_id,
                "setup_status": im_status,
                "progress_current": data.get("progress_current", 0),
                "progress_total": data.get("progress_total", 0),
                "domain": data.get("domain"),
            }
    except Exception:
        pass

    return {
        "job_id": job_id,
        "setup_status": job.setup_status,
        "progress_current": 0,
        "progress_total": 0,
        "domain": job.domain,
    }


@router.post("/{job_id}/close", response_model=schemas.JobResponse)
async def close_job(
    job_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Close an active job"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    job.status = "closed"
    db.commit()
    db.refresh(job)
    
    # Log activity
    log_activity(db, current_user.id, "job_closed", "job", job.id)
    
    return job


def log_activity(db: Session, user_id: int, action: str, entity_type: str = None, entity_id: int = None, details: str = None):
    """Helper function to log activity"""
    activity = models.ActivityLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details
    )
    db.add(activity)
    db.commit()
