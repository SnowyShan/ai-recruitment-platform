from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from .. import models, schemas, auth
from ..database import get_db

router = APIRouter(prefix="/api/settings", tags=["Settings"])

DEFAULTS = {
    "auto_invite_screening": "false",
    "auto_invite_threshold": "75",
}


def _get_value(db: Session, key: str) -> str:
    row = db.query(models.Setting).filter(models.Setting.key == key).first()
    return row.value if row else DEFAULTS.get(key, "")


def _set_value(db: Session, key: str, value: str):
    row = db.query(models.Setting).filter(models.Setting.key == key).first()
    if row:
        row.value = value
        row.updated_at = datetime.utcnow()
    else:
        db.add(models.Setting(key=key, value=value))


@router.get("/", response_model=schemas.SettingsResponse)
async def get_settings(
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    return schemas.SettingsResponse(
        auto_invite_screening=_get_value(db, "auto_invite_screening") == "true",
        auto_invite_threshold=int(_get_value(db, "auto_invite_threshold")),
    )


@router.put("/", response_model=schemas.SettingsResponse)
async def update_settings(
    payload: schemas.SettingsUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    if payload.auto_invite_screening is not None:
        _set_value(db, "auto_invite_screening", str(payload.auto_invite_screening).lower())
    if payload.auto_invite_threshold is not None:
        _set_value(db, "auto_invite_threshold", str(payload.auto_invite_threshold))
    db.commit()

    return schemas.SettingsResponse(
        auto_invite_screening=_get_value(db, "auto_invite_screening") == "true",
        auto_invite_threshold=int(_get_value(db, "auto_invite_threshold")),
    )
