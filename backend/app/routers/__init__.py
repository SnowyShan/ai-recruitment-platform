from .auth import router as auth_router
from .jobs import router as jobs_router
from .candidates import router as candidates_router
from .applications import router as applications_router
from .screening import router as screening_router
from .dashboard import router as dashboard_router

__all__ = [
    "auth_router",
    "jobs_router", 
    "candidates_router",
    "applications_router",
    "screening_router",
    "dashboard_router"
]
