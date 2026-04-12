import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from .database import init_db, AUDIO_DIR, VIDEO_DIR
from .routers import (
    questions_router,
    question_bank_router,
    job_setup_router,
    evaluate_router,
    report_router,
    session_router,
    testdata_router,
    settings_router,
    tts_router,
    probe_router,
)
from .rate_limit import RateLimiter, get_remote_address

rate_limiter = RateLimiter(requests=20, period=60.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="AI Interview Module", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


os.makedirs(AUDIO_DIR, exist_ok=True)
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

os.makedirs(VIDEO_DIR, exist_ok=True)
app.mount("/video", StaticFiles(directory=VIDEO_DIR), name="video")

app.include_router(questions_router)
app.include_router(question_bank_router)
app.include_router(job_setup_router)
app.include_router(evaluate_router)
app.include_router(report_router)
app.include_router(session_router)
app.include_router(testdata_router)
app.include_router(settings_router)
app.include_router(tts_router)
app.include_router(probe_router)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "ai-interview-module"}
