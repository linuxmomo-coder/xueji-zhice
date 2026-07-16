from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.utils import success
from app.core.config import settings
from app.db.session import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas_account import AccountDeactivateRequest, PasswordChangeRequest, SessionRead
from app.services.account import (
    change_password,
    deactivate_account,
    list_sessions,
    revoke_all_sessions,
    revoke_session,
)
from app.services.audit import add_audit_event

router = APIRouter(prefix="/account", tags=["账号管理"])


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        domain=settings.cookie_domain,
        path=f"{settings.api_prefix}/auth",
        secure=settings.secure_cookies,
        httponly=True,
        samesite=settings.cookie_samesite,
    )


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def update_password(
    payload: PasswordChangeRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    change_password(
        db,
        user=current_user,
        current_password=payload.current_password,
        new_password=payload.new_password,
        revoke_other_sessions=payload.revoke_other_sessions,
    )
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="account.password.change",
        resource_type="user",
        resource_id=current_user.id,
        request_id=request.state.request_id,
        after_data={"revoke_other_sessions": payload.revoke_other_sessions},
    )
    db.commit()
    if payload.revoke_other_sessions:
        _clear_refresh_cookie(response)


@router.get("/sessions")
def get_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rows = list_sessions(db, current_user.id)
    return success(
        request,
        [SessionRead.model_validate(row).model_dump() for row in rows],
        total=len(rows),
    )


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    session = revoke_session(db, user_id=current_user.id, session_id=session_id)
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="account.session.revoke",
        resource_type="refresh_session",
        resource_id=session.id,
        request_id=request.state.request_id,
        after_data={"revoked_at": session.revoked_at.isoformat() if session.revoked_at else None},
    )
    db.commit()
    return success(request, SessionRead.model_validate(session).model_dump())


@router.delete("/sessions", status_code=status.HTTP_204_NO_CONTENT)
def delete_all_sessions(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    revoke_all_sessions(db, current_user.id)
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="account.session.revoke_all",
        resource_type="user",
        resource_id=current_user.id,
        request_id=request.state.request_id,
    )
    db.commit()
    _clear_refresh_cookie(response)


@router.post("/deactivate", status_code=status.HTTP_204_NO_CONTENT)
def deactivate(
    payload: AccountDeactivateRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    deactivate_account(
        db,
        user=current_user,
        password=payload.password,
        confirmation=payload.confirmation,
    )
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=None,
        action="account.deactivate",
        resource_type="user",
        resource_id=current_user.id,
        request_id=request.state.request_id,
    )
    db.commit()
    _clear_refresh_cookie(response)
