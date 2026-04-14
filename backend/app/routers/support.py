from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import SupportRequest, User
from ..schemas import SupportRequestCreate, SupportRequestResponse
from ..auth import get_current_user

router = APIRouter(
    prefix="/api/support",
    tags=["support"]
)

@router.post("/", response_model=SupportRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_support_request(
    request: SupportRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new support request
    """
    db_request = SupportRequest(
        **request.model_dump(),
        user_id=current_user.id
    )
    db.add(db_request)
    db.commit()
    db.refresh(db_request)
    return db_request

@router.get("/my-requests", response_model=List[SupportRequestResponse])
async def get_my_support_requests(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all support requests for the current user
    """
    return db.query(SupportRequest).filter(SupportRequest.user_id == current_user.id).all()
