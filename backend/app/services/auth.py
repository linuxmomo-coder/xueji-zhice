from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_fingerprint,
    verify_password,
)
from app.models import Family, FamilyMember, RefreshSession, User
from app.repositories.users import get_by_email, get_primary_family_id


def issue_tokens(db: Session, user: User, user_agent: str | None = None) -> tuple[str, str, str | None]:
    family_id = get_primary_family_id(db, user.id)
    access_token = create_access_token(user.id, user.role, family_id)
    refresh_token, jti, expires_at = create_refresh_token(user.id, user.role, family_id)
    db.add(
        RefreshSession(
            user_id=user.id,
            token_jti=jti,
            token_hash=token_fingerprint(refresh_token),
            expires_at=expires_at,
            user_agent=user_agent,
        )
    )
    return access_token, refresh_token, family_id


def register_parent(
    db: Session, *, email: str, password: str, display_name: str, family_name: str, user_agent: str | None
) -> tuple[User, str, str, str]:
    normalized_email = email.lower().strip()
    if get_by_email(db, normalized_email):
        raise ApiError(409, "AUTH_003", "该邮箱已注册")
    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        role="parent",
        display_name=display_name.strip(),
    )
    db.add(user)
    db.flush()
    family = Family(name=family_name.strip(), primary_guardian_user_id=user.id)
    db.add(family)
    db.flush()
    db.add(
        FamilyMember(
            family_id=family.id,
            user_id=user.id,
            relation_type="guardian",
            is_primary_guardian=True,
            permissions={"manage_students": True, "confirm_documents": True},
        )
    )
    access_token, refresh_token, _ = issue_tokens(db, user, user_agent)
    db.commit()
    return user, access_token, refresh_token, family.id


def login(
    db: Session,
    *,
    email: str,
    password: str,
    role: str,
    user_agent: str | None,
) -> tuple[User, str, str, str | None]:
    user = get_by_email(db, email)
    if (
        not user
        or user.status != "active"
        or user.role != role
        or not verify_password(password, user.password_hash)
    ):
        raise ApiError(401, "AUTH_004", "账号、密码或登录身份不匹配")
    user.last_login_at = datetime.now(timezone.utc)
    access_token, refresh_token, family_id = issue_tokens(db, user, user_agent)
    db.commit()
    return user, access_token, refresh_token, family_id


def rotate_refresh_token(db: Session, refresh_token: str, user_agent: str | None) -> tuple[User, str, str, str | None]:
    try:
        payload = decode_token(refresh_token, "refresh")
    except ValueError as exc:
        raise ApiError(401, "AUTH_005", str(exc)) from exc
    session = db.query(RefreshSession).filter(RefreshSession.token_jti == payload["jti"]).one_or_none()
    now = datetime.now(timezone.utc)
    if (
        not session
        or session.revoked_at is not None
        or session.expires_at.replace(tzinfo=timezone.utc) <= now
        or session.token_hash != token_fingerprint(refresh_token)
    ):
        raise ApiError(401, "AUTH_005", "刷新令牌已失效")
    user = db.get(User, payload["sub"])
    if not user or user.status != "active":
        raise ApiError(401, "AUTH_001", "用户不存在或已停用")
    session.revoked_at = now
    access, refresh, family_id = issue_tokens(db, user, user_agent)
    db.commit()
    return user, access, refresh, family_id


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    try:
        payload = decode_token(refresh_token, "refresh")
    except ValueError:
        return
    session = db.query(RefreshSession).filter(RefreshSession.token_jti == payload["jti"]).one_or_none()
    if session and session.revoked_at is None:
        session.revoked_at = datetime.now(timezone.utc)
        db.commit()
