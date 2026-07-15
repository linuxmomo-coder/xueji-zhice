from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.utils import success
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import LoginRequest, LogoutRequest, RefreshRequest, RegisterParentRequest, UserRead
from app.services.auth import login, register_parent, revoke_refresh_token, rotate_refresh_token

router = APIRouter(prefix="/auth", tags=["认证"])


def _token_payload(user: User, access: str, refresh: str, family_id: str | None) -> dict:
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "user": UserRead.model_validate(user).model_dump(),
        "family_id": family_id,
    }


@router.post("/register/parent", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterParentRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    user, access, refresh, family_id = register_parent(
        db,
        email=str(payload.email),
        password=payload.password,
        display_name=payload.display_name,
        family_name=payload.family_name,
        user_agent=request.headers.get("User-Agent"),
    )
    return success(request, _token_payload(user, access, refresh, family_id))


@router.post("/login")
def login_user(payload: LoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    user, access, refresh, family_id = login(
        db,
        email=str(payload.email),
        password=payload.password,
        user_agent=request.headers.get("User-Agent"),
    )
    return success(request, _token_payload(user, access, refresh, family_id))


@router.post("/refresh")
def refresh(payload: RefreshRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    user, access, refresh_token, family_id = rotate_refresh_token(
        db, payload.refresh_token, request.headers.get("User-Agent")
    )
    return success(request, _token_payload(user, access, refresh_token, family_id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> None:
    revoke_refresh_token(db, payload.refresh_token)


@router.get("/me")
def me(request: Request, user: User = Depends(get_current_user)) -> dict:
    return success(request, UserRead.model_validate(user).model_dump())
