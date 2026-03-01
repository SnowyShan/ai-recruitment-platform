from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from .database import init_db
from .routers import questions_router, evaluate_router, report_router, session_router, testdata_router, settings_router

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

app.include_router(questions_router)
app.include_router(evaluate_router)
app.include_router(report_router)
app.include_router(session_router)
app.include_router(testdata_router)
app.include_router(settings_router)

@app.get("/health")
def health():
    return {"status": "healthy", "service": "ai-interview-module"}
