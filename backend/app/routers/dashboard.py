from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from typing import List, Optional
from datetime import datetime, timedelta
from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=schemas.DashboardStats)
async def get_dashboard_stats(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get dashboard statistics"""
    # Jobs stats
    total_jobs = db.query(models.Job).count()
    active_jobs = db.query(models.Job).filter(models.Job.status == "active").count()
    
    # Candidates stats
    total_candidates = db.query(models.Candidate).count()
    
    # Applications stats
    total_applications = db.query(models.Application).count()
    pending_applications = db.query(models.Application).filter(
        models.Application.status == "pending"
    ).count()
    
    # Screenings stats
    screenings_completed = db.query(models.Screening).filter(
        models.Screening.status == "completed"
    ).count()
    
    # Hired count
    hired_count = db.query(models.Application).filter(
        models.Application.status == "hired"
    ).count()
    
    return {
        "total_jobs": total_jobs,
        "active_jobs": active_jobs,
        "total_candidates": total_candidates,
        "total_applications": total_applications,
        "pending_applications": pending_applications,
        "screenings_completed": screenings_completed,
        "hired_count": hired_count,
        "avg_time_to_hire": None
    }


@router.get("/recent-activity", response_model=List[schemas.RecentActivity])
async def get_recent_activity(
    limit: int = Query(10, ge=1, le=50),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent activity logs"""
    activities = db.query(models.ActivityLog).order_by(
        desc(models.ActivityLog.created_at)
    ).limit(limit).all()
    
    return activities


@router.get("/pipeline-overview")
async def get_pipeline_overview(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get hiring pipeline overview"""
    pipeline = {
        "pending": db.query(models.Application).filter(models.Application.status == "pending").count(),
        "screening": db.query(models.Application).filter(models.Application.status == "screening").count(),
        "shortlisted": db.query(models.Application).filter(models.Application.status == "shortlisted").count(),
        "interview": db.query(models.Application).filter(models.Application.status == "interview").count(),
        "offered": db.query(models.Application).filter(models.Application.status == "offered").count(),
        "hired": db.query(models.Application).filter(models.Application.status == "hired").count(),
        "rejected": db.query(models.Application).filter(models.Application.status == "rejected").count(),
    }
    
    return pipeline


@router.get("/top-jobs")
async def get_top_jobs(
    limit: int = Query(5, ge=1, le=20),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get top jobs by number of applications"""
    jobs = db.query(
        models.Job,
        func.count(models.Application.id).label('application_count')
    ).outerjoin(models.Application).filter(
        models.Job.status == "active"
    ).group_by(models.Job.id).order_by(
        desc('application_count')
    ).limit(limit).all()
    
    result = []
    for job, count in jobs:
        result.append({
            "id": job.id,
            "title": job.title,
            "department": job.department,
            "location": job.location,
            "status": job.status,
            "applications_count": count
        })
    
    return result


@router.get("/recent-applications")
async def get_recent_applications(
    limit: int = Query(5, ge=1, le=20),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get recent applications"""
    applications = db.query(models.Application).options(
    ).order_by(desc(models.Application.applied_at)).limit(limit).all()
    
    result = []
    for app in applications:
        candidate = db.query(models.Candidate).filter(models.Candidate.id == app.candidate_id).first()
        job = db.query(models.Job).filter(models.Job.id == app.job_id).first()
        
        result.append({
            "id": app.id,
            "candidate_name": candidate.full_name if candidate else "Unknown",
            "candidate_email": candidate.email if candidate else "",
            "job_title": job.title if job else "Unknown",
            "status": app.status,
            "match_score": app.match_score,
            "applied_at": app.applied_at
        })
    
    return result


@router.get("/screening-performance")
async def get_screening_performance(
    days: int = Query(30, ge=7, le=365),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get screening performance over time"""
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Get completed screenings in date range
    screenings = db.query(models.Screening).filter(
        models.Screening.status == "completed",
        models.Screening.completed_at >= start_date
    ).all()
    
    # Calculate averages
    if screenings:
        avg_technical = sum(s.technical_score or 0 for s in screenings) / len(screenings)
        avg_communication = sum(s.communication_score or 0 for s in screenings) / len(screenings)
        avg_cultural = sum(s.cultural_fit_score or 0 for s in screenings) / len(screenings)
        avg_overall = sum(s.overall_score or 0 for s in screenings) / len(screenings)
        
        # Recommendation breakdown
        recommendations = {}
        for s in screenings:
            rec = s.recommendation or "unknown"
            recommendations[rec] = recommendations.get(rec, 0) + 1
    else:
        avg_technical = avg_communication = avg_cultural = avg_overall = 0
        recommendations = {}
    
    return {
        "total_screenings": len(screenings),
        "average_scores": {
            "technical": round(avg_technical, 1),
            "communication": round(avg_communication, 1),
            "cultural_fit": round(avg_cultural, 1),
            "overall": round(avg_overall, 1)
        },
        "recommendations": recommendations,
        "period_days": days
    }


@router.get("/hiring-funnel")
async def get_hiring_funnel(
    job_id: Optional[int] = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Get hiring funnel metrics"""
    query = db.query(models.Application)
    
    if job_id:
        query = query.filter(models.Application.job_id == job_id)
    
    total = query.count()
    
    if total == 0:
        return {
            "total_applications": 0,
            "funnel": [],
            "conversion_rates": {}
        }
    
    stages = [
        ("Applied", total),
        ("Screening", query.filter(models.Application.status.in_(["screening", "shortlisted", "interview", "offered", "hired"])).count()),
        ("Shortlisted", query.filter(models.Application.status.in_(["shortlisted", "interview", "offered", "hired"])).count()),
        ("Interview", query.filter(models.Application.status.in_(["interview", "offered", "hired"])).count()),
        ("Offered", query.filter(models.Application.status.in_(["offered", "hired"])).count()),
        ("Hired", query.filter(models.Application.status == "hired").count()),
    ]
    
    funnel = []
    conversion_rates = {}
    
    for i, (stage, count) in enumerate(stages):
        percentage = (count / total) * 100 if total > 0 else 0
        funnel.append({
            "stage": stage,
            "count": count,
            "percentage": round(percentage, 1)
        })
        
        if i > 0:
            prev_count = stages[i-1][1]
            rate = (count / prev_count) * 100 if prev_count > 0 else 0
            conversion_rates[f"{stages[i-1][0]}_to_{stage}"] = round(rate, 1)
    
    return {
        "total_applications": total,
        "funnel": funnel,
        "conversion_rates": conversion_rates
    }
