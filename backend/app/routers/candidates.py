from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import List, Optional
from .. import models, schemas, auth
from ..database import get_db
import json
import os
import uuid

router = APIRouter(prefix="/api/candidates", tags=["Candidates"])

UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")


@router.post("/", response_model=schemas.CandidateResponse, status_code=status.HTTP_201_CREATED)
async def create_candidate(
    candidate_data: schemas.CandidateCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new candidate"""
    # Check if candidate already exists
    existing = db.query(models.Candidate).filter(
        models.Candidate.email == candidate_data.email
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A candidate with this email already exists"
        )
    
    new_candidate = models.Candidate(**candidate_data.model_dump())
    
    db.add(new_candidate)
    db.commit()
    db.refresh(new_candidate)
    
    # Log activity
    log_activity(db, current_user.id, "candidate_created", "candidate", new_candidate.id)
    
    return new_candidate


@router.get("/", response_model=List[schemas.CandidateResponse])
async def get_candidates(
    search: Optional[str] = None,
    skills: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get all candidates with optional filtering"""
    query = db.query(models.Candidate)
    
    # Search in name, email, location
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                models.Candidate.full_name.ilike(search_term),
                models.Candidate.email.ilike(search_term),
                models.Candidate.location.ilike(search_term)
            )
        )
    
    # Filter by skills
    if skills:
        skills_term = f"%{skills}%"
        query = query.filter(models.Candidate.skills.ilike(skills_term))
    
    # Order by created_at descending
    query = query.order_by(models.Candidate.created_at.desc())
    
    candidates = query.offset(skip).limit(limit).all()
    
    return candidates


@router.get("/stats")
async def get_candidate_stats(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get candidate statistics"""
    total_candidates = db.query(models.Candidate).count()
    
    # Get candidates by source
    sources = db.query(
        models.Candidate.source,
        func.count(models.Candidate.id)
    ).group_by(models.Candidate.source).all()
    
    return {
        "total_candidates": total_candidates,
        "by_source": {source: count for source, count in sources}
    }


@router.get("/{candidate_id}", response_model=schemas.CandidateResponse)
async def get_candidate(
    candidate_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific candidate by ID"""
    candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )
    
    return candidate


@router.put("/{candidate_id}", response_model=schemas.CandidateResponse)
async def update_candidate(
    candidate_id: int,
    candidate_update: schemas.CandidateUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Update a candidate"""
    candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )
    
    # Update fields
    update_data = candidate_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(candidate, field, value)
    
    db.commit()
    db.refresh(candidate)
    
    # Log activity
    log_activity(db, current_user.id, "candidate_updated", "candidate", candidate.id)
    
    return candidate


@router.delete("/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_candidate(
    candidate_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a candidate"""
    candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )
    
    # Delete associated applications
    db.query(models.Application).filter(models.Application.candidate_id == candidate_id).delete()
    
    db.delete(candidate)
    db.commit()
    
    # Log activity
    log_activity(db, current_user.id, "candidate_deleted", "candidate", candidate_id)
    
    return None


@router.post("/{candidate_id}/upload-resume")
async def upload_resume(
    candidate_id: int,
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a resume for a candidate"""
    candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )
    
    # Validate file type
    allowed_types = ["application/pdf", "application/msword", 
                     "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and Word documents are allowed"
        )
    
    # Create uploads directory if not exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{file_ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    # Save file
    with open(filepath, "wb") as f:
        content = await file.read()
        f.write(content)
    
    # Update candidate
    candidate.resume_url = filepath
    db.commit()
    
    # Log activity
    log_activity(db, current_user.id, "resume_uploaded", "candidate", candidate.id)
    
    return {"message": "Resume uploaded successfully", "filename": filename}


@router.get("/{candidate_id}/applications", response_model=List[schemas.ApplicationResponse])
async def get_candidate_applications(
    candidate_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get all applications for a candidate"""
    candidate = db.query(models.Candidate).filter(models.Candidate.id == candidate_id).first()
    
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found"
        )
    
    applications = db.query(models.Application).filter(
        models.Application.candidate_id == candidate_id
    ).all()
    
    return applications


from sqlalchemy import func

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
