import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from .database import init_db, AUDIO_DIR
from .routers import (
    questions_router, question_bank_router, job_setup_router,
    evaluate_router, report_router, session_router,
    testdata_router, settings_router, tts_router,
)

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

# Serve generated audio files as static assets
os.makedirs(AUDIO_DIR, exist_ok=True)
app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")

app.include_router(questions_router)
app.include_router(question_bank_router)
app.include_router(job_setup_router)
app.include_router(evaluate_router)
app.include_router(report_router)
app.include_router(session_router)
app.include_router(testdata_router)
app.include_router(settings_router)
app.include_router(tts_router)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "ai-interview-module"}
