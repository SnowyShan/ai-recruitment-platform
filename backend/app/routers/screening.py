from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime
from .. import models, schemas, auth
from ..database import get_db
import json
import random

router = APIRouter(prefix="/api/screenings", tags=["Screenings"])


@router.post("/", response_model=schemas.ScreeningResponse, status_code=status.HTTP_201_CREATED)
async def create_screening(
    screening_data: schemas.ScreeningCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Schedule a new AI screening interview"""
    # Check if application exists
    application = db.query(models.Application).filter(
        models.Application.id == screening_data.application_id
    ).first()
    
    if not application:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found"
        )
    
    # Check if screening already exists for this application
    existing = db.query(models.Screening).filter(
        models.Screening.application_id == screening_data.application_id,
        models.Screening.status.in_(["scheduled", "in_progress"])
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A screening is already scheduled or in progress for this application"
        )
    
    # Create screening
    new_screening = models.Screening(
        application_id=screening_data.application_id,
        scheduled_at=screening_data.scheduled_at or datetime.utcnow(),
        status="scheduled"
    )
    
    db.add(new_screening)
    
    # Update application status
    application.status = "screening"
    
    db.commit()
    db.refresh(new_screening)
    
    # Log activity
    log_activity(db, current_user.id, "screening_scheduled", "screening", new_screening.id)
    
    return new_screening


@router.get("/", response_model=List[schemas.ScreeningResponse])
async def get_screenings(
    status: Optional[str] = None,
    application_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get all screenings with optional filtering"""
    query = db.query(models.Screening)
    
    if status:
        query = query.filter(models.Screening.status == status)
    
    if application_id:
        query = query.filter(models.Screening.application_id == application_id)
    
    # Order by scheduled_at
    query = query.order_by(models.Screening.scheduled_at.desc())
    
    screenings = query.offset(skip).limit(limit).all()
    
    return screenings


@router.get("/stats")
async def get_screening_stats(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get screening statistics"""
    total = db.query(models.Screening).count()
    scheduled = db.query(models.Screening).filter(models.Screening.status == "scheduled").count()
    in_progress = db.query(models.Screening).filter(models.Screening.status == "in_progress").count()
    completed = db.query(models.Screening).filter(models.Screening.status == "completed").count()
    cancelled = db.query(models.Screening).filter(models.Screening.status == "cancelled").count()
    
    # Average scores
    avg_technical = db.query(func.avg(models.Screening.technical_score)).filter(
        models.Screening.technical_score.isnot(None)
    ).scalar() or 0
    
    avg_communication = db.query(func.avg(models.Screening.communication_score)).filter(
        models.Screening.communication_score.isnot(None)
    ).scalar() or 0
    
    avg_overall = db.query(func.avg(models.Screening.overall_score)).filter(
        models.Screening.overall_score.isnot(None)
    ).scalar() or 0
    
    return {
        "total": total,
        "scheduled": scheduled,
        "in_progress": in_progress,
        "completed": completed,
        "cancelled": cancelled,
        "average_technical_score": round(avg_technical, 1),
        "average_communication_score": round(avg_communication, 1),
        "average_overall_score": round(avg_overall, 1)
    }


@router.get("/{screening_id}", response_model=schemas.ScreeningResponse)
async def get_screening(
    screening_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific screening by ID"""
    screening = db.query(models.Screening).filter(models.Screening.id == screening_id).first()
    
    if not screening:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screening not found"
        )
    
    return screening


@router.post("/{screening_id}/start", response_model=schemas.ScreeningResponse)
async def start_screening(
    screening_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Start a scheduled screening"""
    screening = db.query(models.Screening).filter(models.Screening.id == screening_id).first()
    
    if not screening:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screening not found"
        )
    
    if screening.status != "scheduled":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screening cannot be started"
        )
    
    screening.status = "in_progress"
    screening.started_at = datetime.utcnow()
    
    db.commit()
    db.refresh(screening)
    
    log_activity(db, current_user.id, "screening_started", "screening", screening.id)
    
    return screening


@router.post("/{screening_id}/complete", response_model=schemas.ScreeningResponse)
async def complete_screening(
    screening_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Complete a screening with AI-generated scores"""
    screening = db.query(models.Screening).filter(models.Screening.id == screening_id).first()
    
    if not screening:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screening not found"
        )
    
    if screening.status not in ["scheduled", "in_progress"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screening cannot be completed"
        )
    
    # Generate AI evaluation scores (simplified)
    evaluation = generate_ai_evaluation()
    
    screening.status = "completed"
    screening.completed_at = datetime.utcnow()
    screening.started_at = screening.started_at or datetime.utcnow()
    screening.duration_minutes = random.randint(15, 45)
    screening.technical_score = evaluation["technical_score"]
    screening.communication_score = evaluation["communication_score"]
    screening.cultural_fit_score = evaluation["cultural_fit_score"]
    screening.overall_score = evaluation["overall_score"]
    screening.recommendation = evaluation["recommendation"]
    screening.ai_evaluation = json.dumps(evaluation["details"])
    screening.transcript = json.dumps(evaluation["transcript"])
    
    # Update application status based on recommendation
    application = db.query(models.Application).filter(
        models.Application.id == screening.application_id
    ).first()
    
    if application:
        if evaluation["recommendation"] in ["strong_pass", "pass"]:
            application.status = "shortlisted"
        else:
            application.status = "rejected"
    
    db.commit()
    db.refresh(screening)
    
    log_activity(db, current_user.id, "screening_completed", "screening", screening.id)
    
    return screening


@router.post("/{screening_id}/cancel", response_model=schemas.ScreeningResponse)
async def cancel_screening(
    screening_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a scheduled screening"""
    screening = db.query(models.Screening).filter(models.Screening.id == screening_id).first()
    
    if not screening:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screening not found"
        )
    
    if screening.status not in ["scheduled", "in_progress"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Screening cannot be cancelled"
        )
    
    screening.status = "cancelled"
    
    # Revert application status
    application = db.query(models.Application).filter(
        models.Application.id == screening.application_id
    ).first()
    
    if application and application.status == "screening":
        application.status = "pending"
    
    db.commit()
    db.refresh(screening)
    
    log_activity(db, current_user.id, "screening_cancelled", "screening", screening.id)
    
    return screening


@router.put("/{screening_id}", response_model=schemas.ScreeningResponse)
async def update_screening(
    screening_id: int,
    screening_update: schemas.ScreeningUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Update screening notes"""
    screening = db.query(models.Screening).filter(models.Screening.id == screening_id).first()
    
    if not screening:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Screening not found"
        )
    
    update_data = screening_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(screening, field, value)
    
    db.commit()
    db.refresh(screening)
    
    return screening


def generate_ai_evaluation() -> dict:
    """Generate simulated AI evaluation (in production, use actual AI)"""
    technical_score = round(random.uniform(55, 95), 1)
    communication_score = round(random.uniform(60, 95), 1)
    cultural_fit_score = round(random.uniform(50, 90), 1)
    overall_score = round((technical_score * 0.4 + communication_score * 0.35 + cultural_fit_score * 0.25), 1)
    
    # Determine recommendation
    if overall_score >= 80:
        recommendation = "strong_pass"
    elif overall_score >= 65:
        recommendation = "pass"
    elif overall_score >= 50:
        recommendation = "borderline"
    else:
        recommendation = "fail"
    
    # Sample transcript
    transcript = [
        {
            "role": "ai",
            "message": "Hello! Welcome to your screening interview for this position. I'm an AI interviewer and I'll be asking you a few questions. Are you ready to begin?",
            "timestamp": "00:00"
        },
        {
            "role": "candidate",
            "message": "Yes, I'm ready. Thank you for this opportunity.",
            "timestamp": "00:15"
        },
        {
            "role": "ai",
            "message": "Great! Let's start with a simple question. Can you tell me about your most recent project and what technologies you used?",
            "timestamp": "00:20"
        },
        {
            "role": "candidate",
            "message": "In my most recent project, I worked on building a full-stack web application using React for the frontend and Node.js for the backend...",
            "timestamp": "00:30"
        }
    ]
    
    details = {
        "strengths": [
            "Strong technical knowledge demonstrated",
            "Clear communication skills",
            "Problem-solving approach evident"
        ],
        "areas_for_improvement": [
            "Could provide more specific examples",
            "Time management during responses"
        ],
        "key_observations": [
            "Candidate showed enthusiasm for the role",
            "Technical responses were accurate and detailed"
        ]
    }
    
    return {
        "technical_score": technical_score,
        "communication_score": communication_score,
        "cultural_fit_score": cultural_fit_score,
        "overall_score": overall_score,
        "recommendation": recommendation,
        "details": details,
        "transcript": transcript
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
