from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import or_, func
from typing import List, Optional
from .. import models, schemas, auth
from ..database import get_db
import json

router = APIRouter(prefix="/api/applications", tags=["Applications"])


@router.post("/", response_model=schemas.ApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_application(
    application_data: schemas.ApplicationCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new job application"""
    # Check if job exists and is active
    job = db.query(models.Job).filter(models.Job.id == application_data.job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This job is not accepting applications"
        )
    
    # Check if candidate exists, create if not
    candidate = db.query(models.Candidate).filter(
        models.Candidate.email == application_data.email
    ).first()
    
    if not candidate:
        candidate = models.Candidate(
            email=application_data.email,
            full_name=application_data.full_name,
            phone=application_data.phone,
            linkedin_url=application_data.linkedin_url
        )
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
    
    # Check if already applied
    existing_application = db.query(models.Application).filter(
        models.Application.job_id == application_data.job_id,
        models.Application.candidate_id == candidate.id
    ).first()
    
    if existing_application:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This candidate has already applied for this job"
        )
    
    # Create application — scores are null until a resume is analysed
    new_application = models.Application(
        job_id=application_data.job_id,
        candidate_id=candidate.id,
        cover_letter=application_data.cover_letter,
        status="pending",
        match_score=None,
        skills_match=None,
        experience_match=None,
        ai_summary=None,
        ai_recommendation=None,
    )
    
    db.add(new_application)
    db.commit()
    db.refresh(new_application)
    
    # Log activity
    log_activity(db, current_user.id, "application_created", "application", new_application.id)
    
    # Load relationships
    new_application.candidate = candidate
    new_application.job = job
    
    return new_application


@router.get("/", response_model=List[schemas.ApplicationResponse])
async def get_applications(
    job_id: Optional[int] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    min_score: Optional[float] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get all applications with optional filtering"""
    query = db.query(models.Application).options(
        joinedload(models.Application.candidate),
        joinedload(models.Application.job),
        joinedload(models.Application.screenings)
    )

    # Filter by job
    if job_id:
        query = query.filter(models.Application.job_id == job_id)
    
    # Filter by status
    if status:
        query = query.filter(models.Application.status == status)
    
    # Filter by minimum score
    if min_score is not None:
        query = query.filter(models.Application.match_score >= min_score)
    
    # Search in candidate name/email
    if search:
        search_term = f"%{search}%"
        query = query.join(models.Candidate).filter(
            or_(
                models.Candidate.full_name.ilike(search_term),
                models.Candidate.email.ilike(search_term)
            )
        )
    
    # Order by match_score descending, then by applied_at
    query = query.order_by(models.Application.match_score.desc(), models.Application.applied_at.desc())
    
    applications = query.offset(skip).limit(limit).all()
    
    return applications


@router.get("/stats")
async def get_application_stats(
    job_id: Optional[int] = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get application statistics"""
    query = db.query(models.Application)
    
    if job_id:
        query = query.filter(models.Application.job_id == job_id)
    
    total = query.count()
    pending = query.filter(models.Application.status == "pending").count()
    screening = query.filter(models.Application.status == "screening").count()
    shortlisted = query.filter(models.Application.status == "shortlisted").count()
    interview = query.filter(models.Application.status == "interview").count()
    offered = query.filter(models.Application.status == "offered").count()
    hired = query.filter(models.Application.status == "hired").count()
    rejected = query.filter(models.Application.status == "rejected").count()
    
    # Average match score
    avg_score = db.query(func.avg(models.Application.match_score)).filter(
        models.Application.match_score.isnot(None)
    ).scalar() or 0
    
    return {
        "total": total,
        "pending": pending,
        "screening": screening,
        "shortlisted": shortlisted,
        "interview": interview,
        "offered": offered,
        "hired": hired,
        "rejected": rejected,
        "average_match_score": round(avg_score, 1)
    }


@router.post("/bulk-invite-screening")
async def bulk_invite_screening(
    payload: dict,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Bulk invite applications to screening"""
    application_ids = payload.get("application_ids", [])
    invited = 0
    skipped = 0

    for app_id in application_ids:
        application = db.query(models.Application).filter(models.Application.id == app_id).first()
        if not application:
            skipped += 1
            continue

        # Skip if an active screening already exists
        existing = db.query(models.Screening).filter(
            models.Screening.application_id == app_id,
            models.Screening.status.in_(["scheduled", "in_progress"])
        ).first()

        if existing:
            skipped += 1
            continue

        # Create screening record and update application status
        screening = models.Screening(
            application_id=app_id,
            status="scheduled",
            source="bulk",
        )
        db.add(screening)
        application.status = "screening"
        invited += 1

    db.commit()
    log_activity(db, current_user.id, "bulk_invite_screening", details=f"invited={invited},skipped={skipped}")
    return {"invited": invited, "skipped": skipped}


@router.get("/{application_id}", response_model=schemas.ApplicationResponse)
async def get_application(
    application_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific application by ID"""
    application = db.query(models.Application).options(
        joinedload(models.Application.candidate),
        joinedload(models.Application.job),
        joinedload(models.Application.screenings)
    ).filter(models.Application.id == application_id).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    return application


@router.put("/{application_id}", response_model=schemas.ApplicationResponse)
async def update_application(
    application_id: int,
    application_update: schemas.ApplicationUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Update an application"""
    application = db.query(models.Application).filter(models.Application.id == application_id).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Update fields
    update_data = application_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(application, field, value)
    
    db.commit()
    db.refresh(application)
    
    # Log activity
    log_activity(db, current_user.id, "application_updated", "application", application.id, 
                 json.dumps({"status": application.status}))
    
    return application


@router.post("/{application_id}/shortlist", response_model=schemas.ApplicationResponse)
async def shortlist_application(
    application_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Shortlist an application"""
    application = db.query(models.Application).filter(models.Application.id == application_id).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    application.status = "shortlisted"
    db.commit()
    db.refresh(application)
    
    log_activity(db, current_user.id, "application_shortlisted", "application", application.id)
    
    return application


@router.post("/{application_id}/reject", response_model=schemas.ApplicationResponse)
async def reject_application(
    application_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Reject an application"""
    application = db.query(models.Application).filter(models.Application.id == application_id).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    application.status = "rejected"
    db.commit()
    db.refresh(application)
    
    log_activity(db, current_user.id, "application_rejected", "application", application.id)
    
    return application


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(
    application_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Delete an application"""
    application = db.query(models.Application).filter(models.Application.id == application_id).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Delete associated screenings
    db.query(models.Screening).filter(models.Screening.application_id == application_id).delete()
    
    db.delete(application)
    db.commit()
    
    log_activity(db, current_user.id, "application_deleted", "application", application_id)
    
    return None


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
