from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional
from .. import models, schemas, auth
from ..database import get_db
import json, os, httpx
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

INTERVIEW_API_URL = os.getenv("INTERVIEW_API_URL", "http://localhost:8001")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

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


def _trigger_job_setup(job: models.Job, selected_question_ids: list = None, generate_video: bool = False):
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
                "generate_video": generate_video,
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
    generate_video = data.get("video_interview_enabled", False)

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

    # Trigger background question + audio (+ optionally video) generation
    _trigger_job_setup(new_job, selected_question_ids, generate_video=generate_video)

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
                "video_interview_enabled": data.get("video_interview_enabled", False),
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


@router.post("/generate-description")
async def generate_job_description(request: dict):
    """
    Takes a short recruiter prompt and returns a full professional job description.
    """
    prompt_text = request.get("prompt", "")
    if not prompt_text or not prompt_text.strip():
        raise HTTPException(status_code=422, detail="prompt is required")

    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-key-here":
        raise HTTPException(status_code=500, detail="Anthropic API key not configured")

    claude_prompt = f"""You are an expert technical recruiter. Generate a professional job description based on this brief:

"{prompt_text}"

Return a JSON object with exactly these three keys:
{{
  "description": "A 2-3 paragraph role overview covering what the team does, what the candidate will work on, and why it's exciting. No bullet points here.",
  "requirements": "A plain list of 5-7 required qualifications, one per line, starting with a dash. Include years of experience, must-have skills, and domain knowledge. No markdown headers.",
  "skills": "A comma-separated list of 6-10 specific technical skills and tools (e.g. Swift, SwiftUI, Core Data, REST APIs, Git). Just the skill names, comma-separated, no bullets or headers."
}}

Be specific and realistic. Use the tech stack and seniority level implied by the prompt. Avoid buzzword inflation. Return only valid JSON, no other text."""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def call_claude():
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2000,
            messages=[{"role": "user", "content": claude_prompt}],
            timeout=30.0,
        )
        return response.content[0].text

    try:
        import json as _json
        raw = call_claude()
        # Parse JSON response
        try:
            # Strip markdown code fences if Claude wrapped it
            clean = raw.strip()
            if clean.startswith('```'):
                clean = clean.split('```')[1]
                if clean.startswith('json'):
                    clean = clean[4:]
            parsed = _json.loads(clean)
            return {
                "description": parsed.get("description", ""),
                "requirements": parsed.get("requirements", ""),
                "skills": parsed.get("skills", ""),
            }
        except Exception:
            # Fallback: return raw as description if JSON parse fails
            return {"description": raw, "requirements": "", "skills": ""}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate description: {str(e)}")


