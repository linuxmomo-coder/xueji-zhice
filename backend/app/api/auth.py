from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.utils import success
from app.core.config import settings
from app.core.errors import ApiError
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import LoginRequest, RegisterParentRequest, UserRead
from app.services.auth import login, register_parent, revoke_refresh_token, rotate_refresh_token

router = APIRouter(prefix="/auth", tags=["认证"])


def _token_payload(user: User, access: str, family_id: str | None) -> dict:
    return {
        "access_token": access,
        "token_type": "bearer",
        "user": UserRead.model_validate(user).model_dump(),
        "family_id": family_id,
    }


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=refresh_token,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.secure_cookies,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path=f"{settings.api_prefix}/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        domain=settings.cookie_domain,
        path=f"{settings.api_prefix}/auth",
        secure=settings.secure_cookies,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


@router.post("/register/parent", status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterParentRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    user, access, refresh, family_id = register_parent(
        db,
        email=str(payload.email),
        password=payload.password,
        display_name=payload.display_name,
        family_name=payload.family_name,
        user_agent=request.headers.get("User-Agent"),
    )
    _set_refresh_cookie(response, refresh)
    return success(request, _token_payload(user, access, family_id))


@router.post("/login")
def login_user(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> dict:
    user, access, refresh, family_id = login(
        db,
        email=str(payload.email),
        password=payload.password,
        role=payload.role,
        user_agent=request.headers.get("User-Agent"),
    )
    _set_refresh_cookie(response, refresh)
    return success(request, _token_payload(user, access, family_id))


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> dict:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if not refresh_token:
        raise ApiError(401, "AUTH_005", "刷新会话不存在，请重新登录")
    user, access, rotated_refresh, family_id = rotate_refresh_token(
        db, refresh_token, request.headers.get("User-Agent")
    )
    _set_refresh_cookie(response, rotated_refresh)
    return success(request, _token_payload(user, access, family_id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    refresh_token = request.cookies.get(settings.refresh_cookie_name)
    if refresh_token:
        revoke_refresh_token(db, refresh_token)
    _clear_refresh_cookie(response)


@router.get("/me")
def me(request: Request, user: User = Depends(get_current_user)) -> dict:
    return success(request, UserRead.model_validate(user).model_dump())
