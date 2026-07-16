from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import hash_password, verify_password
from app.models import Family, RefreshSession, Student, User


def change_password(
    db: Session,
    *,
    user: User,
    current_password: str,
    new_password: str,
    revoke_other_sessions: bool,
) -> None:
    if not verify_password(current_password, user.password_hash):
        raise ApiError(401, "ACCOUNT_001", "当前密码不正确")
    if verify_password(new_password, user.password_hash):
        raise ApiError(422, "ACCOUNT_002", "新密码不能与当前密码相同")
    user.password_hash = hash_password(new_password)
    if revoke_other_sessions:
        now = datetime.now(timezone.utc)
        db.execute(
            update(RefreshSession)
            .where(
                RefreshSession.user_id == user.id,
                RefreshSession.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
    db.commit()


def list_sessions(db: Session, user_id: str) -> list[RefreshSession]:
    return list(
        db.scalars(
            select(RefreshSession)
            .where(RefreshSession.user_id == user_id)
            .order_by(RefreshSession.created_at.desc())
        ).all()
    )


def revoke_session(db: Session, *, user_id: str, session_id: str) -> RefreshSession:
    session = db.get(RefreshSession, session_id)
    if not session or session.user_id != user_id:
        raise ApiError(404, "ACCOUNT_003", "登录会话不存在")
    if session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(session)
    return session


def revoke_all_sessions(db: Session, user_id: str) -> None:
    db.execute(
        update(RefreshSession)
        .where(
            RefreshSession.user_id == user_id,
            RefreshSession.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.commit()


def deactivate_account(db: Session, *, user: User, password: str, confirmation: str) -> None:
    if confirmation != "停用我的账号":
        raise ApiError(422, "ACCOUNT_004", "请输入指定确认文字")
    if not verify_password(password, user.password_hash):
        raise ApiError(401, "ACCOUNT_001", "当前密码不正确")
    if user.role == "parent":
        family = db.scalar(select(Family).where(Family.primary_guardian_user_id == user.id, Family.status == "active"))
        if family:
            active_students = db.scalar(
                select(Student.id).where(Student.family_id == family.id, Student.status == "active").limit(1)
            )
            if active_students:
                raise ApiError(409, "ACCOUNT_005", "主监护人账号仍有关联学生，请先转移监护权或联系管理员")
    now = datetime.now(timezone.utc)
    user.status = "deactivated"
    user.deleted_at = now
    db.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()