@router.get("/{job_id}/insights")
async def get_job_insights(
    job_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns aggregate analytics for all completed interviews for a job.
    """
    # 1. Fetch application IDs as plain integers (not Row objects)
    application_ids = [
        row[0] for row in
        db.query(models.Application.id).filter(models.Application.job_id == job_id).all()
    ]
    if not application_ids:
        return {"job_id": job_id, "candidate_count": 0, "insights": None}

    # 2. Fetch all completed screenings for this job
    screenings = db.query(models.Screening).filter(
        models.Screening.application_id.in_(application_ids),
        models.Screening.status == "completed",
        models.Screening.overall_score.isnot(None)
    ).all()

    if not screenings:
        return {"job_id": job_id, "candidate_count": 0, "insights": None}

    # 3. Build candidate reports from screening data with full AI evaluation
    reports = []
    for screening in screenings:
        if not (screening.application and screening.application.candidate):
            continue

        ev = {}
        if screening.ai_evaluation:
            try:
                ev = json.loads(screening.ai_evaluation)
            except Exception:
                ev = {}

        reports.append({
            "screening_id": screening.id,
            "candidate_id": screening.application.candidate.id,
            "candidate_name": screening.application.candidate.full_name,
            # Top-level scores
            "overall_score": round(screening.overall_score or 0),
            "technical_score": round(screening.technical_score) if screening.technical_score is not None else None,
            "communication_score": round(screening.communication_score) if screening.communication_score is not None else None,
            "cultural_fit_score": round(screening.cultural_fit_score) if screening.cultural_fit_score is not None else None,
            "recommendation": screening.recommendation or "",
            "recruiter_status": screening.recruiter_status or "pending",
            # From ai_evaluation
            "summary": ev.get("summary", ""),
            "strengths": ev.get("strengths", []),
            "weaknesses": ev.get("weaknesses", []),
            "hiring_recommendation": ev.get("hiring_recommendation", ""),
            "per_question": ev.get("per_question", []),
            # Interview session link
            "interview_session_id": screening.interview_session_id,
        })

    # 4. Fetch job skills
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    skills = [s.strip() for s in (job.skills_required or "").split(",") if s.strip()] if job else []

    # 5. Compute aggregate stats
    scores = [r["overall_score"] for r in reports]
    avg_score = sum(scores) / len(scores) if scores else 0

    # Score distribution buckets: 0-20, 20-40, 40-60, 60-80, 80-100
    distribution = {"0-20": 0, "20-40": 0, "40-60": 0, "60-80": 0, "80-100": 0}
    for s in scores:
        if s < 20: distribution["0-20"] += 1
        elif s < 40: distribution["20-40"] += 1
        elif s < 60: distribution["40-60"] += 1
        elif s < 80: distribution["60-80"] += 1
        else: distribution["80-100"] += 1

    # 6. Call Claude to synthesize cohort-level strengths/weaknesses
    cohort_summary = await synthesize_cohort_insights(reports)

    return {
        "job_id": job_id,
        "job_skills": skills,
        "candidate_count": len(reports),
        "average_score": round(avg_score, 2),
        "score_distribution": distribution,
        "cohort_summary": cohort_summary,
        "candidates": sorted(reports, key=lambda r: r["overall_score"], reverse=True)
    }


async def synthesize_cohort_insights(reports: list) -> dict:
    """
    Uses Claude to identify common patterns across all candidate reports.
    Returns: { "common_strengths": [...], "common_weaknesses": [...], "hiring_recommendation": str }
    """
    if not reports or len(reports) == 0:
        return {
            "common_strengths": [],
            "common_weaknesses": [],
            "hiring_recommendation": "No candidate data available."
        }

    if not ANTHROPIC_API_KEY or ANTHROPIC_API_KEY == "your-key-here":
        return {
            "common_strengths": ["Resume alignment"],
            "common_weaknesses": ["Technical depth"],
            "hiring_recommendation": "Review candidates individually."
        }

    summaries = []
    for r in reports:
        strengths_text = "; ".join(r.get("strengths", [])) or "none listed"
        weaknesses_text = "; ".join(r.get("weaknesses", [])) or "none listed"
        summaries.append(
            f"Candidate: {r['candidate_name']}\n"
            f"Overall: {r['overall_score']}/100 | Tech: {r.get('technical_score', 'N/A')} | "
            f"Comm: {r.get('communication_score', 'N/A')} | Recommendation: {r['recommendation']}\n"
            f"Strengths: {strengths_text}\n"
            f"Weaknesses: {weaknesses_text}\n"
            f"Hiring note: {r.get('hiring_recommendation', '')[:200]}"
        )

    prompt = f"""You are analyzing {len(reports)} candidates who completed AI interviews for the same role.

{chr(10).join(summaries)}

Based on ALL candidates above:
1. What are the 2-3 most common STRENGTHS across this cohort?
2. What are the 2-3 most common WEAKNESSES or skill gaps?
3. Give a 1-sentence overall hiring recommendation for this cohort.

Respond ONLY as JSON:
{{
  "common_strengths": ["...", "..."],
  "common_weaknesses": ["...", "..."],
  "hiring_recommendation": "..."
}}"""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
    def call_claude():
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
            timeout=30.0,
        )
        return response.content[0].text

    try:
        raw = call_claude()
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(clean)
    except Exception as e:
        print(f"[Insights] Claude cohort analysis failed: {e}")
        return {
            "common_strengths": [],
            "common_weaknesses": [],
            "hiring_recommendation": "Unable to generate cohort analysis."
        }


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
