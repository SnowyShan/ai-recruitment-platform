from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from typing import List, Optional
from .. import models, schemas, auth
from ..database import get_db
import json

router = APIRouter(prefix="/api/jobs", tags=["Jobs"])


@router.post("/", response_model=schemas.JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    job_data: schemas.JobCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new job posting"""
    new_job = models.Job(
        **job_data.model_dump(),
        created_by=current_user.id,
        status="draft"
    )
    
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    
    # Log activity
    log_activity(db, current_user.id, "job_created", "job", new_job.id, json.dumps({"title": new_job.title}))
    
    return new_job


@router.get("/", response_model=List[schemas.JobResponse])
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
    
    # Update fields
    update_data = job_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(job, field, value)
    
    db.commit()
    db.refresh(job)
    
    # Log activity
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
    """Publish a draft job"""
    job = db.query(models.Job).filter(models.Job.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    job.status = "active"
    db.commit()
    db.refresh(job)
    
    # Log activity
    log_activity(db, current_user.id, "job_published", "job", job.id)
    
    return job


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
