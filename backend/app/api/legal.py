from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.utils import success
from app.core.errors import ApiError
from app.db.session import get_db
from app.dependencies import current_family_id, get_current_user, require_roles
from app.models import GuardianConsent, User
from app.schemas_account import GuardianConsentInput, GuardianConsentRead
from app.services.audit import add_audit_event
from app.services.legal import current_policy_payload, record_guardian_consent, revoke_consent

router = APIRouter(prefix="/legal", tags=["隐私与授权"])


@router.get("/current")
def current_policy(request: Request) -> dict:
    return success(request, current_policy_payload())


@router.get("/consents")
def list_consents(
    request: Request,
    family_id: str = Depends(current_family_id),
    current_user: User = Depends(require_roles("parent")),
    db: Session = Depends(get_db),
) -> dict:
    rows = list(
        db.scalars(
            select(GuardianConsent)
            .where(
                GuardianConsent.guardian_user_id == current_user.id,
                GuardianConsent.family_id == family_id,
            )
            .order_by(GuardianConsent.accepted_at.desc())
        ).all()
    )
    return success(
        request,
        [GuardianConsentRead.model_validate(row).model_dump() for row in rows],
        total=len(rows),
    )


@router.post("/consents", status_code=status.HTTP_201_CREATED)
def create_consent(
    payload: GuardianConsentInput,
    request: Request,
    family_id: str = Depends(current_family_id),
    current_user: User = Depends(require_roles("parent")),
    db: Session = Depends(get_db),
) -> dict:
    consent = record_guardian_consent(
        db,
        guardian_user_id=current_user.id,
        family_id=family_id,
        terms_version=payload.terms_version,
        privacy_version=payload.privacy_version,
        child_policy_version=payload.child_policy_version,
        consent_scope=payload.consent_scope,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("User-Agent"),
    )
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=family_id,
        action="legal.guardian_consent.accept",
        resource_type="guardian_consent",
        resource_id=consent.id,
        request_id=request.state.request_id,
        after_data={
            "terms_version": consent.terms_version,
            "privacy_version": consent.privacy_version,
            "child_policy_version": consent.child_policy_version,
            "consent_scope": consent.consent_scope,
        },
    )
    db.commit()
    db.refresh(consent)
    return success(request, GuardianConsentRead.model_validate(consent).model_dump())


@router.post("/consents/{consent_id}/revoke")
def revoke_guardian_consent(
    consent_id: str,
    request: Request,
    family_id: str = Depends(current_family_id),
    current_user: User = Depends(require_roles("parent")),
    db: Session = Depends(get_db),
) -> dict:
    consent = db.get(GuardianConsent, consent_id)
    if (
        not consent
        or consent.guardian_user_id != current_user.id
        or consent.family_id != family_id
    ):
        raise ApiError(404, "LEGAL_007", "授权记录不存在")
    revoke_consent(db, consent)
    add_audit_event(
        db,
        actor_user_id=current_user.id,
        family_id=family_id,
        action="legal.guardian_consent.revoke",
        resource_type="guardian_consent",
        resource_id=consent.id,
        request_id=request.state.request_id,
        before_data={"revoked_at": None},
        after_data={"revoked_at": consent.revoked_at.isoformat() if consent.revoked_at else None},
    )
    db.commit()
    db.refresh(consent)
    return success(request, GuardianConsentRead.model_validate(consent).model_dump())
