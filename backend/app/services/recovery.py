from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ApiError
from app.core.security import hash_password
from app.models import AccountToken, RefreshSession, User
from app.repositories.users import get_by_email
from app.services.mailer import MailDeliveryError, send_email

EMAIL_VERIFICATION = "email_verification"
PASSWORD_RESET = "password_reset"


def _fingerprint(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _create_token(
    db: Session,
    *,
    user_id: str,
    purpose: str,
    lifetime: timedelta,
    requested_ip: str | None,
) -> tuple[AccountToken, str]:
    now = datetime.now(timezone.utc)
    db.execute(
        update(AccountToken)
        .where(
            AccountToken.user_id == user_id,
            AccountToken.purpose == purpose,
            AccountToken.used_at.is_(None),
            AccountToken.expires_at > now,
        )
        .values(used_at=now)
    )
    raw_token = secrets.token_urlsafe(32)
    record = AccountToken(
        user_id=user_id,
        purpose=purpose,
        token_hash=_fingerprint(raw_token),
        expires_at=now + lifetime,
        requested_ip=requested_ip,
    )
    db.add(record)
    db.flush()
    return record, raw_token


def is_email_verified(db: Session, user_id: str) -> bool:
    return db.scalar(
        select(AccountToken.id).where(
            AccountToken.user_id == user_id,
            AccountToken.purpose == EMAIL_VERIFICATION,
            AccountToken.used_at.is_not(None),
        ).limit(1)
    ) is not None


def require_verified_email(db: Session, user: User) -> None:
    if settings.require_email_verification and not is_email_verified(db, user.id):
        raise ApiError(403, "AUTH_006", "请先完成邮箱验证")


def issue_email_verification(
    db: Session,
    *,
    user: User,
    requested_ip: str | None,
) -> dict:
    if is_email_verified(db, user.id):
        return {"already_verified": True, "delivery": "not_required"}
    _, raw_token = _create_token(
        db,
        user_id=user.id,
        purpose=EMAIL_VERIFICATION,
        lifetime=timedelta(hours=settings.email_verification_hours),
        requested_ip=requested_ip,
    )
    db.commit()
    link = f"{settings.frontend_public_url.rstrip('/')}/?verify_email_token={quote(raw_token)}"
    try:
        delivered = send_email(
            recipient=user.email,
            subject="学迹智评：验证邮箱",
            text=f"请在有效期内打开以下链接完成邮箱验证：\n\n{link}\n\n如非本人操作，请忽略。",
        )
    except MailDeliveryError as exc:
        if settings.is_production:
            raise ApiError(503, "MAIL_001", "验证邮件暂时无法发送，请稍后重试") from exc
        delivered = False
    return {"already_verified": False, "delivery": "sent" if delivered else "disabled"}


def verify_email(db: Session, raw_token: str) -> User:
    now = datetime.now(timezone.utc)
    record = db.scalar(
        select(AccountToken).where(
            AccountToken.token_hash == _fingerprint(raw_token),
            AccountToken.purpose == EMAIL_VERIFICATION,
        )
    )
    if not record or record.used_at is not None or record.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise ApiError(400, "AUTH_007", "邮箱验证链接无效或已过期")
    user = db.get(User, record.user_id)
    if not user or user.status != "active":
        raise ApiError(400, "AUTH_007", "邮箱验证链接无效")
    record.used_at = now
    db.commit()
    return user


def request_password_reset(db: Session, *, email: str, requested_ip: str | None) -> dict:
    user = get_by_email(db, email.strip().lower())
    if not user or user.status != "active":
        return {"accepted": True}
    _, raw_token = _create_token(
        db,
        user_id=user.id,
        purpose=PASSWORD_RESET,
        lifetime=timedelta(minutes=settings.password_reset_minutes),
        requested_ip=requested_ip,
    )
    db.commit()
    link = f"{settings.frontend_public_url.rstrip('/')}/?password_reset_token={quote(raw_token)}"
    try:
        send_email(
            recipient=user.email,
            subject="学迹智评：重置密码",
            text=f"请在有效期内打开以下链接重置密码：\n\n{link}\n\n如非本人操作，请忽略。",
        )
    except MailDeliveryError as exc:
        if settings.is_production:
            raise ApiError(503, "MAIL_001", "重置邮件暂时无法发送，请稍后重试") from exc
    return {"accepted": True}


def reset_password(db: Session, *, raw_token: str, new_password: str) -> User:
    now = datetime.now(timezone.utc)
    record = db.scalar(
        select(AccountToken).where(
            AccountToken.token_hash == _fingerprint(raw_token),
            AccountToken.purpose == PASSWORD_RESET,
        )
    )
    if not record or record.used_at is not None or record.expires_at.replace(tzinfo=timezone.utc) <= now:
        raise ApiError(400, "AUTH_008", "密码重置链接无效或已过期")
    user = db.get(User, record.user_id)
    if not user or user.status != "active":
        raise ApiError(400, "AUTH_008", "密码重置链接无效")
    user.password_hash = hash_password(new_password)
    record.used_at = now
    db.execute(
        update(RefreshSession)
        .where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()
    return user
