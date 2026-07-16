from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import GuardianConsent

CURRENT_TERMS_VERSION = "2026-07-16"
CURRENT_PRIVACY_VERSION = "2026-07-16"
CURRENT_CHILD_POLICY_VERSION = "2026-07-16"
REQUIRED_CHILD_SCOPE = {
    "student_profile": True,
    "practice_records": True,
    "learning_documents": True,
    "automated_analysis": False,
}


def current_policy_payload() -> dict:
    return {
        "terms_version": CURRENT_TERMS_VERSION,
        "privacy_version": CURRENT_PRIVACY_VERSION,
        "child_policy_version": CURRENT_CHILD_POLICY_VERSION,
        "required_scope": REQUIRED_CHILD_SCOPE,
    }


def record_guardian_consent(
    db: Session,
    *,
    guardian_user_id: str,
    family_id: str,
    terms_version: str,
    privacy_version: str,
    child_policy_version: str,
    consent_scope: dict,
    ip_address: str | None,
    user_agent: str | None,
    student_id: str | None = None,
) -> GuardianConsent:
    if terms_version != CURRENT_TERMS_VERSION:
        raise ApiError(409, "LEGAL_001", "服务条款版本已更新，请重新确认")
    if privacy_version != CURRENT_PRIVACY_VERSION:
        raise ApiError(409, "LEGAL_002", "隐私政策版本已更新，请重新确认")
    if child_policy_version != CURRENT_CHILD_POLICY_VERSION:
        raise ApiError(409, "LEGAL_003", "儿童个人信息保护规则已更新，请重新确认")
    missing = [key for key, required in REQUIRED_CHILD_SCOPE.items() if required and not consent_scope.get(key)]
    if missing:
        raise ApiError(422, "LEGAL_004", f"缺少必要监护人授权：{', '.join(missing)}")

    now = datetime.now(timezone.utc)
    active_rows = list(
        db.scalars(
            select(GuardianConsent).where(
                GuardianConsent.guardian_user_id == guardian_user_id,
                GuardianConsent.family_id == family_id,
                GuardianConsent.student_id == student_id,
                GuardianConsent.revoked_at.is_(None),
            )
        ).all()
    )
    for row in active_rows:
        row.revoked_at = now

    consent = GuardianConsent(
        guardian_user_id=guardian_user_id,
        family_id=family_id,
        student_id=student_id,
        terms_version=terms_version,
        privacy_version=privacy_version,
        child_policy_version=child_policy_version,
        consent_scope=consent_scope,
        accepted_at=now,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(consent)
    db.flush()
    return consent


def get_active_family_consent(db: Session, guardian_user_id: str, family_id: str) -> GuardianConsent | None:
    return db.scalar(
        select(GuardianConsent)
        .where(
            GuardianConsent.guardian_user_id == guardian_user_id,
            GuardianConsent.family_id == family_id,
            GuardianConsent.student_id.is_(None),
            GuardianConsent.revoked_at.is_(None),
        )
        .order_by(GuardianConsent.accepted_at.desc())
    )


def require_active_child_consent(db: Session, guardian_user_id: str, family_id: str) -> GuardianConsent:
    consent = get_active_family_consent(db, guardian_user_id, family_id)
    if not consent:
        raise ApiError(403, "LEGAL_005", "请先由监护人完成儿童个人信息处理授权")
    if (
        consent.terms_version != CURRENT_TERMS_VERSION
        or consent.privacy_version != CURRENT_PRIVACY_VERSION
        or consent.child_policy_version != CURRENT_CHILD_POLICY_VERSION
    ):
        raise ApiError(409, "LEGAL_006", "授权规则已更新，请监护人重新确认")
    missing = [key for key, required in REQUIRED_CHILD_SCOPE.items() if required and not consent.consent_scope.get(key)]
    if missing:
        raise ApiError(403, "LEGAL_005", "当前授权范围不足")
    return consent


def revoke_consent(db: Session, consent: GuardianConsent) -> GuardianConsent:
    if consent.revoked_at is None:
        consent.revoked_at = datetime.now(timezone.utc)
        db.flush()
    return consent
