from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from .database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    RECRUITER = "recruiter"
    HIRING_MANAGER = "hiring_manager"


class JobStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class ApplicationStatus(str, enum.Enum):
    PENDING = "pending"
    SCREENING = "screening"
    SHORTLISTED = "shortlisted"
    INTERVIEW = "interview"
    OFFERED = "offered"
    REJECTED = "rejected"
    HIRED = "hired"


class ScreeningStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    company_name = Column(String(255), nullable=True)
    role = Column(String(50), default=UserRole.RECRUITER.value)
    avatar_url = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    jobs = relationship("Job", back_populates="created_by_user")
    

class Job(Base):
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    department = Column(String(255), nullable=True)
    location = Column(String(255), nullable=True)
    job_type = Column(String(50), default="full_time")  # full_time, part_time, contract, internship
    experience_level = Column(String(50), nullable=True)  # entry, mid, senior, lead, executive
    salary_min = Column(Integer, nullable=True)
    salary_max = Column(Integer, nullable=True)
    description = Column(Text, nullable=False)
    requirements = Column(Text, nullable=True)
    responsibilities = Column(Text, nullable=True)
    skills_required = Column(Text, nullable=True)  # JSON string of skills
    benefits = Column(Text, nullable=True)
    status = Column(String(50), default=JobStatus.DRAFT.value)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deadline = Column(DateTime, nullable=True)
    
    # Relationships
    created_by_user = relationship("User", back_populates="jobs")
    applications = relationship("Application", back_populates="job")


class Candidate(Base):
    __tablename__ = "candidates"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    location = Column(String(255), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    portfolio_url = Column(String(500), nullable=True)
    resume_url = Column(String(500), nullable=True)
    resume_text = Column(Text, nullable=True)  # Extracted text from resume
    skills = Column(Text, nullable=True)  # JSON string of extracted skills
    experience_years = Column(Float, nullable=True)
    education = Column(Text, nullable=True)  # JSON string
    summary = Column(Text, nullable=True)
    source = Column(String(100), default="direct")  # direct, linkedin, referral, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    applications = relationship("Application", back_populates="candidate")


class Application(Base):
    __tablename__ = "applications"
    
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    candidate_id = Column(Integer, ForeignKey("candidates.id"), nullable=False)
    status = Column(String(50), default=ApplicationStatus.PENDING.value)
    cover_letter = Column(Text, nullable=True)
    match_score = Column(Float, nullable=True)  # AI-calculated match score (0-100)
    skills_match = Column(Float, nullable=True)
    experience_match = Column(Float, nullable=True)
    ai_summary = Column(Text, nullable=True)  # AI-generated summary
    ai_recommendation = Column(String(50), nullable=True)  # strong_yes, yes, maybe, no
    notes = Column(Text, nullable=True)  # Recruiter notes
    applied_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    job = relationship("Job", back_populates="applications")
    candidate = relationship("Candidate", back_populates="applications")
    screenings = relationship("Screening", back_populates="application")


class Screening(Base):
    __tablename__ = "screenings"
    
    id = Column(Integer, primary_key=True, index=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    status = Column(String(50), default=ScreeningStatus.SCHEDULED.value)
    scheduled_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    transcript = Column(Text, nullable=True)  # JSON string of conversation
    questions_asked = Column(Text, nullable=True)  # JSON string
    responses = Column(Text, nullable=True)  # JSON string
    technical_score = Column(Float, nullable=True)
    communication_score = Column(Float, nullable=True)
    cultural_fit_score = Column(Float, nullable=True)
    overall_score = Column(Float, nullable=True)
    ai_evaluation = Column(Text, nullable=True)  # JSON string of detailed evaluation
    recommendation = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    source = Column(String(20), default="manual")  # manual, auto, bulk

    # Relationships
    application = relationship("Application", back_populates="screenings")


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InterviewQuestion(Base):
    __tablename__ = "interview_questions"
    
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(100), nullable=False)  # technical, behavioral, situational
    subcategory = Column(String(100), nullable=True)  # e.g., python, leadership, problem_solving
    question = Column(Text, nullable=False)
    expected_answer_points = Column(Text, nullable=True)  # JSON string of key points
    difficulty = Column(String(50), default="medium")  # easy, medium, hard
    skills_tested = Column(Text, nullable=True)  # JSON string of skills
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=True)  # job, candidate, application, screening
    entity_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)  # JSON string
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
