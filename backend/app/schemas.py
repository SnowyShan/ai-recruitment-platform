from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum


# Enums
class UserRole(str, Enum):
    ADMIN = "admin"
    RECRUITER = "recruiter"
    HIRING_MANAGER = "hiring_manager"


class JobStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class ApplicationStatus(str, Enum):
    PENDING = "pending"
    SCREENING = "screening"
    SHORTLISTED = "shortlisted"
    INTERVIEW = "interview"
    OFFERED = "offered"
    REJECTED = "rejected"
    HIRED = "hired"


class ScreeningStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# User Schemas
class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    company_name: Optional[str] = None


class UserCreate(UserBase):
    password: str = Field(min_length=6)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    company_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UserResponse(UserBase):
    id: int
    role: str
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


class TokenData(BaseModel):
    email: Optional[str] = None


# Job Schemas
class JobBase(BaseModel):
    title: str
    department: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = "full_time"
    experience_level: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    description: str
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    skills_required: Optional[str] = None
    benefits: Optional[str] = None
    deadline: Optional[datetime] = None


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    location: Optional[str] = None
    job_type: Optional[str] = None
    experience_level: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    description: Optional[str] = None
    requirements: Optional[str] = None
    responsibilities: Optional[str] = None
    skills_required: Optional[str] = None
    benefits: Optional[str] = None
    status: Optional[str] = None
    deadline: Optional[datetime] = None


class JobResponse(JobBase):
    id: int
    status: str
    created_by: int
    created_at: datetime
    updated_at: datetime
    applications_count: Optional[int] = 0
    
    class Config:
        from_attributes = True


# Candidate Schemas
class CandidateBase(BaseModel):
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None


class CandidateCreate(CandidateBase):
    resume_text: Optional[str] = None
    skills: Optional[str] = None
    experience_years: Optional[float] = None
    education: Optional[str] = None
    summary: Optional[str] = None


class CandidateUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    linkedin_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    skills: Optional[str] = None
    experience_years: Optional[float] = None


class CandidateResponse(CandidateBase):
    id: int
    resume_url: Optional[str] = None
    skills: Optional[str] = None
    experience_years: Optional[float] = None
    education: Optional[str] = None
    summary: Optional[str] = None
    source: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# Application Schemas
class ApplicationBase(BaseModel):
    job_id: int
    candidate_id: int
    cover_letter: Optional[str] = None


class ApplicationCreate(BaseModel):
    job_id: int
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    cover_letter: Optional[str] = None
    linkedin_url: Optional[str] = None


class ApplicationUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class ApplicationResponse(BaseModel):
    id: int
    job_id: int
    candidate_id: int
    status: str
    cover_letter: Optional[str] = None
    match_score: Optional[float] = None
    skills_match: Optional[float] = None
    experience_match: Optional[float] = None
    ai_summary: Optional[str] = None
    ai_recommendation: Optional[str] = None
    notes: Optional[str] = None
    applied_at: datetime
    candidate: Optional[CandidateResponse] = None
    job: Optional[JobResponse] = None
    screenings: List['ScreeningResponse'] = []

    class Config:
        from_attributes = True


# Screening Schemas
class ScreeningCreate(BaseModel):
    application_id: int
    scheduled_at: Optional[datetime] = None


class ScreeningUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None


class ScreeningResponse(BaseModel):
    id: int
    application_id: int
    status: str
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    technical_score: Optional[float] = None
    communication_score: Optional[float] = None
    cultural_fit_score: Optional[float] = None
    overall_score: Optional[float] = None
    recommendation: Optional[str] = None
    ai_evaluation: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# Resolve forward reference in ApplicationResponse
ApplicationResponse.model_rebuild()


# Dashboard Stats
class DashboardStats(BaseModel):
    total_jobs: int
    active_jobs: int
    total_candidates: int
    total_applications: int
    pending_applications: int
    screenings_completed: int
    hired_count: int
    avg_time_to_hire: Optional[float] = None


class RecentActivity(BaseModel):
    id: int
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    details: Optional[str] = None
    created_at: datetime


# Interview Question Schemas
class InterviewQuestionCreate(BaseModel):
    category: str
    subcategory: Optional[str] = None
    question: str
    expected_answer_points: Optional[str] = None
    difficulty: str = "medium"
    skills_tested: Optional[str] = None


class InterviewQuestionResponse(BaseModel):
    id: int
    category: str
    subcategory: Optional[str] = None
    question: str
    difficulty: str
    skills_tested: Optional[str] = None
    is_active: bool
    
    class Config:
        from_attributes = True
