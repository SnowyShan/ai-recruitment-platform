from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os
from dotenv import load_dotenv

from sqlalchemy import inspect, text
from .database import engine, Base, run_migrations
from .routers import (
    auth_router,
    jobs_router,
    candidates_router,
    applications_router,
    screening_router,
    dashboard_router,
    public_router,
    settings_router,
)
from .routers.rate_limit import RateLimiter, get_remote_address

load_dotenv()

rate_limiter = RateLimiter(requests=20, period=60.0)


# Create database tables on startup
@asynccontextmanager
async def lifespan(app: FastAPI):

    # Create tables (new tables only — does not alter existing ones)
    Base.metadata.create_all(bind=engine)
    run_migrations(engine)

    # Lightweight column migrations for existing tables
    insp = inspect(engine)
    with engine.begin() as conn:
        if "screenings" in insp.get_table_names():
            cols = [c["name"] for c in insp.get_columns("screenings")]
            if "source" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE screenings ADD COLUMN source VARCHAR(20) DEFAULT 'manual'"
                    )
                )

    # Create uploads directory
    upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
    os.makedirs(upload_dir, exist_ok=True)

    yield
    # Cleanup if needed


app = FastAPI(
    title="TalentBridge AI",
    description="AI-Powered Recruitment Platform - Intelligent candidate screening and matching",
    version="1.0.0",
    lifespan=lifespan,
    redirect_slashes=False,  # Prevent 307 redirects that strip Authorization headers
)

# CORS Configuration
cors_origins = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173"
)
origins = [origin.strip() for origin in cors_origins.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    excluded_paths = ["/health", "/docs", "/openapi.json", "/redoc"]
    if request.url.path in excluded_paths:
        return await call_next(request)

    # Skip rate limiting in DEBUG mode (tests)
    if os.getenv("DEBUG", "").lower() in ("true", "1", "yes"):
        return await call_next(request)

    client_id = get_remote_address(request)
    if not rate_limiter.is_allowed(client_id):
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded: 20 requests per minute"},
        )
    return await call_next(request)


# Include routers
app.include_router(auth_router)
app.include_router(jobs_router)
app.include_router(candidates_router)
app.include_router(applications_router)
app.include_router(screening_router)
app.include_router(dashboard_router)
app.include_router(public_router)
app.include_router(settings_router)


@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "name": "TalentBridge AI",
        "version": "1.0.0",
        "description": "AI-Powered Recruitment Platform",
        "status": "running",
        "docs": "/docs",
        "redoc": "/redoc",
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
            "dashboard": "/api/dashboard",
            "settings": "/api/settings",
        },
    }
