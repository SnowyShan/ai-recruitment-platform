from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

from .database import engine, Base
from .routers import (
    auth_router,
    jobs_router,
    candidates_router,
    applications_router,
    screening_router,
    dashboard_router,
    public_router,
)

load_dotenv()

# Create database tables on startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create uploads directory
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    os.makedirs(upload_dir, exist_ok=True)
    
    yield
    # Cleanup if needed

app = FastAPI(
    title="TalentBridge AI",
    description="AI-Powered Recruitment Platform - Intelligent candidate screening and matching",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration
cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173")
origins = [origin.strip() for origin in cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(candidates_router)
app.include_router(applications_router)
app.include_router(screening_router)
app.include_router(dashboard_router)
app.include_router(public_router)


@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "name": "TalentBridge AI",
        "version": "1.0.0",
        "description": "AI-Powered Recruitment Platform",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "talentbridge-ai"}


@app.get("/api")
async def api_info():
    """API information"""
    return {
        "version": "1.0.0",
        "endpoints": {
            "auth": "/api/auth",
            "jobs": "/api/jobs",
            "candidates": "/api/candidates",
            "applications": "/api/applications",
            "screenings": "/api/screenings",
            "dashboard": "/api/dashboard"
        }
    }
