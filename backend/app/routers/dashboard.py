from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, desc, case
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
    total_jobs           = db.query(models.Job).count()
    active_jobs          = db.query(models.Job).filter(models.Job.status == "active").count()
    total_candidates     = db.query(models.Candidate).count()
    total_applications   = db.query(models.Application).count()
    pending_applications = db.query(models.Application).filter(models.Application.status == "pending").count()
    screenings_completed = db.query(models.Screening).filter(models.Screening.status == "completed").count()
    hired_count          = db.query(models.Application).filter(models.Application.status == "hired").count()
    return {
        "total_jobs": total_jobs, "active_jobs": active_jobs,
        "total_candidates": total_candidates, "total_applications": total_applications,
        "pending_applications": pending_applications, "screenings_completed": screenings_completed,
        "hired_count": hired_count, "avg_time_to_hire": None,
    }


@router.get("/recent-activity", response_model=List[schemas.RecentActivity])
async def get_recent_activity(
    limit: int = Query(10, ge=1, le=50),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    return db.query(models.ActivityLog).order_by(desc(models.ActivityLog.created_at)).limit(limit).all()


@router.get("/pipeline-overview")
async def get_pipeline_overview(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    statuses = ["pending","screening","shortlisted","interview","offered","hired","rejected"]
    result = {}
    for s in statuses:
        result[s] = db.query(models.Application).filter(models.Application.status == s).count()
    return result


@router.get("/top-jobs")
async def get_top_jobs(
    limit: int = Query(5, ge=1, le=20),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    jobs = db.query(
        models.Job,
        func.count(models.Application.id).label("application_count")
    ).outerjoin(models.Application).filter(
        models.Job.status == "active"
    ).group_by(models.Job.id).order_by(desc("application_count")).limit(limit).all()

    result = []
    for job, count in jobs:
        days_open = (datetime.utcnow() - job.created_at).days if job.created_at else 0
        result.append({
            "id": job.id, "title": job.title,
            "department": job.department, "location": job.location,
            "status": job.status, "applications_count": count,
            "days_open": days_open,
            "is_urgent": getattr(job, "is_urgent", False) or False,
        })
    return result


@router.get("/recent-applications")
async def get_recent_applications(
    limit: int = Query(5, ge=1, le=20),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    apps = db.query(models.Application).options(
        joinedload(models.Application.candidate),
        joinedload(models.Application.job),
    ).order_by(desc(models.Application.applied_at)).limit(limit).all()

    return [{
        "id": a.id,
        "candidate_name": a.candidate.full_name if a.candidate else "Unknown",
        "candidate_email": a.candidate.email if a.candidate else "",
        "job_title": a.job.title if a.job else "Unknown",
        "status": a.status,
        "match_score": a.match_score,
        "applied_at": a.applied_at,
    } for a in apps]


@router.get("/top-candidates")
async def get_top_candidates(
    limit: int = Query(5, ge=1, le=20),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Top AI-matched candidates by score."""
    apps = db.query(models.Application).options(
        joinedload(models.Application.candidate),
        joinedload(models.Application.job),
    ).filter(
        models.Application.match_score.isnot(None)
    ).order_by(desc(models.Application.match_score)).limit(limit).all()

    return [{
        "id": a.id,
        "candidate_name": a.candidate.full_name if a.candidate else "Unknown",
        "candidate_email": a.candidate.email if a.candidate else "",
        "job_title": a.job.title if a.job else "Unknown",
        "job_id": a.job_id,
        "status": a.status,
        "match_score": a.match_score,
        "experience_years": a.candidate.experience_years if a.candidate else None,
        "source": a.candidate.source if a.candidate else "direct",
    } for a in apps]


@router.get("/screening-performance")
async def get_screening_performance(
    days: int = Query(30, ge=7, le=365),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    start_date = datetime.utcnow() - timedelta(days=days)
    screenings = db.query(models.Screening).filter(
        models.Screening.status == "completed",
        models.Screening.completed_at >= start_date
    ).all()

    total = db.query(models.Screening).count()
    scheduled = db.query(models.Screening).filter(models.Screening.status == "scheduled").count()
    in_progress = db.query(models.Screening).filter(models.Screening.status == "in_progress").count()
    completed = db.query(models.Screening).filter(models.Screening.status == "completed").count()
    cancelled = db.query(models.Screening).filter(models.Screening.status == "cancelled").count()

    if screenings:
        avg_overall = sum(s.overall_score or 0 for s in screenings) / len(screenings)
        avg_technical = sum(s.technical_score or 0 for s in screenings) / len(screenings)
        recommendations = {}
        for s in screenings:
            rec = s.recommendation or "unknown"
            recommendations[rec] = recommendations.get(rec, 0) + 1
    else:
        avg_overall = avg_technical = 0
        recommendations = {}

    return {
        "total": total, "scheduled": scheduled, "in_progress": in_progress,
        "completed": completed, "cancelled": cancelled,
        "total_screenings": len(screenings),
        "average_overall_score": round(avg_overall, 1),
        "average_scores": {
            "technical": round(avg_technical, 1),
            "overall": round(avg_overall, 1),
        },
        "recommendations": recommendations,
        "period_days": days,
    }


@router.get("/hiring-funnel")
async def get_hiring_funnel(
    job_id: Optional[int] = None,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.Application)
    if job_id:
        query = query.filter(models.Application.job_id == job_id)

    total = query.count()
    if total == 0:
        return {"total_applications": 0, "funnel": [], "conversion_rates": {}}

    stages = [
        ("Applied",     total),
        ("AI Screened", query.filter(models.Application.status.in_(
            ["screening","shortlisted","interview","offered","hired"])).count()),
        ("Shortlisted", query.filter(models.Application.status.in_(
            ["shortlisted","interview","offered","hired"])).count()),
        ("Interviewed", query.filter(models.Application.status.in_(
            ["interview","offered","hired"])).count()),
        ("Offered",     query.filter(models.Application.status.in_(["offered","hired"])).count()),
        ("Hired",       query.filter(models.Application.status == "hired").count()),
    ]

    funnel = []
    conversion_rates = {}
    for i, (stage, count) in enumerate(stages):
        pct = (count / total * 100) if total > 0 else 0
        funnel.append({"stage": stage, "count": count, "percentage": round(pct, 1)})
        if i > 0:
            prev = stages[i - 1][1]
            rate = (count / prev * 100) if prev > 0 else 0
            conversion_rates[f"{stages[i-1][0]}_to_{stage}"] = round(rate, 1)

    return {"total_applications": total, "funnel": funnel, "conversion_rates": conversion_rates}


@router.get("/insights")
async def get_insights(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Real AI-derived recruitment insights based on live data."""
    insights = []
    now = datetime.utcnow()

    # 1. Jobs with low applicant count and open for > 14 days
    active_jobs = db.query(models.Job).filter(models.Job.status == "active").all()
    for job in active_jobs:
        app_count = db.query(models.Application).filter(models.Application.job_id == job.id).count()
        days_open = (now - job.created_at).days if job.created_at else 0
        if app_count < 8 and days_open > 10:
            insights.append({
                "type": "warn",
                "title": "Low application volume",
                "text": f'"{job.title}" has been open {days_open} days with only {app_count} applicants. Consider expanding sourcing or rewriting the job description.',
                "action": "Manage job",
                "action_to": f"/jobs/{job.id}",
            })

    # 2. Pending applications count
    pending = db.query(models.Application).filter(models.Application.status == "pending").count()
    if pending > 10:
        insights.append({
            "type": "info",
            "title": "Applications awaiting review",
            "text": f"{pending} applications are pending review. Use bulk shortlist to speed up your pipeline.",
            "action": "Review applications",
            "action_to": "/applications",
        })

    # 3. AI screening performance
    completed_scr = db.query(models.Screening).filter(models.Screening.status == "completed").all()
    if completed_scr:
        avg = sum(s.overall_score or 0 for s in completed_scr) / len(completed_scr)
        pass_count = sum(1 for s in completed_scr if s.recommendation == "pass")
        pass_rate = round(pass_count / len(completed_scr) * 100)
        insights.append({
            "type": "info",
            "title": "AI screening summary",
            "text": f"{len(completed_scr)} screenings completed. Avg score {round(avg)}/100 · {pass_rate}% pass rate. Top performers await review.",
            "action": "View screenings",
            "action_to": "/screenings",
        })

    # 4. Top candidate not yet contacted
    top_uncontacted = db.query(models.Application).options(
        joinedload(models.Application.candidate),
        joinedload(models.Application.job),
    ).filter(
        models.Application.status == "shortlisted",
        models.Application.match_score >= 85,
    ).order_by(desc(models.Application.match_score)).first()
    if top_uncontacted and top_uncontacted.candidate:
        insights.append({
            "type": "alert",
            "title": "High-match candidate ready",
            "text": f'{top_uncontacted.candidate.full_name} scored {round(top_uncontacted.match_score or 0)}/100 for {top_uncontacted.job.title if top_uncontacted.job else "a role"} and is shortlisted. Send them to the interview stage before they accept another offer.',
            "action": "View candidate",
            "action_to": "/applications",
        })

    # 5. Scheduled screenings not yet used
    scheduled_expired = db.query(models.Screening).filter(
        models.Screening.status == "scheduled",
        models.Screening.invite_expires_at < now,
        models.Screening.invite_used == False,
    ).count()
    if scheduled_expired > 0:
        insights.append({
            "type": "warn",
            "title": "Expired invitations",
            "text": f"{scheduled_expired} screening invite(s) have expired without being used. Re-invite candidates to keep the pipeline moving.",
            "action": "Manage screenings",
            "action_to": "/screenings",
        })

    return {"insights": insights[:5]}  # cap at 5


@router.get("/weekly-trend")
async def get_weekly_trend(
    weeks: int = Query(8, ge=4, le=16),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Applications received per week for the trend chart."""
    data = []
    for i in range(weeks, 0, -1):
        week_start = datetime.utcnow() - timedelta(weeks=i)
        week_end   = datetime.utcnow() - timedelta(weeks=i - 1)
        count = db.query(models.Application).filter(
            models.Application.applied_at >= week_start,
            models.Application.applied_at < week_end,
        ).count()
        data.append({
            "week": weeks - i + 1,
            "label": f"W{weeks - i + 1}",
            "applications": count,
        })
    return {"trend": data}


@router.get("/notifications")
async def get_notifications(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """Real-time notifications about recent screening completions and important events."""
    from sqlalchemy.orm import joinedload
    notifications = []

    # 1. Recently completed screenings (last 7 days)
    from datetime import datetime, timedelta
    cutoff = datetime.utcnow() - timedelta(days=7)
    recent_scr = db.query(models.Screening).options(
        joinedload(models.Screening.application).joinedload(models.Application.candidate),
        joinedload(models.Screening.application).joinedload(models.Application.job),
    ).filter(
        models.Screening.status == "completed",
        models.Screening.completed_at >= cutoff,
    ).order_by(models.Screening.completed_at.desc()).limit(8).all()

    for s in recent_scr:
        app = s.application
        if not app: continue
        candidate_name = app.candidate.full_name if app.candidate else "A candidate"
        job_title = app.job.title if app.job else "a job"
        score = round(s.overall_score) if s.overall_score else None
        rec = s.recommendation
        time_ago = datetime.utcnow() - s.completed_at
        hours_ago = int(time_ago.total_seconds() // 3600)
        mins_ago = int(time_ago.total_seconds() // 60)

        if hours_ago >= 24:
            time_str = f"{hours_ago // 24}d ago"
        elif hours_ago >= 1:
            time_str = f"{hours_ago}h ago"
        else:
            time_str = f"{max(1, mins_ago)}m ago"

        notifications.append({
            "id": f"scr_{s.id}",
            "type": "screening_complete",
            "title": f"{candidate_name} completed screening",
            "body": f'{job_title} · Score {score}/100 · {"Pass ✓" if rec == "pass" else "Fail ✗" if rec == "fail" else "Pending"}',
            "score": score,
            "recommendation": rec,
            "time": time_str,
            "link": "/screenings",
            "read": False,
        })

    # 2. Newly applied (last 24h)
    cutoff24 = datetime.utcnow() - timedelta(hours=24)
    new_apps = db.query(models.Application).options(
        joinedload(models.Application.candidate),
        joinedload(models.Application.job),
    ).filter(models.Application.applied_at >= cutoff24).order_by(
        models.Application.applied_at.desc()).limit(5).all()

    for a in new_apps:
        cname = a.candidate.full_name if a.candidate else "Someone"
        jname = a.job.title if a.job else "a job"
        notifications.append({
            "id": f"app_{a.id}",
            "type": "new_application",
            "title": f"{cname} applied",
            "body": jname,
            "score": round(a.match_score) if a.match_score else None,
            "recommendation": None,
            "time": "Today",
            "link": "/applications",
            "read": False,
        })

    return {"notifications": notifications[:10], "unread_count": len(notifications)}
